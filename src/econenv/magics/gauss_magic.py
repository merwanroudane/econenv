"""``%gauss`` and ``%%gauss``.

GAUSS runs through its terminal executable, one process per cell. That has one
consequence worth knowing before anything looks wrong: **GAUSS compiles the
whole cell before running any of it**, so a mistyped name on the last line means
the first line never ran either. The error says so rather than leaving you to
wonder why a `print` produced nothing.

Values assigned at the top level of a cell are carried into the next one using
GAUSS's own ``save`` and ``load``. Procedures and ``#include`` state are not —
that is a real limit of running a fresh process each time, and it is documented
rather than papered over.
"""

from __future__ import annotations

from typing import Any, Optional

from IPython.core.magic import Magics, cell_magic, line_magic, magics_class, needs_local_scope

from ..engines import registry as engine_registry
from ._common import (
    MagicParser,
    display_result,
    push_outputs,
    resolve_python_name,
    shell_of,
    split_line,
    strip_quotes,
)


def _parser() -> MagicParser:
    parser = MagicParser(
        prog="%%gauss", add_help=False, description="Run GAUSS in the shared session."
    )
    parser.add_argument(
        "-i",
        "--input",
        action="append",
        default=[],
        metavar="NAME",
        help="Python object to push into GAUSS (DataFrame, array, list, number, text).",
    )
    parser.add_argument(
        "-o",
        "--output",
        action="append",
        default=[],
        metavar="NAME",
        help="GAUSS symbol to bring back into Python, as its natural type.",
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress output.")
    parser.add_argument(
        "--no-graphs", action="store_true", help="Do not capture plots this cell draws."
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
class GaussMagics(Magics):
    """GAUSS cell and line magics."""

    @line_magic("gauss")
    @cell_magic("gauss")
    @needs_local_scope
    def gauss(
        self, line: str = "", cell: Optional[str] = None, local_ns: Optional[dict] = None
    ) -> Any:
        """Run GAUSS code.

        Line form::

            %gauss print rndn(2,2);

        Cell form::

            %%gauss
            x = rndn(100, 3);
            print meanc(x);

        **Sending Python values in** with ``-i``, repeated for several::

            %%gauss -i df -i k
            print rows(df);

        ==============================  ==========================
        Python                          arrives in GAUSS as
        ==============================  ==========================
        ``int``, ``float``, NumPy       scalar
        ``bool``                        1 or 0
        ``str``                         string
        list, tuple, 1-D array          column vector
        2-D array                       matrix, shape preserved
        ``pandas.DataFrame``            numeric matrix
        ==============================  ==========================

        A GAUSS matrix holds only numbers, so a DataFrame's text columns cannot
        cross. They are **named in a warning** rather than dropped in silence,
        and the column names are remembered on the Python side so the frame
        comes back with them.

        **Bringing results back** with ``-o``::

            %%gauss -o b -o n
            b = y / X;        /* least squares */
            n = rows(y);

        ==============================  ==========================
        GAUSS                           comes back as
        ==============================  ==========================
        1x1 matrix                      ``float``
        row or column vector            1-D ``numpy.ndarray``
        matrix                          2-D ``numpy.ndarray``
        string                          ``str``
        ==============================  ==========================

        Numbers cross at seventeen significant digits, which round-trips an
        IEEE double exactly — GAUSS's own ``csvWriteM`` writes about fifteen,
        which is not enough to keep GAUSS in step with the other engines.

        **What does not carry between cells.** Top-level values do; procedures,
        ``#include``s and library state do not, because each cell is a new
        process. Define a procedure in the same cell that uses it.
        """
        local_ns = local_ns or {}
        parser = _parser()

        if cell is None:
            tokens = split_line(line)
            flags, code_tokens = _split_flags(tokens)
            args = parser.parse_args(flags)
            code = " ".join(code_tokens)
            if not code:
                raise ValueError("%gauss needs a command, or use %%gauss for a block.")
        else:
            args = parser.parse_args(split_line(line))
            code = cell

        engine = engine_registry.get("gauss")
        engine.ensure_started()

        for name in args.input:
            key = strip_quotes(name)
            engine.push(key, resolve_python_name(key, local_ns, shell_of(self)))

        result = engine.execute(code, capture_graphs=not args.no_graphs)

        if args.output:
            names = [strip_quotes(n) for n in args.output]
            values = [engine.pull_value(n) for n in names]
            push_outputs(shell_of(self), names, values)

        if args.result:
            return result
        return display_result(result, quiet=args.quiet)
