"""The engine interface every backend implements (brief §4).

Nothing outside :mod:`econenv.engines` and :mod:`econenv.bridges` may touch a
vendor API. Magics, the CLI, diagnostics and the model layer all speak only to
:class:`BaseEngine`.

Subclasses implement the ``_``-prefixed hooks; the public methods here own the
lifecycle bookkeeping, timing, error translation and result construction that
would otherwise be copy-pasted into every adapter.
"""

from __future__ import annotations

import abc
import platform
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import pandas as pd

from .._logging import get_logger
from ..exceptions import (
    CapabilityError,
    EngineExecutionError,
    EngineNotStartedError,
    EngineUnavailableError,
)
from ..results import ExecutionResult
from ..schema import DatasetMetadata


class Capability(str, Enum):
    """What an engine can do. Reported, never assumed (brief §25)."""

    EXECUTE = "execute"
    PERSISTENT_SESSION = "persistent_session"
    PUSH_FRAME = "push_frame"
    PULL_FRAME = "pull_frame"
    PUSH_SCALAR = "push_scalar"
    PULL_SCALAR = "pull_scalar"
    PULL_MATRIX = "pull_matrix"
    GRAPHICS = "graphics"
    OLS = "ols"
    RESTART = "restart"
    INTERRUPT = "interrupt"


class EngineState(str, Enum):
    UNKNOWN = "unknown"
    NOT_INSTALLED = "not_installed"
    INSTALLED = "installed"  # found on disk, not configured
    CONFIGURED = "configured"  # EconEnv knows how to start it
    RUNNING = "running"
    FAILED = "failed"
    STOPPED = "stopped"


@dataclass
class EngineInfo:
    """A snapshot of one engine, safe to serialise (brief §5, §20)."""

    name: str
    display_name: str
    state: EngineState
    version: Optional[str] = None
    edition: Optional[str] = None
    home: Optional[str] = None
    executable: Optional[str] = None
    backend: Optional[str] = None
    platform_supported: bool = True
    capabilities: List[str] = field(default_factory=list)
    detail: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "state": self.state.value,
            "version": self.version,
            "edition": self.edition,
            "home": self.home,
            "executable": self.executable,
            "backend": self.backend,
            "platform_supported": self.platform_supported,
            "capabilities": list(self.capabilities),
            "detail": dict(self.detail),
            "error": self.error,
        }


class BaseEngine(abc.ABC):
    """Abstract execution engine.

    Subclass contract — implement these:

    ``_detect()``      locate the software, fill ``self._home`` / ``_executable``
    ``_start()``       bring up a session
    ``_stop()``        tear it down (must be safe to call twice)
    ``_execute(code)`` run code, return an :class:`ExecutionResult`
    ``_version()``     the version string *of the running session*

    Optional — override where the engine supports it:

    ``_push_frame``, ``_pull_frame``, ``_push_scalar``, ``_pull_scalar``,
    ``_pull_matrix``, ``_fit_ols``.
    """

    #: Registry key, e.g. ``"stata"``.
    name: str = "base"
    #: Human-readable name for display.
    display_name: str = "Base"
    #: Platforms this engine can run on. Empty means "all".
    supported_platforms: tuple = ()
    #: Declared capabilities, before runtime detection narrows them.
    declared_capabilities: tuple = (Capability.EXECUTE,)

    def __init__(self, **options: Any) -> None:
        self.options: Dict[str, Any] = dict(options)
        self._state: EngineState = EngineState.UNKNOWN
        self._home: Optional[str] = None
        self._executable: Optional[str] = None
        self._backend: Optional[str] = None
        self._version_cache: Optional[str] = None
        self._detect_error: Optional[str] = None
        self._detected = False
        self.log = get_logger(self.name)

    # ------------------------------------------------------------------ #
    # platform / availability
    # ------------------------------------------------------------------ #
    @classmethod
    def platform_supported(cls) -> bool:
        """Is this engine even possible on the current OS?"""
        return not cls.supported_platforms or platform.system() in cls.supported_platforms

    def detect(self, *, force: bool = False) -> bool:
        """Locate the software. Cheap, side-effect free, never starts anything."""
        if self._detected and not force:
            return self._state not in (EngineState.NOT_INSTALLED, EngineState.UNKNOWN)
        self._detected = True
        self._detect_error = None
        if not self.platform_supported():
            self._state = EngineState.NOT_INSTALLED
            self._detect_error = (
                f"{self.display_name} is not supported on {platform.system()}; "
                f"supported: {', '.join(self.supported_platforms)}"
            )
            return False
        try:
            found = self._detect()
        except Exception as exc:
            self._state = EngineState.NOT_INSTALLED
            self._detect_error = f"{type(exc).__name__}: {exc}"
            self.log.debug("detect failed: %s", exc)
            return False
        if found and self._state in (EngineState.UNKNOWN, EngineState.NOT_INSTALLED):
            self._state = EngineState.CONFIGURED
        elif not found:
            self._state = EngineState.NOT_INSTALLED
        return bool(found)

    @property
    def available(self) -> bool:
        """True when the engine is installed and configurable on this machine."""
        self.detect()
        return self._state in (
            EngineState.INSTALLED,
            EngineState.CONFIGURED,
            EngineState.RUNNING,
            EngineState.STOPPED,
        )

    @property
    def running(self) -> bool:
        return self._state is EngineState.RUNNING

    @property
    def state(self) -> EngineState:
        return self._state

    def configure(self, **options: Any) -> None:
        """Apply user options. Forces re-detection, and stops a live session."""
        if self.running:
            self.stop()
        self.options.update(options)
        self._detected = False
        self._version_cache = None
        self.detect(force=True)

    # ------------------------------------------------------------------ #
    # lifecycle
    # ------------------------------------------------------------------ #
    def start(self) -> None:
        """Bring up a persistent session. Idempotent."""
        if self.running:
            return
        if not self.available:
            raise EngineUnavailableError(
                self._detect_error or f"{self.display_name} was not found on this machine.",
                engine=self.name,
                hint=f"Run `econenv doctor` or `%econ doctor {self.name}` for the details.",
            )
        self.log.debug("starting")
        try:
            self._start()
        except Exception:
            self._state = EngineState.FAILED
            raise
        self._state = EngineState.RUNNING
        self._version_cache = None

    def stop(self) -> None:
        """Tear the session down. Safe to call when not running."""
        if self._state is not EngineState.RUNNING:
            self._state = EngineState.STOPPED if self._detected else self._state
            return
        try:
            self._stop()
        finally:
            self._state = EngineState.STOPPED
            self._version_cache = None

    def restart(self) -> None:
        self.stop()
        self.start()

    def ensure_started(self) -> None:
        """Start on demand when ``core.autostart`` is on, else say so plainly."""
        if self.running:
            return
        from .. import config as _config

        if _config.get_option("core", "autostart", True):
            self.start()
        else:
            raise EngineNotStartedError(
                f"{self.display_name} is not running and autostart is off.",
                engine=self.name,
                hint=f"Run `%econ start {self.name}`.",
            )

    def cleanup(self) -> None:
        """Release every resource. Called at interpreter exit."""
        try:
            self.stop()
        except Exception as exc:
            self.log.debug("cleanup: %s", exc)

    # ------------------------------------------------------------------ #
    # execution
    # ------------------------------------------------------------------ #
    def execute(self, code: str, **kwargs: Any) -> ExecutionResult:
        """Run *code* and return a normalised :class:`ExecutionResult`.

        Timing, the ``engine``/``code`` fields and error translation happen here
        so no adapter has to remember them.
        """
        self.ensure_started()
        started = time.perf_counter()
        try:
            result = self._execute(code, **kwargs)
        except EngineExecutionError as exc:
            exc.code = exc.code or code
            raise
        except Exception as exc:
            raise EngineExecutionError(str(exc), engine=self.name, code=code, raw=exc) from exc
        result.engine = self.name
        result.code = code
        if not result.elapsed:
            result.elapsed = time.perf_counter() - started
        if result.engine_version is None:
            result.engine_version = self.version()
        return result

    def version(self) -> Optional[str]:
        """Version of the *running* session, cached.

        Deliberately not the version found on disk — for EViews those two can
        disagree (see the Phase 0 audit, §5.1).
        """
        if self._version_cache is None:
            try:
                self._version_cache = self._version()
            except Exception as exc:
                self.log.debug("version lookup failed: %s", exc)
                self._version_cache = None
        return self._version_cache

    # ------------------------------------------------------------------ #
    # data
    # ------------------------------------------------------------------ #
    def push(self, name: str, obj: Any, **kwargs: Any) -> None:
        """Send a Python object into the engine under *name*."""
        self.ensure_started()
        if isinstance(obj, pd.DataFrame):
            self._require(Capability.PUSH_FRAME)
            self._push_frame(name, obj, **kwargs)
        elif isinstance(obj, pd.Series):
            self._require(Capability.PUSH_FRAME)
            self._push_frame(name, obj.to_frame(), **kwargs)
        else:
            self._require(Capability.PUSH_SCALAR)
            self._push_scalar(name, obj, **kwargs)

    def pull(self, name: Optional[str] = None, **kwargs: Any) -> Any:
        """Bring an object back out of the engine."""
        self.ensure_started()
        self._require(Capability.PULL_FRAME)
        return self._pull_frame(name, **kwargs)

    def pull_value(self, name: str, **kwargs: Any) -> Any:
        """Bring *name* back as its natural Python type, not necessarily a frame.

        ``pull`` is frame-oriented, which is what ``move`` and ``broadcast``
        need. It is the wrong contract for a scalar: an engine variable holding
        ``10`` is a number, and wrapping it in a DataFrame to satisfy a single
        return type serves nobody. Engines that can tell their types apart
        override ``_pull_value``; the rest fall back to the frame, so this is
        always safe to call.
        """
        self.ensure_started()
        return self._pull_value(name, **kwargs)

    def pull_scalar(self, expression: str) -> Any:
        self.ensure_started()
        self._require(Capability.PULL_SCALAR)
        return self._pull_scalar(expression)

    def pull_matrix(self, name: str):
        self.ensure_started()
        self._require(Capability.PULL_MATRIX)
        return self._pull_matrix(name)

    # ------------------------------------------------------------------ #
    # introspection
    # ------------------------------------------------------------------ #
    def capabilities(self) -> List[Capability]:
        """Capabilities that hold *right now*, on this install.

        Declared capabilities are filtered by what the running backend actually
        supports, which is why this is a method and not a constant (brief §25).
        """
        return list(self.declared_capabilities)

    def has(self, capability: Capability) -> bool:
        return capability in self.capabilities()

    def _require(self, capability: Capability) -> None:
        if not self.has(capability):
            raise CapabilityError(
                f"{self.display_name} does not support {capability.value} in EconEnv "
                f"{'(backend: ' + self._backend + ')' if self._backend else ''}".strip()
            )

    def info(self) -> EngineInfo:
        """A serialisable snapshot, used by ``%econ engines``, the CLI and doctor."""
        self.detect()
        return EngineInfo(
            name=self.name,
            display_name=self.display_name,
            state=self._state,
            version=self.version() if self.running else self._static_version(),
            edition=self._edition(),
            home=self._home,
            executable=self._executable,
            backend=self._backend,
            platform_supported=self.platform_supported(),
            capabilities=[c.value for c in self.capabilities()],
            detail=self._info_detail(),
            error=self._detect_error,
        )

    def status_line(self) -> str:
        info = self.info()
        bits = [f"{info.display_name:<8}", f"{info.state.value:<14}"]
        if info.version:
            bits.append(info.version)
        if info.edition:
            bits.append(f"({info.edition})")
        if info.backend:
            bits.append(f"[{info.backend}]")
        return " ".join(bits)

    def __repr__(self) -> str:
        return f"<{type(self).__name__} state={self._state.value} version={self._version_cache}>"

    # ------------------------------------------------------------------ #
    # hooks for subclasses
    # ------------------------------------------------------------------ #
    @abc.abstractmethod
    def _detect(self) -> bool:
        """Locate the software. Return True when it is usable."""

    @abc.abstractmethod
    def _start(self) -> None: ...

    @abc.abstractmethod
    def _stop(self) -> None: ...

    @abc.abstractmethod
    def _execute(self, code: str, **kwargs: Any) -> ExecutionResult: ...

    def _version(self) -> Optional[str]:
        return None

    def _static_version(self) -> Optional[str]:
        """Version inferred from disk, before a session exists."""
        return None

    def _edition(self) -> Optional[str]:
        return None

    def _info_detail(self) -> Dict[str, Any]:
        return {}

    def _push_frame(self, name: str, df: pd.DataFrame, **kwargs: Any) -> None:
        raise CapabilityError(f"{self.display_name} cannot receive DataFrames.")

    def _pull_frame(self, name: Optional[str], **kwargs: Any) -> pd.DataFrame:
        raise CapabilityError(f"{self.display_name} cannot return DataFrames.")

    def _push_scalar(self, name: str, value: Any, **kwargs: Any) -> None:
        raise CapabilityError(f"{self.display_name} cannot receive scalars.")

    def _pull_value(self, name: str, **kwargs: Any) -> Any:
        """Default: whatever ``pull`` gives, so every engine answers something."""
        self._require(Capability.PULL_FRAME)
        return self._pull_frame(name, **kwargs)

    def _pull_scalar(self, expression: str) -> Any:
        raise CapabilityError(f"{self.display_name} cannot return scalars.")

    def _pull_matrix(self, name: str):
        raise CapabilityError(f"{self.display_name} cannot return matrices.")

    def _fit_ols(self, spec, data: pd.DataFrame, meta: Optional[DatasetMetadata] = None):
        raise CapabilityError(f"{self.display_name} has no OLS adapter yet.")
