"""GAUSS as an EconEnv engine.

GAUSS is driven through its terminal executable. A native binding to the GAUSS
Engine C API would give a persistent workspace and faster transfers, and the
architecture here leaves room for it — :class:`GaussEngine` selects a *backend*
rather than talking to a process directly — but the CLI is what exists today and
it is honest about what it cannot do.

**Which installation runs.** More than one GAUSS can be installed and they do
not all work; on the machine this was developed against, ``gauss24`` and
``gauss25`` are present and only ``gauss26`` runs. So detection reports the
installation EconEnv will *actually* use and lists the rest, rather than naming
the newest directory on disk and hoping. That is the same mistake the EViews
adapter used to make with ProgIDs, and the MATLAB adapter with engine releases.

**Detection does not start GAUSS.** Finding the executable and reading its
banner costs milliseconds; starting a session does not. ``%econ status`` stays
fast, and ``%econ doctor gauss --deep`` is where a real round trip happens.
"""

from __future__ import annotations

import glob
import os
import platform
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from .. import config as _config
from ..exceptions import DataTransferError, EngineExecutionError
from ..results import ExecutionResult
from ._gauss_cli import GaussCliBackend, describe, find_executable, probe_version
from .base import BaseEngine, Capability
from .registry import register

#: ``gauss26``, ``GAUSS 24``, ``gauss24.0`` — the version in a directory name.
_VERSION_IN_NAME = re.compile(r"(\d+)(?:[._](\d+))?\s*$")


def _version_key(path: Path) -> tuple:
    """Sort key that puts the newest installation first."""
    match = _VERSION_IN_NAME.search(path.name.replace("GAUSS", "").replace("gauss", ""))
    if not match:
        return (0, 0)
    return (int(match.group(1)), int(match.group(2) or 0))


def find_gauss() -> List[Path]:
    """GAUSS installation roots, newest first.

    GAUSS does not install into Program Files by default on Windows — the
    installation this was developed against is ``C:\\gauss26`` — so looking only
    where other vendors put things would find nothing.
    """
    roots: List[Path] = []

    configured = _config.get_option("gauss", "home", None)
    if configured:
        roots.append(Path(configured))
    for variable in ("GAUSSHOME", "MTENGHOME", "GAUSS_HOME"):
        if value := os.environ.get(variable):
            roots.append(Path(value))

    if platform.system() == "Windows":
        patterns = [
            r"C:\gauss*",
            r"C:\GAUSS*",
            os.path.join(os.environ.get("PROGRAMFILES", r"C:\Program Files"), "GAUSS*"),
            os.path.join(os.environ.get("PROGRAMFILES", r"C:\Program Files"), "Aptech", "*"),
        ]
    elif platform.system() == "Darwin":
        patterns = ["/Applications/GAUSS*", "/Applications/Aptech/*"]
    else:
        patterns = ["/usr/local/gauss*", "/opt/gauss*", "/usr/local/GAUSS*"]

    for pattern in patterns:
        roots.extend(Path(match) for match in glob.glob(pattern))

    seen: set = set()
    found: List[Path] = []
    for root in roots:
        key = str(root).lower()
        if key in seen or not root.is_dir():
            continue
        seen.add(key)
        if find_executable(root) is not None:
            found.append(root)

    found.sort(key=_version_key, reverse=True)
    return found


@register
class GaussEngine(BaseEngine):
    """GAUSS, through its terminal executable."""

    name = "gauss"
    display_name = "GAUSS"
    declared_capabilities = (
        Capability.EXECUTE,
        Capability.PUSH_FRAME,
        Capability.PULL_FRAME,
        Capability.PUSH_SCALAR,
        Capability.PULL_SCALAR,
        Capability.PULL_MATRIX,
        Capability.RESTART,
    )

    def __init__(self, **options: Any) -> None:
        super().__init__(**options)
        self._backend: Any = None
        self._installs: List[Path] = []
        self._executable_path: Optional[Path] = None
        self._version_cache_value: Optional[str] = None
        self._last_frame: Optional[str] = None

    # ------------------------------------------------------------------ #
    # detection
    # ------------------------------------------------------------------ #
    def _detect(self) -> bool:
        self._installs = find_gauss()
        if not self._installs:
            self._detect_error = (
                "No GAUSS installation was found. EconEnv looks at gauss.home, the "
                "GAUSSHOME and MTENGHOME environment variables, and the usual "
                "install locations (C:\\gauss* on Windows). Set the path if yours "
                "is elsewhere:  %econ config gauss.home C:/gauss26"
            )
            return False

        chosen = self._installs[0]
        executable = find_executable(chosen)
        if executable is None:  # pragma: no cover - find_gauss filters these out
            self._detect_error = f"{chosen} has no tgauss executable."
            return False

        self._home = str(chosen)
        self._executable = str(executable)
        self._executable_path = executable
        self._backend_kind = self._requested_backend()
        return True

    def _requested_backend(self) -> str:
        """``auto`` today means ``cli``; a native backend can claim it later."""
        choice = str(_config.get_option("gauss", "backend", "auto") or "auto").lower()
        if choice in ("native",):
            # Stated rather than silently downgraded: a user who asked for the
            # native backend should know they did not get it.
            return "native-unavailable"
        return "cli"

    def _static_version(self) -> Optional[str]:
        if self._version_cache_value is None and self._executable_path is not None:
            self._version_cache_value = probe_version(self._executable_path)
        return self._version_cache_value

    def _info_detail(self) -> Dict[str, Any]:
        detail: Dict[str, Any] = {
            "installations": [str(p) for p in self._installs],
            "using": self._home,
        }
        if self._executable_path is not None:
            detail.update(describe(self._executable_path))
        if getattr(self, "_backend_kind", "cli") == "native-unavailable":
            detail["backend"] = (
                "cli (gauss.backend=native was requested, but no native binding is built yet)"
            )
        detail["session"] = (
            "One process per cell. Values are carried between cells with GAUSS's "
            "own save/load; procedures and #include state are not."
        )
        return detail

    # ------------------------------------------------------------------ #
    # lifecycle
    # ------------------------------------------------------------------ #
    def _start(self) -> None:
        assert self._executable_path is not None
        self._backend = GaussCliBackend(self._executable_path, Path(self._home or "."))
        self._backend.start()

    def _stop(self) -> None:
        if self._backend is not None:
            self._backend.stop()
            self._backend = None

    # ------------------------------------------------------------------ #
    # execution
    # ------------------------------------------------------------------ #
    def _execute(self, code: str, **kwargs: Any) -> ExecutionResult:
        timeout = float(_config.get_option("gauss", "timeout", 600) or 600)
        text, error = self._backend.execute(code, timeout=timeout)
        if error:
            raise EngineExecutionError(error, engine=self.name, code=code)
        return ExecutionResult(engine=self.name, code=code, stdout=text)

    # ------------------------------------------------------------------ #
    # data
    # ------------------------------------------------------------------ #
    def _push_frame(self, name: str, df: pd.DataFrame, **kwargs: Any) -> None:
        from ..bridges.gauss_bridge import push_frame

        push_frame(self, name, df, **kwargs)
        self._last_frame = name

    def _pull_frame(self, name: Optional[str], **kwargs: Any) -> pd.DataFrame:
        from ..bridges.gauss_bridge import pull_frame

        target = name or self._last_frame
        if target is None:
            raise DataTransferError(
                "GAUSS has no current dataset, so `pull` needs a name: "
                "econenv.pull('gauss', 'mydata').",
                engine=self.name,
                hint="Push one first, or name a matrix in the GAUSS workspace.",
            )
        return pull_frame(self, target, **kwargs)

    def _push_scalar(self, name: str, value: Any, **kwargs: Any) -> None:
        from ..bridges.gauss_bridge import push_value

        push_value(self, name, value)

    def _pull_value(self, name: str, **kwargs: Any) -> Any:
        from ..bridges.gauss_bridge import pull_value

        return pull_value(self, name, **kwargs)

    def _pull_scalar(self, expression: str) -> Any:
        from ..bridges.gauss_bridge import evaluate

        return evaluate(self, expression)

    def _pull_matrix(self, name: str) -> np.ndarray:
        from ..bridges.gauss_bridge import pull_matrix

        return pull_matrix(self, name)
