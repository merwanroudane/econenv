"""``%Rec`` / ``%%Rec`` — and ``%R`` / ``%%R`` when nothing else owns them."""

from __future__ import annotations

from typing import Any, Optional

from IPython.core.magic import Magics, cell_magic, line_magic, magics_class, needs_local_scope

from .._logging import get_logger
from ..engines import registry as engine_registry
from ._common import MagicParser, display_result, resolve_python_name, shell_of, split_line

_log = get_logger("magics.r")


def _parser() -> MagicParser:
    parser = MagicParser(
        prog="%%Rec", add_help=False, description="Run R code in the shared session."
    )
    parser.add_argument(
        "-i",
        "--input",
        action="append",
        default=[],
        metavar="NAME",
        help="Python object to push into R before running (repeatable).",
    )
    parser.add_argument(
        "-o",
        "--output",
        action="append",
        default=[],
        metavar="NAME",
        help="R object to pull back into Python afterwards (repeatable).",
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress the output.")
    parser.add_argument("--no-graphics", action="store_true", help="Do not open a plot device.")
    parser.add_argument(
        "-r",
        "--result",
        action="store_true",
        help="Return the ExecutionResult instead of printing.",
    )
    return parser


@magics_class
class RMagics(Magics):
    """EconEnv's R magics."""

    @needs_local_scope
    @line_magic("Rec")
    @cell_magic("Rec")
    def rec(
        self, line: str = "", cell: Optional[str] = None, local_ns: Optional[dict] = None
    ) -> Any:
        """Run R code.

        Line form::

            %Rec summary(fit)
            %Rec -o coefs coefs <- coef(fit)

        Cell form::

            %%Rec -i df -o fit_table
            fit <- lm(y ~ x, data = df)
            fit_table <- as.data.frame(summary(fit)$coefficients)
        """
        return self._run(line, cell, local_ns or {})

    def _run(self, line: str, cell: Optional[str], local_ns: dict) -> Any:
        parser = _parser()
        if cell is None:
            tokens = split_line(line)
            flags, code_tokens = _split_flags(tokens)
            args = parser.parse_args(flags)
            code = " ".join(code_tokens)
            if not code:
                raise ValueError("%Rec needs R code on the same line, or use %%Rec for a cell.")
        else:
            args = parser.parse_args(split_line(line))
            code = cell

        engine = engine_registry.get("r")
        engine.ensure_started()

        for name in args.input:
            engine.push(name, resolve_python_name(name, local_ns, shell_of(self)))

        kwargs = {"graphics": "off"} if args.no_graphics else {}
        result = engine.execute(code, **kwargs)

        for name in args.output:
            shell_of(self).push({name: engine.pull(name)})

        if args.result:
            return result
        return display_result(result, quiet=args.quiet)

    @line_magic("Rec_pull")
    def rec_pull(self, line: str) -> Any:
        """``%Rec_pull <r_object>`` — return an R object as a pandas DataFrame."""
        name = line.strip()
        if not name:
            raise ValueError("Usage: %Rec_pull <r object name>")
        return engine_registry.get("r").pull(name)

    @line_magic("Rec_push")
    def rec_push(self, line: str) -> None:
        """``%Rec_push <python_name> [as <r_name>]`` — send a Python object to R."""
        tokens = split_line(line)
        if not tokens:
            raise ValueError("Usage: %Rec_push <python name> [as <r name>]")
        source = tokens[0]
        target = tokens[2] if len(tokens) >= 3 and tokens[1] == "as" else source
        engine_registry.get("r").push(target, shell_of(self).user_ns[source])


def _split_flags(tokens: list) -> tuple:
    """Separate leading option flags from the R code on a line magic."""
    flags, index = [], 0
    while index < len(tokens):
        token = tokens[index]
        if token.startswith("-"):
            flags.append(token)
            if token in {"-i", "--input", "-o", "--output"} and index + 1 < len(tokens):
                flags.append(tokens[index + 1])
                index += 1
            index += 1
        else:
            break
    return flags, tokens[index:]


def load_rpy2_magics(ipython: Any) -> bool:
    """Load rpy2's official ``%R`` / ``%%R`` if rpy2 is importable.

    Brief §7: when the official implementation exists, use it rather than
    imitating it.
    """
    import importlib.util

    if importlib.util.find_spec("rpy2") is None:
        return False
    try:
        ipython.run_line_magic("load_ext", "rpy2.ipython")
    except Exception as exc:
        _log.info("rpy2 is installed but its magics would not load: %s", exc)
        return False
    return True


def claim_short_r_names(ipython: Any) -> bool:
    """Alias ``%R``/``%%R`` to EconEnv's R magic, but only if they are free.

    Never shadows an existing magic — that is the collision rule in brief §3.
    """
    manager = ipython.magics_manager
    taken = "R" in manager.magics.get("line", {}) or "R" in manager.magics.get("cell", {})
    if taken:
        return False
    instance = None
    for magics in manager.registry.values():
        if isinstance(magics, RMagics):
            instance = magics
            break
    if instance is None:
        return False
    manager.register_function(instance.rec, magic_kind="line", magic_name="R")
    manager.register_function(instance.rec, magic_kind="cell", magic_name="R")
    return True
