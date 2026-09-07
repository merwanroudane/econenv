"""The engine registry (brief §5).

Holds the *classes* that are known and the *instances* that are live, and is the
extension point for third-party engines — either by calling :func:`register`, or
by publishing an ``econenv.engines`` entry point:

.. code-block:: toml

    [project.entry-points."econenv.engines"]
    julia = "my_pkg.engine:JuliaEngine"

Entry points are loaded lazily and a broken plugin is reported, not raised: one
bad third-party engine must not stop the other three from working.
"""

from __future__ import annotations

import atexit
import contextlib
from typing import Any, Dict, Iterator, List, Optional, Type

from .._logging import get_logger
from ..exceptions import EconEnvError, EngineNotFoundError
from .base import BaseEngine, EngineInfo

_log = get_logger("registry")

_classes: Dict[str, Type[BaseEngine]] = {}
_instances: Dict[str, BaseEngine] = {}
_plugin_errors: Dict[str, str] = {}
_entry_points_loaded = False
_builtins_loaded = False


def register(engine_cls: Type[BaseEngine], *, replace: bool = False) -> Type[BaseEngine]:
    """Register an engine class. Usable as a decorator."""
    if not (isinstance(engine_cls, type) and issubclass(engine_cls, BaseEngine)):
        raise EconEnvError(f"{engine_cls!r} is not a BaseEngine subclass.")
    name = engine_cls.name
    if not name or name == "base":
        raise EconEnvError(f"{engine_cls.__name__} must set a unique `name`.")
    if name in _classes and not replace:
        if _classes[name] is engine_cls:
            return engine_cls
        raise EconEnvError(
            f"An engine named {name!r} is already registered "
            f"({_classes[name].__name__}). Pass replace=True to override."
        )
    _classes[name] = engine_cls
    _instances.pop(name, None)
    _log.debug("registered engine %s -> %s", name, engine_cls.__name__)
    return engine_cls


def unregister(name: str) -> None:
    engine = _instances.pop(name, None)
    if engine is not None:
        engine.cleanup()
    _classes.pop(name, None)


def _load_builtin() -> None:
    """Import the engines that ship with EconEnv."""
    from . import (  # noqa: F401
        eviews_engine,
        gauss_engine,
        matlab_engine,
        python_engine,
        r_engine,
        stata_engine,
    )


def _load_entry_points() -> None:
    global _entry_points_loaded
    if _entry_points_loaded:
        return
    _entry_points_loaded = True
    try:
        from importlib.metadata import entry_points
    except ImportError:  # pragma: no cover
        return
    # `entry_points(group=...)` is the 3.10+ signature; 3.9 returns a dict.
    found: Any
    try:
        found = entry_points(group="econenv.engines")
    except TypeError:  # pragma: no cover - Python 3.9 API
        found = entry_points().get("econenv.engines", [])
    for entry in found:
        if entry.name in _classes:
            continue
        try:
            register(entry.load())
        except Exception as exc:
            _plugin_errors[entry.name] = f"{type(exc).__name__}: {exc}"
            _log.warning("engine plugin %r failed to load: %s", entry.name, exc)


def _ensure_loaded() -> None:
    """Import the built-in engines exactly once.

    This used to be guarded by ``if not _classes``, which is a proxy for "the
    built-ins have not been imported" only until something imports one engine
    module directly — as several test modules do. Registering that one class
    made ``_classes`` non-empty, so the rest were never imported, and
    ``registry.names()`` silently returned a short list.
    """
    global _builtins_loaded
    if not _builtins_loaded:
        _builtins_loaded = True
        _load_builtin()
    _load_entry_points()


def names() -> List[str]:
    """Registered engine names, ``python`` first then alphabetical."""
    _ensure_loaded()
    ordered = sorted(_classes)
    if "python" in ordered:
        ordered.remove("python")
        ordered.insert(0, "python")
    return ordered


def get(name: str, **options: Any) -> BaseEngine:
    """Return the singleton instance for *name*, creating it if needed."""
    _ensure_loaded()
    key = name.strip().lower()
    if key not in _classes:
        raise EngineNotFoundError(
            f"No engine named {name!r}. Registered: {', '.join(names())}",
            engine=name,
        )
    engine = _instances.get(key)
    if engine is None:
        engine = _classes[key]()
        _instances[key] = engine
    if options:
        engine.configure(**options)
    return engine


def instances() -> Dict[str, BaseEngine]:
    """Only the engines that have actually been instantiated."""
    return dict(_instances)


def all_engines() -> Iterator[BaseEngine]:
    """Every registered engine, instantiating as needed."""
    for name in names():
        yield get(name)


def info(name: Optional[str] = None) -> List[EngineInfo]:
    """Snapshot one engine, or all of them."""
    if name is not None:
        return [get(name).info()]
    return [engine.info() for engine in all_engines()]


def available() -> List[str]:
    """Names of engines installed and usable on this machine."""
    return [e.name for e in all_engines() if e.available]


def running() -> List[str]:
    """Names of engines with a live session."""
    return [name for name, engine in _instances.items() if engine.running]


def plugin_errors() -> Dict[str, str]:
    """Third-party engines that failed to load, and why."""
    _ensure_loaded()
    return dict(_plugin_errors)


def stop_all() -> None:
    """Stop every live session (``%econ stop``, ``econenv`` exit)."""
    for engine in list(_instances.values()):
        try:
            engine.stop()
        except Exception as exc:
            _log.debug("stop_all: %s failed: %s", engine.name, exc)


def reset(name: Optional[str] = None) -> None:
    """Drop instances so the next :func:`get` builds a fresh one."""
    targets = [name] if name else list(_instances)
    for key in targets:
        engine = _instances.pop(key, None)
        if engine is not None:
            engine.cleanup()


@atexit.register
def _shutdown() -> None:  # pragma: no cover - interpreter teardown
    for engine in list(_instances.values()):
        with contextlib.suppress(Exception):
            engine.cleanup()
