"""Stata magics — delegated to PyStata, never reimplemented.

Brief §8 and §61 both say so, and there is a practical reason beyond obedience:
``%%stata`` in PyStata carries a Stata-aware tab-completer, ``-d``/``-f``
DataFrame options, ``-ret``/``-eret``/``-sret`` result capture and graph
rendering that StataCorp maintains against their own binary. Reimplementing it
would mean shipping a worse copy that goes stale on every Stata release.

EconEnv therefore loads ``pystata.ipython.stpymagic`` and adds only the pieces
PyStata does not have: engine lifecycle and EconEnv-shaped result objects, under
names that cannot collide (``%stata_pull``, ``%stata_push``, ``%stata_run``).
"""

from __future__ import annotations

from typing import Any, Optional

from IPython.core.magic import Magics, cell_magic, line_magic, magics_class

from .._logging import get_logger
from ..engines import registry as engine_registry
from ._common import MagicParser, display_result, shell_of, split_line, strip_quotes

_log = get_logger("magics.stata")


def load_stata_magics(ipython: Any) -> str:
    """Load PyStata's official magics. Returns a status string for ``%econ engines``."""
    engine = engine_registry.get("stata")
    if not engine.available:
        ipython.register_magics(StataHelperMagics)
        return "unavailable (Stata not found) — %stata_run still works once configured"
    try:
        loaded = engine.load_official_magics(ipython)  # type: ignore[attr-defined]
    except Exception as exc:
        _log.info("PyStata magics not loaded: %s", exc)
        loaded = False
    ipython.register_magics(StataHelperMagics)
    if loaded:
        return "pystata (official)"
    return "not loaded — Stata found but PyStata would not initialise"


@magics_class
class StataHelperMagics(Magics):
    """The Stata pieces PyStata does not provide, under non-colliding names."""

    @line_magic("stata_run")
    @cell_magic("stata_run")
    def stata_run(self, line: str = "", cell: Optional[str] = None) -> Any:
        """Run Stata code and return an EconEnv :class:`ExecutionResult`.

        ``%%stata`` remains the everyday magic; this one exists when you want
        the structured result object (return code, timing, engine version) for
        a script or a comparison rather than formatted output.
        """
        parser = MagicParser(prog="%%stata_run", add_help=False)
        parser.add_argument("-q", "--quiet", action="store_true")
        parser.add_argument("-r", "--result", action="store_true")
        if cell is None:
            tokens = split_line(line)
            flags = [t for t in tokens if t.startswith("-")]
            code = " ".join(t for t in tokens if not t.startswith("-"))
            args = parser.parse_args(flags)
        else:
            args = parser.parse_args(split_line(line))
            code = cell
        if not code.strip():
            raise ValueError("%stata_run needs Stata code.")

        engine = engine_registry.get("stata")
        engine.ensure_started()
        result = engine.execute(code)
        if args.result:
            return result
        return display_result(result, quiet=args.quiet)

    @line_magic("stata_pull")
    def stata_pull(self, line: str) -> Any:
        """``%stata_pull [frame]`` — Stata's dataset as a pandas DataFrame."""
        name = strip_quotes(line.strip()) or None
        return engine_registry.get("stata").pull(name)

    @line_magic("stata_push")
    def stata_push(self, line: str) -> None:
        """``%stata_push <dataframe> [as <frame>]`` — load a frame into Stata."""
        tokens = split_line(line)
        if not tokens:
            raise ValueError("Usage: %stata_push <dataframe name> [as <stata frame name>]")
        source = strip_quotes(tokens[0])
        target = strip_quotes(tokens[2]) if len(tokens) >= 3 and tokens[1] == "as" else "default"
        engine_registry.get("stata").push(target, shell_of(self).user_ns[source])

    @line_magic("stata_matrix")
    def stata_matrix(self, line: str) -> Any:
        """``%stata_matrix <name>`` — a Stata matrix (``r(table)``, ``e(b)``) as ndarray."""
        name = line.strip()
        if not name:
            raise ValueError("Usage: %stata_matrix r(table)")
        return engine_registry.get("stata").pull_matrix(name)
