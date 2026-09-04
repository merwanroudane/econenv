"""``econenv doctor`` — diagnostics with actionable advice (brief §14).

Every check returns PASS, WARN or ERROR **and a fix**. A diagnostic that says
"R not found" without saying what to do about it is only half a diagnostic.

Checks never start an engine unless asked to (``deep=True``), so ``doctor`` is
safe to run on a machine where launching EViews or Stata would be slow or would
consume a licence seat.
"""

from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from . import config as _config
from . import discovery
from ._version import __version__


class Status(str, Enum):
    PASS = "PASS"
    WARN = "WARNING"
    ERROR = "ERROR"
    SKIP = "SKIP"


def _symbols() -> Dict[Status, str]:
    """Tick marks where the console can render them, ASCII where it cannot.

    The default Windows console is cp1252 and raises ``UnicodeEncodeError`` on
    U+2714, which would turn a diagnostic run into a traceback — the one place
    that must never happen.
    """
    encoding = getattr(sys.stdout, "encoding", None) or "ascii"
    try:
        "✔✘".encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return {Status.PASS: "[ok]", Status.WARN: "[!!]", Status.ERROR: "[XX]", Status.SKIP: "[--]"}
    return {Status.PASS: "✔", Status.WARN: "!", Status.ERROR: "✘", Status.SKIP: "-"}


@dataclass
class Check:
    """One diagnostic."""

    name: str
    status: Status
    detail: str = ""
    fix: str = ""
    group: str = "general"

    def to_dict(self) -> Dict[str, str]:
        return {
            "name": self.name,
            "status": self.status.value,
            "detail": self.detail,
            "fix": self.fix,
            "group": self.group,
        }

    def __str__(self) -> str:
        line = f"{_symbols()[self.status]} {self.status.value:<7} {self.name}"
        if self.detail:
            line += f": {self.detail}"
        if self.fix and self.status in (Status.WARN, Status.ERROR):
            line += f"\n              → {self.fix}"
        return line


@dataclass
class Report:
    """The full diagnostic run."""

    checks: List[Check] = field(default_factory=list)
    econenv_version: str = __version__

    def add(self, *checks: Check) -> None:
        self.checks.extend(checks)

    def by_group(self) -> Dict[str, List[Check]]:
        out: Dict[str, List[Check]] = {}
        for check in self.checks:
            out.setdefault(check.group, []).append(check)
        return out

    @property
    def errors(self) -> List[Check]:
        return [c for c in self.checks if c.status is Status.ERROR]

    @property
    def warnings(self) -> List[Check]:
        return [c for c in self.checks if c.status is Status.WARN]

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> Dict[str, Any]:
        return {
            "econenv_version": self.econenv_version,
            "ok": self.ok,
            "counts": {
                status.value: sum(1 for c in self.checks if c.status is status) for status in Status
            },
            "checks": [c.to_dict() for c in self.checks],
        }

    def __str__(self) -> str:
        lines = [f"EconEnv {self.econenv_version} — diagnostics", ""]
        for group, checks in self.by_group().items():
            lines.append(group.upper())
            lines += [f"  {c!s}" for c in checks]
            lines.append("")
        counts = self.to_dict()["counts"]
        lines.append(
            f"{counts['PASS']} passed · {counts['WARNING']} warnings · {counts['ERROR']} errors"
        )
        return "\n".join(lines)

    def _repr_mimebundle_(self, include=None, exclude=None):
        return {"text/plain": str(self), "text/html": self._html()}

    def _html(self) -> str:
        import html as _html

        colours = {
            Status.PASS: "#2e7d32",
            Status.WARN: "#ef6c00",
            Status.ERROR: "#c62828",
            Status.SKIP: "#777",
        }
        pieces = [
            "<div style='font-family:system-ui,sans-serif;font-size:13px'>",
            f"<div style='font-weight:600'>EconEnv {_html.escape(self.econenv_version)} — diagnostics</div>",
        ]
        for group, checks in self.by_group().items():
            pieces.append(
                f"<div style='margin-top:8px;font-weight:600;text-transform:uppercase;"
                f"font-size:11px;color:#555'>{_html.escape(group)}</div>"
            )
            pieces.append("<table style='border-collapse:collapse'>")
            for check in checks:
                fix = (
                    f"<div style='color:#555;font-size:12px'>→ {_html.escape(check.fix)}</div>"
                    if check.fix and check.status in (Status.WARN, Status.ERROR)
                    else ""
                )
                pieces.append(
                    "<tr>"
                    f"<td style='padding:1px 8px;color:{colours[check.status]};font-weight:600'>"
                    f"{check.status.value}</td>"
                    f"<td style='padding:1px 8px'>{_html.escape(check.name)}</td>"
                    f"<td style='padding:1px 8px'>{_html.escape(check.detail)}{fix}</td>"
                    "</tr>"
                )
            pieces.append("</table>")
        pieces.append("</div>")
        return "".join(pieces)


# --------------------------------------------------------------------------- #
# checks
# --------------------------------------------------------------------------- #
def check_host() -> List[Check]:
    checks = [
        Check(
            "Python",
            Status.PASS if sys.version_info >= (3, 9) else Status.ERROR,
            f"{platform.python_version()} at {sys.executable}",
            "EconEnv needs Python 3.9 or newer.",
            group="host",
        ),
        Check("Operating system", Status.PASS, platform.platform(), group="host"),
        Check("Architecture", Status.PASS, platform.machine(), group="host"),
    ]

    for module, required, note in [
        ("IPython", True, "magics need IPython"),
        ("pandas", True, "the interchange format"),
        ("numpy", True, "numerics"),
        ("jupyterlab", False, "for the notebook UI"),
        ("pyarrow", False, "enables the fast feather transfer to R"),
    ]:
        version = _module_version(module)
        if version:
            checks.append(Check(module, Status.PASS, version, group="host"))
        else:
            checks.append(
                Check(
                    module,
                    Status.ERROR if required else Status.WARN,
                    "not installed",
                    f"pip install {module.lower()} — {note}",
                    group="host",
                )
            )

    temp = tempfile.gettempdir()
    writable = os.access(temp, os.W_OK)
    checks.append(
        Check(
            "Temporary directory",
            Status.PASS if writable else Status.ERROR,
            temp,
            "R and EViews transfers need a writable temp directory. Set TMPDIR.",
            group="host",
        )
    )
    return checks


def check_config() -> List[Check]:
    sources = _config.sources()
    checks = [
        Check(
            "Config file",
            Status.PASS if sources["file"] else Status.SKIP,
            sources["file"] or f"none (would be {_config.config_path()})",
            group="config",
        )
    ]
    if sources["env"]:
        checks.append(
            Check("Environment overrides", Status.PASS, ", ".join(sources["env"]), group="config")
        )
    if sources["runtime"]:
        checks.append(
            Check(
                "Runtime overrides",
                Status.PASS,
                ", ".join(f"{s}.{k}" for s, keys in sources["runtime"].items() for k in keys),
                group="config",
            )
        )
    return checks


def check_r(deep: bool = False) -> List[Check]:
    checks: List[Check] = []
    installs = discovery.find_r(_config.get_option("r", "home"))
    if not installs:
        return [
            Check(
                "R installation",
                Status.WARN,
                "not found",
                'Install R, then set it with `%econ config r.home "C:/Program Files/R/R-4.5.2"` '
                "or export R_HOME.",
                group="r",
            )
        ]

    best = installs[0]
    checks.append(
        Check("R installation", Status.PASS, f"{best.home} (R {best.version or '?'})", group="r")
    )
    if len(installs) > 1:
        checks.append(
            Check(
                "Multiple R versions",
                Status.WARN,
                ", ".join(f"{i.version or '?'} at {i.home}" for i in installs),
                "EconEnv picks the newest. Pin one with `%econ config r.home ...`.",
                group="r",
            )
        )

    checks.append(
        Check(
            "R_HOME",
            Status.PASS if os.environ.get("R_HOME") else Status.WARN,
            os.environ.get("R_HOME") or "not set",
            "Not fatal — EconEnv sets it for the child process — but other tools may want it.",
            group="r",
        )
    )
    checks.append(
        Check(
            "R on PATH",
            Status.PASS if shutil.which("R") or shutil.which("Rscript") else Status.WARN,
            shutil.which("R") or shutil.which("Rscript") or "not on PATH",
            "Optional: EconEnv calls the executable by full path.",
            group="r",
        )
    )

    from .engines.r_engine import REngine

    console = REngine._console_executable(best.home)
    checks.append(
        Check(
            "R console front-end",
            Status.PASS if console else Status.ERROR,
            str(console) if console else "Rterm/R not found inside the installation",
            "The subprocess backend needs Rterm.exe (Windows) or bin/R (POSIX).",
            group="r",
        )
    )

    rpy2 = importlib.util.find_spec("rpy2") is not None
    checks.append(
        Check(
            "rpy2",
            Status.PASS if rpy2 else Status.SKIP,
            "importable — the in-process backend and the official %R magics are available"
            if rpy2
            else "not installed; EconEnv uses its subprocess backend instead",
            "rpy2 publishes no Windows wheels; the subprocess backend is the supported "
            "route on Windows and needs nothing extra.",
            group="r",
        )
    )

    if deep:
        checks.append(_deep_engine_check("r"))
    return checks


def check_stata(deep: bool = False) -> List[Check]:
    checks: List[Check] = []
    installs = discovery.find_stata(_config.get_option("stata", "home"))
    if not installs:
        return [
            Check(
                "Stata installation",
                Status.WARN,
                "not found",
                'Install Stata 17+, then `%econ config stata.home "C:/Program Files/Stata19"`.',
                group="stata",
            )
        ]

    with_pystata = [i for i in installs if i.detail.get("pystata")]
    for install in installs:
        has_pystata = bool(install.detail.get("pystata"))
        checks.append(
            Check(
                f"Stata {install.version or '?'}",
                Status.PASS if has_pystata else Status.WARN,
                f"{install.home} · edition {install.edition or '?'}"
                + ("" if has_pystata else " · no utilities/pystata"),
                "PyStata ships with Stata 17 and later. Older releases cannot be driven "
                "from Python.",
                group="stata",
            )
        )

    if not with_pystata:
        checks.append(
            Check(
                "PyStata",
                Status.ERROR,
                "no installation contains utilities/pystata",
                "Upgrade to Stata 17+ or point EconEnv at the right installation.",
                group="stata",
            )
        )
    else:
        checks.append(
            Check(
                "PyStata",
                Status.PASS,
                with_pystata[0].detail["pystata"],
                group="stata",
            )
        )

    checks.append(
        Check(
            "stata_setup",
            Status.PASS if importlib.util.find_spec("stata_setup") else Status.SKIP,
            "installed" if importlib.util.find_spec("stata_setup") else "not installed (optional)",
            "EconEnv puts utilities/ on sys.path itself, so stata_setup is not required.",
            group="stata",
        )
    )

    configured_edition = _config.get_option("stata", "edition")
    detected = with_pystata[0].edition if with_pystata else None
    if configured_edition and detected and configured_edition.lower() != detected:
        checks.append(
            Check(
                "Stata edition",
                Status.WARN,
                f"configured {configured_edition}, executable suggests {detected}",
                "`pystata.config.init` fails if the edition is not the licensed one.",
                group="stata",
            )
        )

    if deep:
        checks.append(_deep_engine_check("stata"))
    return checks


def check_eviews(deep: bool = False) -> List[Check]:
    if platform.system() != "Windows":
        return [
            Check(
                "EViews",
                Status.SKIP,
                f"COM automation is Windows-only; this is {platform.system()}",
                "EconEnv installs and works fine without it — the other engines are unaffected.",
                group="eviews",
            )
        ]

    checks: List[Check] = []
    comtypes = importlib.util.find_spec("comtypes") is not None
    installs = discovery.find_eviews()

    # Not an ERROR. `doctor` exits 1 on any error, and a perfectly good
    # Python + R + Stata installation must not fail a CI gate because the user
    # never asked for EViews support. ERROR is reserved for "you configured
    # this and it is broken".
    if comtypes:
        comtypes_status, comtypes_detail = Status.PASS, _module_version("comtypes") or "installed"
    elif installs:
        comtypes_status = Status.WARN
        comtypes_detail = "not installed, but EViews is present on this machine"
    else:
        comtypes_status, comtypes_detail = Status.SKIP, "not installed (no EViews found either)"
    checks.append(
        Check(
            "comtypes",
            comtypes_status,
            comtypes_detail,
            "pip install 'econenv[eviews]' to enable the EViews engine.",
            group="eviews",
        )
    )

    if installs:
        checks.append(
            Check(
                "EViews installation",
                Status.PASS,
                ", ".join(f"{i.version or '?'} at {i.home}" for i in installs),
                group="eviews",
            )
        )
    else:
        checks.append(
            Check(
                "EViews installation",
                Status.WARN,
                "not found in Program Files",
                "Install EViews, or ignore this if you do not use it.",
                group="eviews",
            )
        )

    progids = discovery.eviews_progids()
    if progids:
        checks.append(Check("COM ProgID", Status.PASS, ", ".join(progids), group="eviews"))
        if "EViews.Manager" in progids and len(installs) > 1:
            checks.append(
                Check(
                    "COM version binding",
                    Status.WARN,
                    "several EViews versions are installed and the generic "
                    "EViews.Manager ProgID binds to whichever registered last",
                    "Pin one: `%econ config eviews.progid EViews.Manager.14`. "
                    "`%econ status` always shows the version actually connected.",
                    group="eviews",
                )
            )
    else:
        checks.append(
            Check(
                "COM ProgID",
                Status.ERROR if installs else Status.WARN,
                "no EViews COM server is registered",
                "Run EViews once as the current user so it registers itself, "
                "or reinstall with automation enabled.",
                group="eviews",
            )
        )

    if importlib.util.find_spec("pyeviews") is not None:
        try:
            import pyeviews  # noqa: F401

            detail, status = (
                "installed and importable (not used — EconEnv talks to COM directly)",
                Status.PASS,
            )
        except Exception as exc:
            detail, status = f"installed but broken: {type(exc).__name__}: {exc}", Status.SKIP
        checks.append(
            Check(
                "pyeviews",
                status,
                detail,
                "EconEnv does not depend on pyeviews; nothing needs fixing.",
                group="eviews",
            )
        )

    if deep:
        checks.append(_deep_engine_check("eviews"))
    return checks


def _deep_engine_check(name: str) -> Check:
    """Actually start the engine and run a trivial command."""
    from .engines import registry as engine_registry

    try:
        engine = engine_registry.get(name)
        if not engine.available:
            return Check(
                f"{name} live check",
                Status.SKIP,
                engine.info().error or "not available",
                group=name,
            )
        engine.start()
        version = engine.version()
        return Check(
            f"{name} live check",
            Status.PASS,
            f"session started, reports version {version}",
            group=name,
        )
    except Exception as exc:
        return Check(
            f"{name} live check",
            Status.ERROR,
            f"{type(exc).__name__}: {str(exc).splitlines()[0]}",
            "See the message above; `%econ doctor` without --deep skips this step.",
            group=name,
        )


def _module_version(name: str) -> Optional[str]:
    try:
        import importlib.metadata as md

        return md.version(name)
    except Exception:
        spec = importlib.util.find_spec(name)
        return "installed" if spec else None


def run(engine: Optional[str] = None, *, deep: bool = False) -> Report:
    """Run the diagnostics.

    Parameters
    ----------
    engine:
        Limit to one engine's checks.
    deep:
        Also start each engine and run a trivial command. Slower, and it will
        launch Stata/EViews.
    """
    report = Report()
    runners = {
        "r": lambda: check_r(deep),
        "stata": lambda: check_stata(deep),
        "eviews": lambda: check_eviews(deep),
    }
    if engine:
        key = engine.lower()
        if key not in runners:
            report.add(Check(f"engine {engine}", Status.ERROR, "unknown engine", group="general"))
            return report
        report.add(*runners[key]())
        return report

    report.add(*check_host())
    report.add(*check_config())
    for runner in runners.values():
        report.add(*runner())
    return report
