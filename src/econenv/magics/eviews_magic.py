"""``%eviews`` / ``%%eviews`` — EViews inside the Python kernel.

No official EViews IPython magic exists (EViews 14 ships ``XeusEViews.exe``, a
*separate Jupyter kernel*, which would mean a second notebook rather than one),
so this magic is EconEnv's. It is a thin shell over
:class:`~econenv.engines.eviews_engine.EViewsEngine` — brief §9 asks for an
adapter, not scattered COM calls.
"""

from __future__ import annotations

from typing import Any, Optional

from IPython.core.magic import Magics, cell_magic, line_magic, magics_class, needs_local_scope

from ..engines import registry as engine_registry
from ._common import MagicParser, display_result, shell_of, split_line, strip_quotes


def _parser() -> MagicParser:
    parser = MagicParser(
        prog="%%eviews", add_help=False, description="Run EViews commands in the shared session."
    )
    parser.add_argument(
        "-i",
        "--input",
        action="append",
        default=[],
        metavar="NAME",
        help="Python DataFrame to push into a new EViews workfile page.",
    )
    parser.add_argument(
        "-o",
        "--output",
        action="append",
        default=[],
        metavar="NAME",
        help="Pull EViews series back into Python under this name.",
    )
    parser.add_argument("--page", default=None, help="Select this workfile page first.")
    parser.add_argument(
        "--append",
        action="store_true",
        help="With -i, write into the active page instead of creating a workfile.",
    )
    parser.add_argument("--no-graphs", action="store_true", help="Do not export graph objects.")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress output.")
    parser.add_argument(
        "-r",
        "--result",
        action="store_true",
        help="Return the ExecutionResult instead of printing.",
    )
    return parser


@magics_class
class EViewsMagics(Magics):
    """EViews line and cell magics."""

    @needs_local_scope
    @line_magic("eviews")
    @cell_magic("eviews")
    def eviews(
        self, line: str = "", cell: Optional[str] = None, local_ns: Optional[dict] = None
    ) -> Any:
        """Run EViews commands.

        Line form::

            %eviews create q 2000Q1 2020Q4
            %eviews equation eq1.ls y c x

        Cell form::

            %%eviews -i df -o resid
            equation eq1.ls y c x
            eq1.makeresid resid
        """
        local_ns = local_ns or {}
        parser = _parser()

        if cell is None:
            tokens = split_line(line)
            flags, code_tokens = _split_flags(tokens)
            args = parser.parse_args(flags)
            code = " ".join(code_tokens)
            if not code:
                raise ValueError("%eviews needs a command, or use %%eviews for a block.")
        else:
            args = parser.parse_args(split_line(line))
            code = cell

        engine = engine_registry.get("eviews")
        engine.ensure_started()

        for name in args.input:
            key = strip_quotes(name)
            obj = local_ns.get(key, shell_of(self).user_ns.get(key))
            if obj is None:
                raise NameError(f"{key!r} is not defined in Python.")
            engine.push(key, obj, new_workfile=not args.append)

        if args.page:
            engine.execute(f"pageselect {args.page}", capture_graphs=False)

        result = engine.execute(code, capture_graphs=not args.no_graphs)

        for name in args.output:
            key = strip_quotes(name)
            shell_of(self).push({key: engine.pull(key)})

        if args.result:
            return result
        return display_result(result, quiet=args.quiet)

    @line_magic("eviews_get")
    def eviews_get(self, line: str) -> Any:
        """``%eviews_get <expression>`` — evaluate an EViews scalar or string.

        The ``=`` prefix EViews needs for non-series expressions is added for
        you, so ``%eviews_get @vernum`` and ``%eviews_get eq1.@r2`` both work.
        """
        expression = line.strip()
        if not expression:
            raise ValueError("Usage: %eviews_get <eviews expression>")
        return engine_registry.get("eviews").pull_scalar(expression)

    @line_magic("eviews_pull")
    def eviews_pull(self, line: str) -> Any:
        """``%eviews_pull [series names]`` — read the active page into pandas."""
        names = line.strip() or None
        return engine_registry.get("eviews").pull(names)

    @line_magic("eviews_push")
    def eviews_push(self, line: str) -> None:
        """``%eviews_push <dataframe> [--append]`` — send a frame to EViews."""
        tokens = split_line(line)
        if not tokens:
            raise ValueError("Usage: %eviews_push <dataframe name> [--append]")
        name = strip_quotes(tokens[0])
        append = "--append" in tokens
        engine_registry.get("eviews").push(
            name, shell_of(self).user_ns[name], new_workfile=not append
        )

    @line_magic("eviews_show")
    def eviews_show(self, line: str) -> None:
        """``%eviews_show [on|off]`` — show or hide the EViews application window."""
        engine = engine_registry.get("eviews")
        engine.ensure_started()
        wanted = (line.strip() or "on").lower()
        engine.set_visible(wanted in {"on", "true", "1", "show"})  # type: ignore[attr-defined]


def _split_flags(tokens: list) -> tuple:
    flags, index = [], 0
    while index < len(tokens):
        token = tokens[index]
        if token.startswith("-"):
            flags.append(token)
            if token in {"-i", "--input", "-o", "--output", "--page"} and index + 1 < len(tokens):
                flags.append(tokens[index + 1])
                index += 1
            index += 1
        else:
            break
    return flags, tokens[index:]
