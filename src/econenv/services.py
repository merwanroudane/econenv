"""The service layer shared by ``%econ`` and the ``econenv`` CLI (brief §34).

Both front-ends call these functions, so a behaviour change lands in both at
once and neither can drift. Everything here returns plain data — dicts,
DataFrames, report objects — and does no printing, so the CLI can render text
while the magic renders HTML.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from . import config as _config
from . import diagnostics, transfer
from ._version import __version__
from .engines import registry as engine_registry
from .exceptions import ConfigurationError
from .models.registry import model_registry


def status() -> Dict[str, Any]:
    """Everything ``%econ status`` shows."""
    infos = engine_registry.info()
    return {
        "econenv_version": __version__,
        "engines": [info.to_dict() for info in infos],
        "running": engine_registry.running(),
        "available": engine_registry.available(),
        "plugin_errors": engine_registry.plugin_errors(),
    }


def status_frame() -> pd.DataFrame:
    """The engine table, as a DataFrame for rich display."""
    rows = []
    for info in engine_registry.info():
        rows.append(
            {
                "engine": info.display_name,
                "state": info.state.value,
                "version": info.version or "",
                "edition": info.edition or "",
                "backend": info.backend or "",
                "location": info.home or "",
            }
        )
    return pd.DataFrame(rows).set_index("engine")


def engines(name: Optional[str] = None) -> List[Dict[str, Any]]:
    return [info.to_dict() for info in engine_registry.info(name)]


def versions() -> Dict[str, Optional[str]]:
    """Version per engine — the *connected* one where a session is live."""
    out: Dict[str, Optional[str]] = {"econenv": __version__}
    for engine in engine_registry.all_engines():
        info = engine.info()
        out[engine.name] = info.version
    return out


def capabilities(name: Optional[str] = None) -> pd.DataFrame:
    """Which capability each engine reports right now."""
    from .engines.base import Capability

    targets = [engine_registry.get(name)] if name else list(engine_registry.all_engines())
    rows = []
    for engine in targets:
        available = set(engine.capabilities()) if engine.available else set()
        row = {"engine": engine.display_name}
        row.update({c.value: ("yes" if c in available else "—") for c in Capability})
        rows.append(row)
    return pd.DataFrame(rows).set_index("engine")


def model_matrix() -> pd.DataFrame:
    """The estimator x engine capability matrix (brief §25)."""
    return model_registry.matrix()


def start(name: str) -> Dict[str, Any]:
    engine = engine_registry.get(name)
    engine.start()
    return engine.info().to_dict()


def stop(name: Optional[str] = None) -> List[str]:
    if name:
        engine_registry.get(name).stop()
        return [name]
    stopped = engine_registry.running()
    engine_registry.stop_all()
    return stopped


def restart(name: str) -> Dict[str, Any]:
    engine = engine_registry.get(name)
    engine.restart()
    return engine.info().to_dict()


def reset(name: Optional[str] = None) -> None:
    """Drop engine instances and runtime config so the next use is fresh."""
    engine_registry.reset(name)
    _config.reset(name)


def doctor(engine: Optional[str] = None, *, deep: bool = False) -> diagnostics.Report:
    return diagnostics.run(engine, deep=deep)


def snapshot(**kwargs: Any) -> Dict[str, Any]:
    return transfer.snapshot(**kwargs)


def config_show() -> pd.DataFrame:
    """Resolved configuration as a two-level table."""
    rows = []
    resolved = _config.as_dict()
    for section, values in resolved.items():
        for key, value in values.items():
            rows.append(
                {"option": f"{section}.{key}", "value": "" if value is None else str(value)}
            )
    return pd.DataFrame(rows).set_index("option")


def config_set(dotted: str, value: str) -> str:
    """``config_set("r.home", "C:/R")`` -> the resolved value, as stored."""
    if "." not in dotted:
        raise ConfigurationError(
            f"{dotted!r} is not a section.key pair. Try `r.home` or `core.timeout`."
        )
    section, key = dotted.split(".", 1)
    _config.set_option(section, key, value)
    engine_registry.reset(section if section in engine_registry.names() else None)
    return str(_config.get_option(section, key))


def config_sources() -> Dict[str, Any]:
    return _config.sources()
