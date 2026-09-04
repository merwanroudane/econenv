"""``econenv`` command line (brief §34).

Every subcommand calls :mod:`econenv.services` — the same functions ``%econ``
uses — so the CLI and the magic cannot disagree about what "status" means.

Exit codes: ``0`` success, ``1`` a diagnostic error was found, ``2`` bad usage.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from typing import List, Optional

from . import services
from ._logging import configure, level_from_env
from ._version import __version__
from .exceptions import EconEnvError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="econenv",
        description="EconEnv — Python, R, Stata and EViews in one Jupyter session.",
        epilog="Docs: https://github.com/merwanroudane/econenv",
    )
    parser.add_argument("--version", action="version", version=f"econenv {__version__}")
    parser.add_argument("--json", action="store_true", help="Machine-readable output.")
    parser.add_argument(
        "--log", default=None, metavar="LEVEL", help="DEBUG, INFO, WARNING or ERROR."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Which engines are installed, configured and running.")
    sub.add_parser("engines", help="Detailed information about each engine.")
    sub.add_parser("versions", help="Version of EconEnv and of each engine.")
    sub.add_parser("capabilities", help="Capability matrix.")
    sub.add_parser("models", help="Estimator x engine matrix.")
    sub.add_parser("info", help="Everything at once, as a reproducibility snapshot.")

    doctor = sub.add_parser("doctor", help="Diagnose the installation.")
    doctor.add_argument("engine", nargs="?", default=None, help="r, stata or eviews.")
    doctor.add_argument(
        "--deep",
        action="store_true",
        help="Also start each engine (slower; launches Stata/EViews).",
    )

    eviews = sub.add_parser(
        "eviews", help="Look up EViews commands by task or keyword, for GUI users."
    )
    eviews.add_argument("term", nargs="*", help="A task name, or any keyword to search for.")

    config = sub.add_parser("config", help="Show or set configuration.")
    config.add_argument("key", nargs="?", default=None, help="e.g. r.home")
    config.add_argument("value", nargs="?", default=None)
    config.add_argument("--sources", action="store_true", help="Which layers are contributing.")

    snapshot = sub.add_parser("snapshot", help="Write a reproducibility snapshot.")
    snapshot.add_argument("path", nargs="?", default=None, help="Output JSON file.")
    snapshot.add_argument("--deep", action="store_true", help="Start engines to read versions.")

    return parser


def _make_stdout_tolerant() -> None:
    """Stop a legacy console encoding from turning output into a traceback.

    The default Windows console is cp1252, which cannot encode the arrows and
    tick marks the diagnostics use. Reconfiguring to UTF-8 with ``replace``
    means a narrow console degrades the glyphs instead of crashing the command.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        with contextlib.suppress(OSError, ValueError):  # redirected streams
            reconfigure(encoding="utf-8", errors="replace")


def main(argv: Optional[List[str]] = None) -> int:
    _make_stdout_tolerant()
    parser = build_parser()
    args = parser.parse_args(argv)
    configure(args.log or level_from_env())

    try:
        return _dispatch(args)
    except EconEnvError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:  # pragma: no cover
        return 130


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "status":
        payload = services.status()
        if args.json:
            print(json.dumps(payload, indent=2, default=str))
            return 0
        print(f"EconEnv {payload['econenv_version']}\n")
        print(services.status_frame().to_string())
        if payload["plugin_errors"]:
            print("\nThird-party engine plugins that failed to load:")
            for name, error in payload["plugin_errors"].items():
                print(f"  {name}: {error}")
        return 0

    if args.command == "eviews":
        from .engines import eviews_commands as catalogue

        term = " ".join(args.term or []).strip()
        if term.split()[:1] in (["find"], ["search"]):
            term = " ".join(term.split()[1:])

        if not term:
            print("EViews commands by task. Use: econenv eviews <task-or-keyword>\n")
            for name, description in catalogue.categories().items():
                print(f"  {name:<10} {description}")
            return 0

        matches = catalogue.find(term)
        if not matches:
            print(f"Nothing matches {term!r}. Run `econenv eviews` for the list of tasks.")
            return 1
        print(catalogue.categories().get(term.lower()) or f"{len(matches)} matching {term!r}")
        print()
        for command in matches:
            print(command)
            print()
        return 0

    if args.command == "engines":
        details = services.engines()
        if args.json:
            print(json.dumps(details, indent=2, default=str))
            return 0
        for info in details:
            print(f"{info['display_name']} ({info['name']})")
            print(f"  state        {info['state']}")
            print(f"  version      {info['version'] or '-'}")
            for field in ("edition", "backend", "home", "executable"):
                if info.get(field):
                    print(f"  {field:<12} {info[field]}")
            print(f"  capabilities {', '.join(info['capabilities'])}")
            if info["error"]:
                print(f"  note         {info['error']}")
            for key, value in info["detail"].items():
                print(f"  {key:<12} {value}")
            print()
        return 0

    if args.command == "versions":
        found = services.versions()
        if args.json:
            print(json.dumps(found, indent=2))
            return 0
        for name, version in found.items():
            print(f"{name:<10} {version or '-'}")
        return 0

    if args.command == "capabilities":
        table = services.capabilities()
        print(table.to_json(orient="index", indent=2) if args.json else table.to_string())
        return 0

    if args.command == "models":
        table = services.model_matrix()
        print(table.to_json(orient="index", indent=2) if args.json else table.to_string())
        return 0

    if args.command == "info":
        payload = services.snapshot(include_packages=False)
        print(json.dumps(payload, indent=2, default=str))
        return 0

    if args.command == "doctor":
        report = services.doctor(args.engine, deep=args.deep)
        if args.json:
            print(json.dumps(report.to_dict(), indent=2))
        else:
            print(report)
        return 0 if report.ok else 1

    if args.command == "config":
        if args.sources:
            print(json.dumps(services.config_sources(), indent=2))
            return 0
        if args.key is None:
            table = services.config_show()
            print(table.to_json(orient="index", indent=2) if args.json else table.to_string())
            return 0
        if args.value is None:
            from . import config as _config

            section, key = args.key.split(".", 1)
            print(_config.get_option(section, key))
            return 0
        print(f"{args.key} = {services.config_set(args.key, args.value)}")
        print("Note: this sets the option for this process only.")
        print(f"Persist it by editing {_config_path()}.")
        return 0

    if args.command == "snapshot":
        from . import transfer

        if args.path:
            path = transfer.save_snapshot(args.path, deep=args.deep)
            print(f"snapshot written to {path}")
        else:
            print(json.dumps(transfer.snapshot(deep=args.deep), indent=2, default=str))
        return 0

    return 2


def _config_path() -> str:
    from . import config as _config

    return str(_config.config_path())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
