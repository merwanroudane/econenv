"""``%econ`` — the management magic (brief §13).

A single namespaced entry point with real subcommand parsing, so it cannot
collide with anything and its syntax is documented rather than guessed:

``%econ status``          engine table
``%econ engines``         detail, including who owns which magic name
``%econ versions``        version per engine
``%econ capabilities``    capability matrix
``%econ models``          estimator x engine matrix
``%econ doctor [engine] [--deep]``
``%econ start|stop|restart|reset [engine]``
``%econ config [key [value]]``
``%econ snapshot [path]``
``%econ push|pull``       one-off data moves
``%econ ols <formula> --data df [--engines ...]``
"""

from __future__ import annotations

import json
from typing import Any, List, Optional

from IPython.core.magic import Magics, line_magic, magics_class, needs_local_scope

from .. import services
from .._version import __version__
from ..exceptions import EconEnvError
from ._common import MagicParser, resolve_python_name, shell_of, split_line, strip_quotes


def _build_parser() -> MagicParser:
    parser = MagicParser(prog="%econ", add_help=False, description="Manage EconEnv engines.")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", add_help=False, help="Engine table.")
    sub.add_parser("engines", add_help=False, help="Detailed engine information.")
    sub.add_parser("versions", add_help=False, help="Version of each engine.")
    sub.add_parser("capabilities", add_help=False, help="Capability matrix.")
    sub.add_parser("models", add_help=False, help="Estimator x engine matrix.")

    doctor = sub.add_parser("doctor", add_help=False, help="Diagnostics.")
    doctor.add_argument("engine", nargs="?", default=None)
    doctor.add_argument("--deep", action="store_true", help="Also start each engine.")
    doctor.add_argument("--json", action="store_true", help="Return the report as a dict.")

    for name in ("start", "restart"):
        node = sub.add_parser(name, add_help=False)
        node.add_argument("engine")
    stop = sub.add_parser("stop", add_help=False)
    stop.add_argument("engine", nargs="?", default=None)
    reset = sub.add_parser("reset", add_help=False)
    reset.add_argument("engine", nargs="?", default=None)

    config = sub.add_parser("config", add_help=False, help="Show or set configuration.")
    config.add_argument("key", nargs="?", default=None)
    config.add_argument("value", nargs="?", default=None)
    config.add_argument("--sources", action="store_true", help="Show which layers are active.")

    snapshot = sub.add_parser("snapshot", add_help=False, help="Reproducibility snapshot.")
    snapshot.add_argument("path", nargs="?", default=None)
    snapshot.add_argument("--deep", action="store_true", help="Start engines to read versions.")

    push = sub.add_parser("push", add_help=False, help="Send a Python object to an engine.")
    push.add_argument("engine")
    push.add_argument("name")
    push.add_argument("--as", dest="target", default=None)

    pull = sub.add_parser("pull", add_help=False, help="Fetch an object from an engine.")
    pull.add_argument("engine")
    pull.add_argument("name", nargs="?", default=None)
    pull.add_argument("--as", dest="target", default=None)

    move = sub.add_parser("move", add_help=False, help="Move data between two engines.")
    move.add_argument("source")
    move.add_argument("target")
    move.add_argument("name")

    export = sub.add_parser("export", add_help=False, help="Write results to publication formats.")
    export.add_argument(
        "name", nargs="?", default=None, help="Python variable holding the result to export."
    )
    export.add_argument(
        "path", nargs="?", default=None, help="Destination file or stem, e.g. paper/table1"
    )
    export.add_argument(
        "--formats", default=None, help="Comma-separated: tex,docx,xlsx,csv,html,md,rtf"
    )
    export.add_argument("--style", default="journal", choices=["journal", "full"])
    export.add_argument("--caption", default=None)
    export.add_argument("--label", default=None)

    eviews = sub.add_parser(
        "eviews", add_help=False, help="Look up EViews commands by task or keyword."
    )
    eviews.add_argument("term", nargs="*", default=None)

    matlab = sub.add_parser(
        "matlab", add_help=False, help="Look up MATLAB commands, or MATLAB help topics."
    )
    matlab.add_argument("term", nargs="*", default=None)

    ols = sub.add_parser("ols", add_help=False, help="Run one OLS across engines.")
    ols.add_argument("formula", nargs="+")
    ols.add_argument("--data", required=True, help="Name of the DataFrame in Python.")
    ols.add_argument("--engines", default=None, help="Comma-separated engine list.")
    ols.add_argument("--vcov", default=None)
    ols.add_argument("--no-constant", action="store_true")

    return parser


@magics_class
class EconMagics(Magics):
    """EconEnv's management magic."""

    @needs_local_scope
    @line_magic("econ")
    def econ(self, line: str = "", local_ns: Optional[dict] = None) -> Any:
        local_ns = local_ns or {}
        tokens = split_line(line)
        if not tokens or tokens[0] in {"-h", "--help", "help"}:
            print(_build_parser().format_help())
            print(_HELP_EXTRA)
            return None

        args = _build_parser().parse_args(tokens)
        handler = getattr(self, f"_cmd_{args.command}", None)
        if handler is None:
            raise EconEnvError(f"Unknown %econ command {args.command!r}.")
        return handler(args, local_ns)

    # -- inspection -------------------------------------------------------- #
    def _cmd_status(self, args, local_ns) -> Any:
        print(f"EconEnv {__version__}")
        return services.status_frame()

    def _cmd_engines(self, args, local_ns) -> Any:
        from . import registration_lines

        for info in services.engines():
            print(f"{info['display_name']} ({info['name']})")
            print(f"  state        {info['state']}")
            print(f"  version      {info['version'] or '-'}")
            if info["edition"]:
                print(f"  edition      {info['edition']}")
            if info["backend"]:
                print(f"  backend      {info['backend']}")
            if info["home"]:
                print(f"  location     {info['home']}")
            print(f"  capabilities {', '.join(info['capabilities'])}")
            if info["error"]:
                print(f"  note         {info['error']}")
            print()
        lines = registration_lines()
        if lines:
            print("Magic ownership")
            for entry in lines:
                print(f"  {entry}")
        return None

    def _cmd_export(self, args, local_ns) -> Any:
        """Write a result to disk without leaving the notebook.

        The point of doing this from a cell rather than by hand is that the
        numbers in the file come from the object that produced them, so a table
        cannot drift from the estimation that made it.
        """
        from ..export import export as _export

        if not args.name or (args.name in ("help", "formats") and not args.path):
            print(_EXPORT_HELP)
            return None

        key = strip_quotes(args.name)
        obj = resolve_python_name(key, local_ns, shell_of(self))

        formats = [f.strip() for f in args.formats.split(",")] if args.formats else None
        result = _export(
            obj,
            strip_quotes(args.path),
            formats=formats,
            style=args.style,
            caption=args.caption,
            label=args.label,
        )
        print(result)
        return None

    def _cmd_matlab(self, args, local_ns) -> Any:
        """MATLAB commands for research work, searchable from the cell.

        MATLAB is not short of documentation; it is short of a way to ask "is
        there a function for this, and is it in a toolbox I actually have"
        without leaving the notebook. Every entry names its toolbox, and the
        tick marks the ones resolved against a live MATLAB.
        """
        from ..engines import matlab_commands as catalogue

        term = " ".join(getattr(args, "term", None) or []).strip()
        head = term.split()[0].lower() if term else ""

        if head in ("status", "doctor"):
            from .. import services

            return services.doctor("matlab") if head == "doctor" else services.status()

        if head == "colab":
            print(_COLAB_HELP)
            return None

        if head == "export":
            print(_MATLAB_EXPORT_HELP)
            return None

        if head in ("help", "magic"):
            print(_MATLAB_MAGIC_HELP)
            return None

        if not term:
            verified = sum(1 for c in catalogue.COMMANDS if c.verified)
            print(
                f"{len(catalogue.COMMANDS)} MATLAB commands for research "
                f"({verified} resolved against a live MATLAB).\n"
            )
            for name, description in catalogue.categories().items():
                count = len(catalogue.by_category(name))
                print(f"  {name:<13} {description} ({count})")
            print("\n  colab         Running MATLAB through Colab's local runtime")
            print("  export        Saving MATLAB figures and tables for publication")
            print("  status        Which MATLAB EconEnv will start")
            print("  doctor        Diagnose MATLAB setup")
            print("\nExamples:")
            print("  %econ matlab timeseries          unit roots, ARIMA, VAR")
            print("  %econ matlab find cointegration  search everything")
            print("  %econ matlab find wavelet")
            print("\nToolboxes these commands need:")
            for toolbox, count in catalogue.toolboxes().items():
                print(f"  {count:>3}  {toolbox}")
            return None

        if head in ("find", "search"):
            term = " ".join(term.split()[1:])

        matches = catalogue.find(term)
        if not matches:
            print(f"Nothing matches {term!r}. Try `%econ matlab` for the categories,")
            print("or ask MATLAB itself:  %%matlab\\n  lookfor " + term.split()[0])
            return None

        heading = (
            catalogue.categories().get(term.lower())
            or f"{len(matches)} command(s) matching {term!r}"
        )
        print(f"{heading}\n")
        for command in matches:
            print(command)
            print()
        return None

    def _cmd_eviews(self, args, local_ns) -> Any:
        """Find the EViews command for something you would normally click.

        The reason this is a magic and not only a documentation page: the
        question "what do I type for a Johansen test" is asked *while writing
        the cell*, and an answer that needs a browser is an answer too late.
        """
        from ..engines import eviews_commands as catalogue

        term = " ".join(getattr(args, "term", None) or []).strip()

        if not term:
            print("EViews commands by task. Use `%econ eviews <task>` or a keyword.\n")
            for name, description in catalogue.categories().items():
                print(f"  {name:<10} {description}")
            print("\nExamples:")
            print("  %econ eviews graph              every kind of plot")
            print("  %econ eviews estimate           estimating equations")
            print("  %econ eviews find cointegration search everything")
            return None

        if term.split()[0] in {"find", "search"}:
            term = " ".join(term.split()[1:])

        matches = catalogue.find(term)
        if not matches:
            print(f"Nothing matches {term!r}. Try `%econ eviews` for the list of tasks,")
            print("or ask EViews itself:  %%eviews\n  help <command>")
            return None

        heading = (
            catalogue.categories().get(term.lower())
            or f"{len(matches)} command(s) matching {term!r}"
        )
        print(f"{heading}\n")
        for command in matches:
            print(command)
            print()
        return None

    def _cmd_versions(self, args, local_ns) -> Any:
        return services.versions()

    def _cmd_capabilities(self, args, local_ns) -> Any:
        return services.capabilities()

    def _cmd_models(self, args, local_ns) -> Any:
        return services.model_matrix()

    # -- lifecycle --------------------------------------------------------- #
    def _cmd_doctor(self, args, local_ns) -> Any:
        report = services.doctor(args.engine, deep=args.deep)
        return report.to_dict() if args.json else report

    def _cmd_start(self, args, local_ns) -> Any:
        info = services.start(args.engine)
        print(f"{info['display_name']} started — version {info['version'] or 'unknown'}")
        return None

    def _cmd_stop(self, args, local_ns) -> Any:
        stopped = services.stop(args.engine)
        print(f"stopped: {', '.join(stopped) if stopped else 'nothing was running'}")
        return None

    def _cmd_restart(self, args, local_ns) -> Any:
        info = services.restart(args.engine)
        print(f"{info['display_name']} restarted — version {info['version'] or 'unknown'}")
        return None

    def _cmd_reset(self, args, local_ns) -> Any:
        services.reset(args.engine)
        print(f"reset: {args.engine or 'all engines and runtime config'}")
        return None

    # -- config ------------------------------------------------------------ #
    def _cmd_config(self, args, local_ns) -> Any:
        if args.sources:
            return services.config_sources()
        if args.key is None:
            return services.config_show()
        if args.value is None:
            from .. import config as _config

            section, key = args.key.split(".", 1)
            return _config.get_option(section, key)
        stored = services.config_set(args.key, strip_quotes(args.value))
        print(f"{args.key} = {stored}")
        return None

    # -- reproducibility --------------------------------------------------- #
    def _cmd_snapshot(self, args, local_ns) -> Any:
        payload = services.snapshot(deep=args.deep)
        if args.path:
            from .. import transfer

            path = transfer.save_snapshot(strip_quotes(args.path), deep=args.deep)
            print(f"snapshot written to {path}")
            return None
        print(
            json.dumps(
                {"econenv_version": payload["econenv_version"], "engines": list(payload["engines"])}
            )
        )
        return payload

    # -- data -------------------------------------------------------------- #
    def _cmd_push(self, args, local_ns) -> Any:
        from .. import transfer

        obj = resolve_python_name(args.name, local_ns, shell_of(self))
        transfer.push(args.engine, args.target or args.name, obj)
        print(f"{args.name} -> {args.engine}:{args.target or args.name}")
        return None

    def _cmd_pull(self, args, local_ns) -> Any:
        from .. import transfer

        obj = transfer.pull(args.engine, args.name)
        if args.target:
            shell_of(self).push({args.target: obj})
            print(f"{args.engine}:{args.name} -> {args.target}")
            return None
        return obj

    def _cmd_move(self, args, local_ns) -> Any:
        from .. import transfer

        frame = transfer.move(args.source, args.target, args.name)
        print(f"{args.source}:{args.name} -> {args.target}:{args.name} ({len(frame)} rows)")
        return frame

    # -- models ------------------------------------------------------------ #
    def _cmd_ols(self, args, local_ns) -> Any:
        from ..models import compare_ols

        data = resolve_python_name(args.data, local_ns, shell_of(self))
        engines: Optional[List[str]] = (
            [e.strip() for e in args.engines.split(",")] if args.engines else None
        )
        return compare_ols(
            data,
            " ".join(args.formula),
            engines=engines,
            constant=not args.no_constant,
            vcov=args.vcov,
        )


_HELP_EXTRA = """\
Examples
  %econ status
  %econ doctor eviews --deep
  %econ config stata.edition mp
  %econ config r.home "C:/Program Files/R/R-4.5.2"
  %econ push r df --as mydata
  %econ move stata r auto
  %econ ols y ~ x1 + x2 --data df --engines python,r,stata
  %econ snapshot ./environment.json
"""

#: Colab's local runtime puts the notebook interface in the browser and the
#: kernel on your own machine, which is the only arrangement in which MATLAB,
#: EViews and a local Stata can be driven from Colab at all.
_COLAB_HELP = """Running MATLAB from Google Colab, through a local runtime
===========================================================

Colab normally runs on a Linux VM at Google, where your MATLAB is not
installed and your licence does not apply. The local runtime keeps the Colab
interface in your browser but runs the kernel on YOUR computer, so MATLAB,
EViews and Stata all work exactly as they do in a local notebook.

    Colab UI (browser)  ->  local Jupyter server  ->  EconEnv  ->  MATLAB

1. Activate the environment that has EconEnv        [Windows CMD/PowerShell]

     <your-env>\\Scripts\\activate
     python --version

2. Start Jupyter so Colab is allowed to talk to it  [Windows CMD/PowerShell]

     jupyter notebook \\
       --ServerApp.allow_origin="https://colab.research.google.com" \\
       --ServerApp.allow_credentials=True

   Jupyter picks a free port itself. If you need a fixed one, add
   --ServerApp.port=8888; if that port is busy Jupyter will say so and you can
   choose another.

3. Copy the address it prints, token and all:

     http://localhost:<PORT>/?token=<TOKEN>

4. In Colab:  Connect -> Connect to local runtime -> paste -> Connect

5. Check the kernel really is yours                 [Python cell]

     import sys; print(sys.executable)

   It must show your own environment, not /usr/bin/python3.

6. Then everything is normal                        [Python cell]

     %load_ext econenv
     %econ status

     %%matlab
     version

SECURITY
  The local runtime executes notebook code on your computer, with your files
  and your installed software. Connect only notebooks you trust, and never
  share the token — it is the credential to your kernel."""


#: Publication-quality output from MATLAB, which is `exportgraphics` underneath
#: rather than anything EconEnv invents.
_MATLAB_EXPORT_HELP = """Saving MATLAB results for publication
=====================================

FIGURES

  Capture format is a setting, and it must be chosen BEFORE the cell runs:
  a bitmap cannot be turned into a vector afterwards.

     %econ config matlab.graphics pdf     # png | svg | pdf | off
     %econ config matlab.dpi 300          # for png

  pdf and svg are vector — sharp at any size, which is what most economics
  journals ask for. Underneath this is MATLAB's own exportgraphics, so the
  figure is rendered by MATLAB rather than screenshotted.

  Figures captured by a cell are also written to disk from Python:

     res = %matlab --result plot(x, y)
     econenv.export_figures(res, "paper/figures")

  Or from MATLAB directly, when you want full control:

     %%matlab
     exportgraphics(gcf, 'fig1.pdf', 'ContentType', 'vector');
     exportgraphics(gcf, 'fig1.png', 'Resolution', 600);

TABLES

  Bring the table into Python, then export it like any other result:

     %%matlab -o T
     T = mdl.Coefficients;

     econenv.export(T, "paper/table1", formats=["tex", "docx", "xlsx"])

  or from a cell:

     %econ export T paper/table1 --formats tex,docx --caption "Table 1"

  Formats: tex, docx, xlsx, csv, html, md, rtf.  docx and xlsx need
  `pip install "econenv[export]"`; the rest need nothing.

WHAT NOT TO EXPECT

  EconEnv will not re-wrap a raster figure as a "vector" PDF, and will not
  compute a statistic MATLAB did not report. A blank cell in a table is a
  number the engine did not give."""


#: The magic's own help, printed rather than requiring `%%matlab?`.
_MATLAB_MAGIC_HELP = """%matlab and %%matlab
=====================

  %matlab disp(version)          one statement

  %%matlab                       a block
  x = 1:10;
  disp(mean(x))

SENDING PYTHON VALUES IN

  %%matlab -i x -i df            repeat -i for several

  int/float/NumPy scalar -> double      list/tuple/1-D array -> double column
  bool                   -> logical     2-D array            -> double, shape kept
  complex                -> complex     Series               -> one-column table
  str                    -> char        DataFrame            -> table

  %econ config matlab.vectors row       send 1-D as a row instead

BRINGING RESULTS BACK

  %%matlab -o y -o A -o T

  numeric scalar -> float (int for integer classes)   vector    -> 1-D ndarray
  logical scalar -> bool                              matrix    -> 2-D ndarray
  char/string    -> str                               table     -> DataFrame
  complex scalar -> complex                           cellstr   -> list of str

  A struct or a mixed cell array raises DataTransferError naming the class;
  convert it in MATLAB first (struct2table, table) and pull that.

FLAGS

  -q            do not display the output
  --no-graphs   do not capture figures from this cell
  --result      return the ExecutionResult (.text, .figures) instead of
                displaying it

The first MATLAB cell of a session takes about a minute while MATLAB starts.
`%econ doctor matlab` explains anything that will not start."""


#: `%econ export` with nothing to export: the formats, what can be exported and
#: which optional dependency each needs. Written out rather than derived so it
#: can say *why* a format is there.
_EXPORT_HELP = r"""Exporting results for publication
=================================

  %econ export <name> <path> [--formats ...] [--style journal|full]
                             [--caption "..."] [--label tab:x]

  <name> is a Python variable: a ComparisonResult, a ModelResult, a
  DataFrame, a Figure, or a list mixing them.

TABLE FORMATS

  tex     LaTeX with booktabs rules, ready to \input        no extra install
  csv     plain values                                      no extra install
  html    self-contained, styled like a journal table       no extra install
  rtf     for submission systems that still want it         no extra install
  docx    a real editable Word table, not a picture         econenv[export]
  xlsx    one sheet per table, full precision               econenv[export]
  md      markdown                                          econenv[export]

     pip install "econenv[export]"

  Give a path with a suffix and that format is used; give a stem and you get
  the journal bundle — tex, docx and xlsx:

     %econ export cmp paper/table1            three files
     %econ export cmp paper/table1.tex        just LaTeX

FIGURE FORMATS

  png, svg, pdf, eps. The extension follows the CONTENT, not the filename:
  naming a PNG .pdf makes a file nothing can open, so EconEnv corrects it and
  says so. Ask the engine for vector output before running the cell —

     %econ config matlab.graphics pdf
     %econ config r.graphics pdf
     %econ config eviews.graphics svg

  because a bitmap cannot be converted into a vector afterwards.

TWO LAYOUTS

  --style journal   what a paper prints: coefficient with stars, standard
                    error beneath in parentheses, N and fit statistics at the
                    foot. The default.
  --style full      one row per term per engine with coefficient, standard
                    error, statistic, p-value and confidence interval as
                    separate columns. For checking, not for a paper.

WHAT IT WILL NOT DO

  Invent a statistic the engine did not report, fake vector output from a
  raster figure, or round twice. Blank cells are missing numbers, not zeros.

  %econ matlab export   the same thing from the MATLAB side"""
