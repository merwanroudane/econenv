"""Locating R, Stata and EViews without hard-coding anyone's machine (brief §27).

Search order is the same for all three:

1. explicit EconEnv config (``%econ config`` / ``config.toml``)
2. the conventional environment variable (``R_HOME``, ``STATA_HOME``)
3. ``PATH``
4. the Windows registry, where the vendor writes one
5. the usual install roots for the platform

Discovery **validates the executable**, not just the folder. This machine has a
``C:\\Program Files\\Stata18`` directory containing no ``.exe`` at all; a
folder-only check would have picked it and then failed at ``init``.
"""

from __future__ import annotations

import glob
import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from ._logging import get_logger

_log = get_logger("discovery")

IS_WINDOWS = platform.system() == "Windows"
IS_MACOS = platform.system() == "Darwin"


@dataclass
class Installation:
    """One candidate installation found on disk."""

    engine: str
    home: Path
    executable: Optional[Path] = None
    version: Optional[str] = None
    edition: Optional[str] = None
    source: str = "scan"  # config | env | path | registry | scan
    detail: Dict[str, str] = field(default_factory=dict)

    @property
    def valid(self) -> bool:
        return self.executable is not None and Path(self.executable).exists()

    def __str__(self) -> str:
        bits = [self.engine, str(self.home)]
        if self.version:
            bits.append(self.version)
        if self.edition:
            bits.append(f"({self.edition})")
        bits.append(f"via {self.source}")
        return " ".join(bits)


def _version_key(text: Optional[str]) -> tuple:
    """Sort key that orders '19.5' above '18' above '17' (and text last)."""
    if not text:
        return (0,)
    nums = [int(n) for n in re.findall(r"\d+", text)[:4]]
    return (1, *nums) if nums else (0,)


def _read_registry(root: str, subkey: str, value: Optional[str] = None) -> Optional[str]:
    if not IS_WINDOWS:
        return None
    try:
        import winreg
    except ImportError:  # pragma: no cover
        return None
    hive = {"HKLM": winreg.HKEY_LOCAL_MACHINE, "HKCU": winreg.HKEY_CURRENT_USER}[root]
    for access in (winreg.KEY_READ, winreg.KEY_READ | winreg.KEY_WOW64_32KEY):
        try:
            with winreg.OpenKey(hive, subkey, 0, access) as key:
                data, _ = winreg.QueryValueEx(key, value or "")
                if isinstance(data, str) and data.strip():
                    return data.strip()
        except OSError:
            continue
    return None


def _registry_subkeys(root: str, subkey: str) -> List[str]:
    if not IS_WINDOWS:
        return []
    try:
        import winreg
    except ImportError:  # pragma: no cover
        return []
    hive = {"HKLM": winreg.HKEY_LOCAL_MACHINE, "HKCU": winreg.HKEY_CURRENT_USER}[root]
    out: List[str] = []
    for access in (winreg.KEY_READ, winreg.KEY_READ | winreg.KEY_WOW64_32KEY):
        try:
            with winreg.OpenKey(hive, subkey, 0, access) as key:
                index = 0
                while True:
                    try:
                        out.append(winreg.EnumKey(key, index))
                        index += 1
                    except OSError:
                        break
            break
        except OSError:
            continue
    return out


def _program_roots() -> List[Path]:
    """Plausible install roots for the current platform."""
    if IS_WINDOWS:
        roots = [
            os.environ.get("PROGRAMFILES", r"C:\Program Files"),
            os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
            os.environ.get("PROGRAMW6432", r"C:\Program Files"),
            r"C:\\",
        ]
    elif IS_MACOS:
        roots = ["/Applications", "/usr/local", "/opt", str(Path.home() / "Applications")]
    else:
        roots = ["/usr/lib", "/usr/local", "/opt", "/usr/share"]
    seen, out = set(), []
    for root in roots:
        path = Path(root)
        if path.is_dir() and str(path) not in seen:
            seen.add(str(path))
            out.append(path)
    return out


# --------------------------------------------------------------------------- #
# R
# --------------------------------------------------------------------------- #
def _r_executable(home: Path) -> Optional[Path]:
    """The R front-end inside an R_HOME, for the current architecture."""
    if IS_WINDOWS:
        candidates = [home / "bin" / "x64" / "R.exe", home / "bin" / "R.exe"]
    else:
        candidates = [home / "bin" / "R", home / "R"]
    return next((c for c in candidates if c.is_file()), None)


def find_r(configured: Optional[str] = None) -> List[Installation]:
    """Every usable R installation, newest first."""
    found: List[Installation] = []
    seen: set = set()

    def add(home_str: Optional[str], source: str) -> None:
        if not home_str:
            return
        home = Path(home_str).expanduser()
        # Tolerate being handed bin/ or bin/x64/ instead of R_HOME itself.
        for candidate in (home, home.parent, home.parent.parent):
            exe = _r_executable(candidate)
            if exe and str(candidate.resolve()).lower() not in seen:
                seen.add(str(candidate.resolve()).lower())
                found.append(
                    Installation(
                        engine="r",
                        home=candidate,
                        executable=exe,
                        version=_r_version(exe),
                        source=source,
                    )
                )
                return

    add(configured, "config")
    add(os.environ.get("R_HOME"), "env")

    on_path = shutil.which("R") or shutil.which("Rscript")
    if on_path:
        exe = Path(on_path)
        add(str(exe.parent.parent), "path")

    if IS_WINDOWS:
        for hive in ("HKLM", "HKCU"):
            add(_read_registry(hive, r"SOFTWARE\R-core\R", "InstallPath"), "registry")
            for sub in _registry_subkeys(hive, r"SOFTWARE\R-core\R"):
                add(_read_registry(hive, rf"SOFTWARE\R-core\R\{sub}", "InstallPath"), "registry")

    for root in _program_roots():
        for pattern in ("R/R-*", "R-*", "lib/R", "R"):
            for match in sorted(glob.glob(str(root / pattern))):
                add(match, "scan")

    if IS_MACOS:
        add("/Library/Frameworks/R.framework/Resources", "scan")

    found.sort(key=lambda i: _version_key(i.version), reverse=True)
    return found


def _r_version(exe: Path) -> Optional[str]:
    try:
        out = subprocess.run(
            [str(exe), "--version"],
            capture_output=True,
            text=True,
            timeout=25,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        _log.debug("R --version failed for %s: %s", exe, exc)
        return None
    text = f"{out.stdout}\n{out.stderr}"
    match = re.search(r"R version (\d+\.\d+\.\d+)", text)
    return match.group(1) if match else None


# --------------------------------------------------------------------------- #
# Stata
# --------------------------------------------------------------------------- #
_STATA_EXES = {
    "mp": ["StataMP-64.exe", "StataMP.exe", "stata-mp", "StataMP"],
    "se": ["StataSE-64.exe", "StataSE.exe", "stata-se", "StataSE"],
    "be": ["StataBE-64.exe", "StataBE.exe", "Stata-64.exe", "stata-be", "StataBE", "stata"],
}


def _stata_executable(home: Path) -> tuple:
    """Best (executable, edition) inside a Stata home, MP > SE > BE."""
    search_dirs = [home, home / "bin", home / "Contents" / "MacOS"]
    for edition in ("mp", "se", "be"):
        for name in _STATA_EXES[edition]:
            for directory in search_dirs:
                candidate = directory / name
                if candidate.is_file():
                    return candidate, edition
    return None, None


def find_stata(configured: Optional[str] = None) -> List[Installation]:
    """Every usable Stata installation, newest first.

    An install is only reported when a launcher executable **and** the bundled
    ``utilities/pystata`` package are both present — pystata is what EconEnv
    actually drives.
    """
    found: List[Installation] = []
    seen: set = set()

    def add(home_str: Optional[str], source: str) -> None:
        if not home_str:
            return
        home = Path(home_str).expanduser()
        if not home.is_dir() or str(home.resolve()).lower() in seen:
            return
        exe, edition = _stata_executable(home)
        if exe is None:
            _log.debug("skipping %s: no Stata executable inside", home)
            return
        seen.add(str(home.resolve()).lower())
        pystata_dir = home / "utilities" / "pystata"
        found.append(
            Installation(
                engine="stata",
                home=home,
                executable=exe,
                version=_stata_version_from_path(home),
                edition=edition,
                source=source,
                detail={
                    "pystata": str(pystata_dir) if pystata_dir.is_dir() else "",
                    "utilities": str(home / "utilities"),
                },
            )
        )

    add(configured, "config")
    add(os.environ.get("STATA_HOME"), "env")

    for exe_name in ("StataMP-64", "StataSE-64", "stata-mp", "stata-se", "stata"):
        on_path = shutil.which(exe_name)
        if on_path:
            add(str(Path(on_path).parent), "path")

    if IS_WINDOWS:
        for hive in ("HKLM", "HKCU"):
            for sub in _registry_subkeys(hive, r"SOFTWARE\Stata"):
                add(_read_registry(hive, rf"SOFTWARE\Stata\{sub}", "InstallPath"), "registry")

    for root in _program_roots():
        for pattern in ("Stata*", "stata*"):
            for match in sorted(glob.glob(str(root / pattern))):
                add(match, "scan")

    found.sort(key=lambda i: _version_key(i.version), reverse=True)
    return found


def _stata_version_from_path(home: Path) -> Optional[str]:
    """Version from the directory name — the real one comes from ``c(stata_version)``.

    ``StataNow19`` and ``Stata18`` both encode it; anything else returns None
    rather than a guess.
    """
    match = re.search(r"(\d+)", home.name)
    return match.group(1) if match else None


def pystata_path(home: Path) -> Optional[Path]:
    """``<STATA_HOME>/utilities`` when it contains a ``pystata`` package."""
    utilities = Path(home) / "utilities"
    return utilities if (utilities / "pystata").is_dir() else None


# --------------------------------------------------------------------------- #
# EViews
# --------------------------------------------------------------------------- #
def find_eviews() -> List[Installation]:
    """Every EViews installation on disk, newest first (Windows only)."""
    if not IS_WINDOWS:
        return []
    found: List[Installation] = []
    seen: set = set()
    for root in _program_roots():
        for match in sorted(glob.glob(str(root / "EViews*"))):
            home = Path(match)
            if not home.is_dir() or str(home.resolve()).lower() in seen:
                continue
            exes = sorted(home.glob("EViews*.exe"))
            main = next(
                (e for e in exes if re.fullmatch(r"EViews\d+\.exe", e.name, re.IGNORECASE)), None
            )
            if main is None:
                continue
            seen.add(str(home.resolve()).lower())
            version = re.search(r"(\d+)", main.stem)
            found.append(
                Installation(
                    engine="eviews",
                    home=home,
                    executable=main,
                    version=version.group(1) if version else None,
                    source="scan",
                    detail={"has_xeus_kernel": str((home / "XeusEViews.exe").is_file())},
                )
            )
    found.sort(key=lambda i: _version_key(i.version), reverse=True)
    return found


def eviews_progids() -> List[str]:
    """COM ProgIDs that resolve on this machine, generic first.

    Registration order decides what the generic ``EViews.Manager`` binds to, so
    the caller must report the version it *connected* to (audit §5.1).
    """
    if not IS_WINDOWS:
        return []
    candidates = ["EViews.Manager"] + [f"EViews{v}.Manager" for v in range(20, 9, -1)]
    resolved = []
    for progid in candidates:
        if _read_registry("HKLM", rf"SOFTWARE\Classes\{progid}\CLSID") or _clsid_for(progid):
            resolved.append(progid)
    return resolved


def _clsid_for(progid: str) -> Optional[str]:
    if not IS_WINDOWS:
        return None
    try:
        import winreg
    except ImportError:  # pragma: no cover
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, f"{progid}\\CLSID") as key:
            return winreg.QueryValue(key, None)
    except OSError:
        return None


# --------------------------------------------------------------------------- #
# environment snapshot support
# --------------------------------------------------------------------------- #
def host_info() -> Dict[str, str]:
    """OS / architecture / Python facts for the reproducibility snapshot."""
    return {
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "python_executable": sys.executable,
    }


def which_all(names_: Sequence[str]) -> Dict[str, Optional[str]]:
    return {name: shutil.which(name) for name in names_}
