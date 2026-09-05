"""``%matlab`` and ``%%matlab``.

MATLAB is slow to start — about a minute cold — so the first cell that uses it
pays for the whole session and every later one is fast. That is worth knowing
before you assume something has hung, and it is why the engine is never started
by ``%econ status``.
"""

from __future__ import annotations

from typing import Any, Optional

from IPython.core.magic import Magics, cell_magic, line_magic, magics_class, needs_local_scope

from ..engines import registry as engine_registry
from ._common import MagicParser, display_result, push_outputs, shell_of, split_line, strip_quotes


def _parser() -> MagicParser:
    parser = MagicParser(
        prog="%%matlab", add_help=False, description="Run MATLAB in the shared session."
    )
    parser.add_argument(
        "-i",
        "--input",
        action="append",
        default=[],
        metavar="NAME",
        help="Python DataFrame to push into the MATLAB workspace as a table.",
    )
    parser.add_argument(
        "-o",
        "--output",
        action="append",
        default=[],
        metavar="NAME",
        help="MATLAB variable to bring back into Python after the cell runs.",
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress output.")
    parser.add_argument(
        "--no-graphs", action="store_true", help="Do not capture figures this cell draws."
    )
    parser.add_argument(
        "--result", action="store_true", help="Return the ExecutionResult instead of displaying it."
    )
    return parser


def _split_flags(tokens):
    """Separate leading flags from the code that follows, for the line form."""
    flags, code = [], []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in ("-i", "--input", "-o", "--output"):
            flags += tokens[index : index + 2]
            index += 2
            continue
        if token in ("-q", "--quiet", "--no-graphs", "--result"):
            flags.append(token)
            index += 1
            continue
        code = tokens[index:]
        break
    return flags, code


@magics_class
class MatlabMagics(Magics):
    """MATLAB cell and line magics."""

    @line_magic("matlab")
    @cell_magic("matlab")
    @needs_local_scope
    def matlab(
        self, line: str = "", cell: Optional[str] = None, local_ns: Optional[dict] = None
    ) -> Any:
        """Run MATLAB code.

        Line form::

            %matlab disp(version)

        Cell form::

            %%matlab -i df -o beta
            fit = fitlm(df, 'y ~ x1 + x2');
            beta = fit.Coefficients.Estimate;
        """
        local_ns = local_ns or {}
        parser = _parser()

        if cell is None:
            tokens = split_line(line)
            flags, code_tokens = _split_flags(tokens)
            args = parser.parse_args(flags)
            code = " ".join(code_tokens)
            if not code:
                raise ValueError("%matlab needs a command, or use %%matlab for a block.")
        else:
            args = parser.parse_args(split_line(line))
            code = cell

        engine = engine_registry.get("matlab")
        engine.ensure_started()

        for name in args.input:
            key = strip_quotes(name)
            obj = local_ns.get(key, shell_of(self).user_ns.get(key))
            if obj is None:
                raise NameError(f"{key!r} is not defined in Python.")
            engine.push(key, obj)

        result = engine.execute(code, capture_graphs=not args.no_graphs)

        if args.output:
            names = [strip_quotes(n) for n in args.output]
            values = [engine.pull(n) for n in names]
            push_outputs(shell_of(self), names, values)

        if args.result:
            return result
        return display_result(result, quiet=args.quiet)
