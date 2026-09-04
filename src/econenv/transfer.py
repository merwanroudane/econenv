"""The unified data bridge (brief §10) and provenance (brief §20, §21).

One DataFrame, created once in Python, moved to any engine — and between any two
engines — without an export/import round of CSV files. :func:`move` routes
through pandas because pandas is the canonical interchange object; the point is
that the *user* never writes a file.

:func:`snapshot` records what produced a result, and :func:`provenance` hashes
the code and the data so a run can be identified later.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import platform
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from . import discovery
from ._logging import get_logger
from ._version import __version__
from .engines import registry as engine_registry
from .schema import ConversionReport, DatasetMetadata, describe_frame

_log = get_logger("transfer")


def push(engine: str, name: str, obj: Any, **kwargs: Any) -> None:
    """Send *obj* into *engine* under *name*."""
    engine_registry.get(engine).push(name, obj, **kwargs)


def pull(engine: str, name: Optional[str] = None, **kwargs: Any) -> Any:
    """Bring an object back out of *engine*."""
    return engine_registry.get(engine).pull(name, **kwargs)


def move(
    source: str,
    target: str,
    name: str,
    *,
    target_name: Optional[str] = None,
    **kwargs: Any,
) -> pd.DataFrame:
    """Move a dataset directly from one engine to another.

    Returns the pandas frame that passed through, so the conversion notes from
    both legs stay inspectable.
    """
    frame = pull(source, name, **kwargs)
    if not isinstance(frame, pd.DataFrame):
        frame = pd.DataFrame(frame)
    push(target, target_name or name, frame)
    meta = frame.attrs.get("econenv_metadata")
    if isinstance(meta, DatasetMetadata):
        meta.record(f"{source} -> python -> {target}")
    return frame


def conversion_report(frame: pd.DataFrame) -> Optional[ConversionReport]:
    """The conversion notes attached to *frame*, if any."""
    report = frame.attrs.get("econenv_conversion")
    return report if isinstance(report, ConversionReport) else None


def metadata(frame: pd.DataFrame) -> Optional[DatasetMetadata]:
    meta = frame.attrs.get("econenv_metadata")
    return meta if isinstance(meta, DatasetMetadata) else None


def annotate(
    frame: pd.DataFrame,
    *,
    name: Optional[str] = None,
    time_var: Optional[str] = None,
    panel_var: Optional[str] = None,
    frequency: Optional[str] = None,
) -> pd.DataFrame:
    """Attach or update :class:`DatasetMetadata` on *frame* (brief §12)."""
    meta = metadata(frame) or describe_frame(frame, name=name)
    if name:
        meta.name = name
    if time_var:
        meta.time_var = time_var
    if panel_var:
        meta.panel_var = panel_var
    if frequency:
        meta.frequency = frequency
    frame.attrs["econenv_metadata"] = meta
    return frame


# --------------------------------------------------------------------------- #
# reproducibility
# --------------------------------------------------------------------------- #
def snapshot(*, include_packages: bool = True, deep: bool = False) -> Dict[str, Any]:
    """A record of the whole environment (brief §20).

    ``deep=True`` starts each available engine to read its true version;
    otherwise only what is already running reports one.
    """
    from .engines.python_engine import PythonEngine

    engines: Dict[str, Any] = {}
    for engine in engine_registry.all_engines():
        info = engine.info()
        entry = info.to_dict()
        if deep and engine.available and not engine.running:
            try:
                engine.start()
                entry["version"] = engine.version()
            except Exception as exc:
                entry["error"] = f"{type(exc).__name__}: {exc}"
        engines[engine.name] = entry

    python_engine = engine_registry.get("python")
    assert isinstance(python_engine, PythonEngine)

    out: Dict[str, Any] = {
        "econenv_version": __version__,
        "timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "host": discovery.host_info(),
        "engines": engines,
    }
    if include_packages:
        out["python_packages"] = python_engine.all_packages()
        r_engine = engine_registry.get("r")
        if r_engine.running:
            try:
                out["r_packages"] = r_engine.r_packages()  # type: ignore[attr-defined]
            except Exception as exc:
                _log.debug("R package listing failed: %s", exc)
    return out


def save_snapshot(path: Union[str, Path], **kwargs: Any) -> Path:
    """Write :func:`snapshot` to a JSON file."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(snapshot(**kwargs), indent=2, default=str), encoding="utf-8")
    return target


def hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()[:16]


def hash_frame(df: pd.DataFrame) -> str:
    """A stable content hash of a DataFrame, for provenance records."""
    try:
        digest = pd.util.hash_pandas_object(df, index=True).to_numpy().tobytes()
    except TypeError:  # object columns pandas will not hash
        digest = df.astype(str).to_csv(index=True).encode("utf-8")
    header = ",".join(f"{c}:{df[c].dtype}" for c in df.columns).encode("utf-8")
    return hashlib.sha256(header + digest).hexdigest()[:16]


def provenance(
    *,
    engine: str,
    code: str,
    data: Optional[pd.DataFrame] = None,
    elapsed: Optional[float] = None,
) -> Dict[str, Any]:
    """A provenance record for one execution (brief §21)."""
    instance = engine_registry.get(engine)
    return {
        "engine": engine,
        "engine_version": instance.version() if instance.running else instance.info().version,
        "econenv_version": __version__,
        "code_sha256_16": hash_code(code),
        "data_sha256_16": hash_frame(data) if data is not None else None,
        "n_obs": None if data is None else len(data),
        "timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "duration_seconds": elapsed,
        "host": platform.node(),
        "platform": platform.platform(),
    }


def dataset_report(frame: pd.DataFrame) -> List[str]:
    """Human-readable summary of a frame's metadata and conversion history."""
    lines: List[str] = []
    meta = metadata(frame)
    if meta:
        lines.append(f"source engine: {meta.source_engine or 'python'}")
        if meta.time_var:
            lines.append(f"time variable: {meta.time_var}")
        if meta.panel_var:
            lines.append(f"panel variable: {meta.panel_var}")
        if meta.frequency:
            lines.append(f"frequency: {meta.frequency}")
        lines += [f"history: {event}" for event in meta.history]
    report = conversion_report(frame)
    if report:
        lines.append(str(report))
    return lines
