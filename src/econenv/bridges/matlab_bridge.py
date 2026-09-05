"""pandas ↔ MATLAB, through the Engine API rather than a file.

MATLAB's ``table`` is the right target: it carries column names, mixed types and
row order, which a bare numeric matrix does not. The Engine API will not build
one directly, so numeric columns cross as ``matlab.double`` and text as cell
arrays, and the table is assembled inside MATLAB from those.

What survives, and what is warned about, is the point of this module — a
transfer that silently turns dates into numbers is worse than one that refuses.
"""

from __future__ import annotations

import contextlib
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from ..exceptions import DataTransferError
from ..schema import ConversionReport, DatasetMetadata, Severity, describe_frame

#: MATLAB's own limit on identifier length.
_MAX_NAME = 63


def _safe_name(name: str) -> str:
    """A MATLAB-legal variable name, as close to the original as possible."""
    cleaned = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in str(name))
    if not cleaned or not cleaned[0].isalpha():
        cleaned = "v_" + cleaned
    return cleaned[:_MAX_NAME]


def push_frame(engine, name: str, df: pd.DataFrame, **kwargs: Any) -> ConversionReport:
    """Send a DataFrame into the MATLAB workspace as a ``table``."""
    if df is None or not isinstance(df, pd.DataFrame):
        raise DataTransferError("push expects a pandas DataFrame.", engine="matlab", name=name)

    import matlab

    report = ConversionReport(engine="matlab", direction="push")
    frame = df.copy()

    # An index that carries meaning becomes a column, because MATLAB tables have
    # row names but they are strings only — a DatetimeIndex would be flattened.
    if isinstance(frame.index, pd.DatetimeIndex):
        label = frame.index.name or "date"
        frame.insert(0, label, frame.index)
        report.add(
            Severity.INFO,
            f"index moved to a column named {label!r}; MATLAB tables have no date index",
        )
    elif frame.index.name and not isinstance(frame.index, pd.RangeIndex):
        frame.insert(0, frame.index.name, frame.index)
        report.add(Severity.INFO, f"index moved to a column named {frame.index.name!r}")

    columns, renamed = [], {}
    for column in frame.columns:
        safe = _safe_name(column)
        if safe != str(column):
            renamed[str(column)] = safe
        columns.append(safe)
    if renamed:
        report.add(Severity.WARNING, f"columns renamed for MATLAB: {renamed}")

    eng = engine._eng
    parts = []
    for original, safe in zip(frame.columns, columns):
        series = frame[original]
        # MATLAB identifiers must start with a letter, so the scratch name
        # cannot use a leading underscore the way a Python one would.
        holder = f"eeTmp_{safe}"
        parts.append((holder, safe))

        if pd.api.types.is_bool_dtype(series):
            eng.workspace[holder] = matlab.logical([[bool(v)] for v in series.fillna(False)])
            if series.isna().any():
                report.add(
                    Severity.WARNING,
                    f"{original!r}: MATLAB logicals cannot be missing; NaN became false",
                )

        elif pd.api.types.is_numeric_dtype(series):
            values = series.astype(float).tolist()
            eng.workspace[holder] = matlab.double([[v] for v in values])
            if pd.api.types.is_integer_dtype(series):
                report.add(
                    Severity.INFO, f"{original!r}: integers became double, as MATLAB tables prefer"
                )

        elif pd.api.types.is_datetime64_any_dtype(series):
            # ISO text, then parsed inside MATLAB, so it lands as a real datetime
            iso = series.dt.strftime("%Y-%m-%dT%H:%M:%S").fillna("").tolist()
            eng.workspace[holder] = iso
            eng.eval(
                f"{holder} = datetime({holder}, 'InputFormat', 'yyyy-MM-dd''T''HH:mm:ss');",
                nargout=0,
            )
            report.add(Severity.INFO, f"{original!r}: datetime preserved as a MATLAB datetime")

        elif isinstance(series.dtype, pd.CategoricalDtype):
            eng.workspace[holder] = [str(v) for v in series.astype(str).tolist()]
            eng.eval(f"{holder} = categorical({holder}');", nargout=0)
            report.add(Severity.INFO, f"{original!r}: pandas category became a MATLAB categorical")

        else:
            text = series.astype(str).where(series.notna(), "").tolist()
            eng.workspace[holder] = [str(v) for v in text]
            eng.eval(f"{holder} = string({holder}');", nargout=0)
            if series.isna().any():
                report.add(Severity.WARNING, f"{original!r}: missing strings became empty strings")

    # Every column must be n-by-1. Numeric ones already are; anything built from
    # a Python list arrives as a 1-by-n row, and table() rejects the mixture.
    for holder, _ in parts:
        eng.eval(f"{holder} = {holder}(:);", nargout=0)

    holders = ", ".join(holder for holder, _ in parts)
    names = ", ".join(f"'{safe}'" for _, safe in parts)
    try:
        eng.eval(f"{name} = table({holders}, 'VariableNames', {{{names}}});", nargout=0)
    except Exception as exc:
        raise DataTransferError(
            f"MATLAB could not assemble the table {name!r}: {exc}",
            engine="matlab",
            name=name,
            raw=exc,
        ) from exc
    finally:
        for holder, _ in parts:
            # Cleanup must never mask the real error above.
            with contextlib.suppress(Exception):
                eng.eval(f"clear {holder};", nargout=0)

    engine._last_frame = name
    report.emit()
    return report


def pull_frame(engine, name: str, **kwargs: Any) -> pd.DataFrame:
    """Read a MATLAB ``table`` (or numeric matrix) back into pandas."""
    eng = engine._eng
    try:
        is_table = bool(eng.eval(f"istable({name})", nargout=1))
    except Exception as exc:
        raise DataTransferError(
            f"{name!r} is not in the MATLAB workspace.", engine="matlab", name=name, raw=exc
        ) from exc

    if not is_table:
        try:
            values = np.array(eng.workspace[name], dtype=float)
        except Exception as exc:
            raise DataTransferError(
                f"{name!r} is neither a table nor a numeric matrix.",
                engine="matlab",
                name=name,
                raw=exc,
            ) from exc
        frame = pd.DataFrame(values)
        frame.attrs["econenv_metadata"] = describe_frame(frame, name=name, source_engine="matlab")
        return frame

    columns = eng.eval(f"{name}.Properties.VariableNames", nargout=1)
    labels = [str(c) for c in (columns if isinstance(columns, (list, tuple)) else [columns])]

    data: Dict[str, Any] = {}
    for label in labels:
        kind = str(eng.eval(f"class({name}.{label})", nargout=1))
        if kind in ("double", "single", "int8", "int16", "int32", "int64", "logical"):
            raw = eng.eval(f"double({name}.{label})", nargout=1)
            data[label] = np.array(raw, dtype=float).ravel()
            if kind == "logical":
                data[label] = data[label].astype(bool)
        elif kind == "datetime":
            iso = eng.eval(f"cellstr(string({name}.{label}, 'yyyy-MM-dd''T''HH:mm:ss'))", nargout=1)
            data[label] = pd.to_datetime(_as_str_list(iso), errors="coerce")
        elif kind == "categorical":
            data[label] = pd.Categorical(
                _as_str_list(eng.eval(f"cellstr({name}.{label})", nargout=1))
            )
        else:
            data[label] = _as_str_list(eng.eval(f"cellstr(string({name}.{label}))", nargout=1))

    frame = pd.DataFrame(data)
    meta: Optional[DatasetMetadata] = describe_frame(frame, name=name, source_engine="matlab")
    frame.attrs["econenv_metadata"] = meta
    return frame


def _as_str_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value]
