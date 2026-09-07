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
        prog="%%matlab", add_help=False, description="Run MATLAB in the shared session."
    )
    parser.add_argument(
        "-i",
        "--input",
        action="append",
        default=[],
        metavar="NAME",
        help="Python object to push into MATLAB (DataFrame, array, list, number, text).",
    )
    parser.add_argument(
        "-o",
        "--output",
        action="append",
        default=[],
        metavar="NAME",
        help="MATLAB variable to bring back into Python, as its natural type.",
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
        """Run MATLAB in the session EconEnv keeps open.

        Line form, for a single statement::

            %matlab disp(version)

        Cell form, for a block::

            %%matlab
            x = 1:10;
            disp(mean(x))

        **Sending Python values in** with ``-i``. Repeat the flag for several::

            %%matlab -i x -i df
            disp(x)
            head(df)

        =============================  ==========================
        Python                         arrives in MATLAB as
        =============================  ==========================
        ``int``, ``float``, NumPy      ``double`` scalar
        ``bool``                       ``logical``
        ``complex``                    complex ``double``
        ``str``                        ``char``
        list, tuple, 1-D array         ``double`` column vector
        2-D array                      ``double``, shape preserved
        ``pandas.Series``              one-column ``table``
        ``pandas.DataFrame``           ``table``
        =============================  ==========================

        A 1-D sequence lands as a *column*, which is what a regressor, a series
        and a table column all want. ``%econ config matlab.vectors row`` changes
        it if you would rather have rows.

        **Bringing results back** with ``-o``. The Python type follows the
        MATLAB class, so a scalar is a number and not a one-cell DataFrame::

            %%matlab -o y -o A -o T
            y = 10;                       % -> 10.0
            A = [1 2; 3 4];               % -> 2-D numpy array
            T = table([1;2], [3;4]);      % -> pandas DataFrame

        =============================  ==========================
        MATLAB                         comes back as
        =============================  ==========================
        numeric scalar                 ``float`` (``int`` if integer class)
        complex scalar                 ``complex``
        logical scalar                 ``bool``
        ``char`` / ``string`` scalar   ``str``
        row or column vector           1-D ``numpy.ndarray``
        2-D matrix                     2-D ``numpy.ndarray``
        ``string`` array / cellstr     ``list`` of ``str``
        ``table`` / ``timetable``      ``pandas.DataFrame``
        =============================  ==========================

        Anything else — a struct, a mixed cell array, a model object — raises a
        ``DataTransferError`` naming the MATLAB class, rather than guessing.
        Convert it in MATLAB first (``struct2table``, ``table``) and pull that.

        **Figures** drawn by the cell are captured and displayed, each once.
        ``--no-graphs`` turns that off for one cell;
        ``%econ config matlab.graphics pdf`` makes them vector for publication.

        **Other flags**

        ``-q``          run without displaying the output
        ``--result``    return the :class:`ExecutionResult` object instead of
                        displaying it, for when you want ``.text`` or
                        ``.figures`` in Python

        The first MATLAB cell of a session takes about a minute while MATLAB
        starts; every cell after it is fast. ``%econ doctor matlab`` explains
        anything that will not start, and ``%econ matlab`` is a searchable
        catalogue of MATLAB commands for research work.
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
            engine.push(key, resolve_python_name(key, local_ns, shell_of(self)))

        result = engine.execute(code, capture_graphs=not args.no_graphs)

        if args.output:
            names = [strip_quotes(n) for n in args.output]
            values = [engine.pull_value(n) for n in names]
            push_outputs(shell_of(self), names, values)

        if args.result:
            return result
        return display_result(result, quiet=args.quiet)
