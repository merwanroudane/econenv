"""Layered configuration (brief §27).

Precedence, lowest to highest:

1. built-in defaults
2. the config file — ``$ECONENV_CONFIG`` or ``~/.econenv/config.toml``
3. environment variables — ``ECONENV_<SECTION>_<KEY>``
4. explicit runtime calls — :func:`set_option`, ``%econ config ...``

Nothing here hard-codes a machine-specific path. Paths come from *discovery*
(see :mod:`econenv.discovery`); this module only stores the user's overrides.
"""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any, Dict, Mapping, MutableMapping, Optional

from ._logging import get_logger
from .exceptions import ConfigurationError

try:  # Python >= 3.11
    import tomllib as _toml_reader
except ModuleNotFoundError:  # pragma: no cover - Python 3.9/3.10
    try:
        import tomli as _toml_reader  # type: ignore[no-redef]
    except ModuleNotFoundError:  # pragma: no cover
        _toml_reader = None  # type: ignore[assignment]

_log = get_logger("config")

#: Built-in defaults. Every key that may be configured must appear here, so
#: ``%econ config`` can list the full surface without guessing.
DEFAULTS: Dict[str, Dict[str, Any]] = {
    "core": {
        "log_level": "WARNING",
        "autostart": True,  # start an engine on first use instead of erroring
        "timeout": 300.0,  # seconds, per execution
    },
    "r": {
        "home": None,  # R_HOME; None -> discover
        "backend": "auto",  # auto | subprocess | rpy2
        "executable": None,  # explicit Rscript/R path
        "graphics": "svg",  # svg | png | off
        "width": 7.0,  # inches
        "height": 4.5,
        "dpi": 110,
        "transfer": "auto",  # auto | feather | csv
        "claim_r_magic": True,  # register %%R when nothing else owns it
    },
    "stata": {
        "home": None,  # STATA_HOME; None -> discover
        "edition": None,  # be | se | mp; None -> discover
        "splash": False,
        "graph_format": "svg",
        "use_official_magics": True,
    },
    "eviews": {
        "progid": "EViews.Manager",  # pin e.g. "EViews14.Manager" if needed
        "instance": "new",  # new | either | existing
        "busy_retries": 5,  # COM "EViews is currently busy" backoff attempts
        "show_window": False,
        "graphics": "png",  # png | svg | off
        "width": 6.0,
        "height": 4.0,
        "keep_temp": False,
    },
}

_ENV_PREFIX = "ECONENV_"

_runtime: Dict[str, Dict[str, Any]] = {}
_file_cache: Optional[Dict[str, Dict[str, Any]]] = None
_file_path_cache: Optional[Path] = None


# --------------------------------------------------------------------------- #
# file layer
# --------------------------------------------------------------------------- #
def config_path() -> Path:
    """Where the config file lives (it need not exist)."""
    override = os.environ.get("ECONENV_CONFIG")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".econenv" / "config.toml"


def _load_file(path: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    global _file_cache, _file_path_cache
    target = path or config_path()
    if _file_cache is not None and _file_path_cache == target:
        return _file_cache
    data: Dict[str, Dict[str, Any]] = {}
    if target.is_file():
        if _toml_reader is None:  # pragma: no cover
            _log.warning("%s found but no TOML reader available (need tomli on <3.11)", target)
        else:
            try:
                with open(target, "rb") as fh:
                    raw = _toml_reader.load(fh)
            except Exception as exc:
                raise ConfigurationError(f"Could not parse {target}: {exc}") from exc
            for section, values in raw.items():
                if isinstance(values, Mapping):
                    data[section] = dict(values)
    _file_cache, _file_path_cache = data, target
    return data


def reload() -> None:
    """Forget the cached config file so the next read picks up edits."""
    global _file_cache, _file_path_cache
    _file_cache = None
    _file_path_cache = None


# --------------------------------------------------------------------------- #
# env layer
# --------------------------------------------------------------------------- #
def _coerce(value: str, reference: Any) -> Any:
    """Cast an environment string to the type of the corresponding default."""
    if isinstance(reference, bool):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(reference, float):
        return float(value)
    if isinstance(reference, int):
        return int(value)
    return value


def _env_layer() -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for section, keys in DEFAULTS.items():
        for key, default in keys.items():
            name = f"{_ENV_PREFIX}{section.upper()}_{key.upper()}"
            if name in os.environ:
                try:
                    out.setdefault(section, {})[key] = _coerce(os.environ[name], default)
                except ValueError as exc:
                    raise ConfigurationError(
                        f"{name}={os.environ[name]!r} is not valid: {exc}"
                    ) from exc
    # Conventional aliases people already have set.
    for alias, (section, key) in {
        "R_HOME": ("r", "home"),
        "STATA_HOME": ("stata", "home"),
        "ECONENV_LOG_LEVEL": ("core", "log_level"),
    }.items():
        if alias in os.environ and key not in out.get(section, {}):
            out.setdefault(section, {})[key] = os.environ[alias]
    return out


# --------------------------------------------------------------------------- #
# public API
# --------------------------------------------------------------------------- #
def _merge(*layers: Mapping[str, Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    for layer in layers:
        for section, values in layer.items():
            target: MutableMapping[str, Any] = merged.setdefault(section, {})
            for key, value in values.items():
                target[key] = value
    return merged


def as_dict() -> Dict[str, Dict[str, Any]]:
    """The fully resolved configuration, all layers applied."""
    return _merge(copy.deepcopy(DEFAULTS), _load_file(), _env_layer(), _runtime)


def get_option(section: str, key: str, default: Any = None) -> Any:
    """Read one resolved option."""
    return as_dict().get(section, {}).get(key, default)


def section(name: str) -> Dict[str, Any]:
    """Read a whole resolved section."""
    return as_dict().get(name, {})


def set_option(section_name: str, key: str, value: Any) -> None:
    """Set a runtime override — the highest-precedence layer.

    Unknown keys are rejected rather than silently stored, so a typo in
    ``%econ config`` is caught immediately.
    """
    if section_name not in DEFAULTS:
        raise ConfigurationError(
            f"Unknown config section {section_name!r}. Known: {', '.join(sorted(DEFAULTS))}"
        )
    if key not in DEFAULTS[section_name]:
        known = ", ".join(sorted(DEFAULTS[section_name]))
        raise ConfigurationError(f"Unknown option {section_name}.{key!r}. Known: {known}")
    reference = DEFAULTS[section_name][key]
    if isinstance(value, str) and reference is not None:
        value = _coerce(value, reference)
    _runtime.setdefault(section_name, {})[key] = value
    _log.debug("runtime config %s.%s set", section_name, key)


def reset(section_name: Optional[str] = None) -> None:
    """Drop runtime overrides for one section, or all of them."""
    if section_name is None:
        _runtime.clear()
    else:
        _runtime.pop(section_name, None)


def sources() -> Dict[str, Any]:
    """Report which layers are contributing — used by ``%econ config`` and doctor."""
    path = config_path()
    return {
        "defaults": True,
        "file": str(path) if path.is_file() else None,
        "env": sorted(
            name
            for name in os.environ
            if name.startswith(_ENV_PREFIX) or name in {"R_HOME", "STATA_HOME"}
        ),
        "runtime": {s: sorted(v) for s, v in _runtime.items() if v},
    }
