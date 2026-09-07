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


# --------------------------------------------------------------------------- #
# typed transfer, for values that are not tables
# --------------------------------------------------------------------------- #
# `pull_frame` answers "give me this as a DataFrame", which is the right
# contract for `econenv.pull` and for moving data between engines. It is the
# wrong contract for `%%matlab -o y` where `y = 10`: a scalar is not a frame,
# and forcing it through pandas produced `ValueError: Must pass 2-d input.
# shape=()` — an error raised inside pandas that says nothing about MATLAB.
#
# So the typed path below is separate and explicit. What each MATLAB class
# becomes in Python is documented in docs/engines/matlab.md and tested; nothing
# here guesses.

#: MATLAB classes that carry numbers.
_NUMERIC = {
    "double",
    "single",
    "int8",
    "int16",
    "int32",
    "int64",
    "uint8",
    "uint16",
    "uint32",
    "uint64",
}

#: MATLAB integer classes, which come back as Python ``int`` rather than float.
_INTEGER = {"int8", "int16", "int32", "int64", "uint8", "uint16", "uint32", "uint64"}


def _matlab_class(eng, name: str) -> str:
    """The MATLAB class of *name*, or raise if it is not in the workspace."""
    try:
        exists = bool(eng.eval("exist('" + name + "', 'var')", nargout=1))
    except Exception as exc:  # a malformed name, mostly
        raise DataTransferError(
            f"MATLAB could not inspect {name!r}: {exc}", engine="matlab", name=name, raw=exc
        ) from exc
    if not exists:
        raise DataTransferError(
            f"{name!r} is not in the MATLAB workspace.",
            engine="matlab",
            name=name,
            hint="Check the spelling, and that the cell creating it ran without error.",
        )
    return str(eng.eval(f"class({name})", nargout=1))


def pull_value(engine, name: str, **kwargs: Any) -> Any:
    """Read any MATLAB variable back into its natural Python type.

    ===========================  =========================================
    MATLAB                       Python
    ===========================  =========================================
    numeric scalar               ``float`` (``int`` for integer classes)
    complex scalar               ``complex``
    logical scalar               ``bool``
    ``char`` / ``string`` scalar ``str``
    row or column vector         1-D ``numpy.ndarray``
    2-D matrix                   2-D ``numpy.ndarray``
    ``string`` array / cellstr   ``list`` of ``str``
    ``table`` / ``timetable``    ``pandas.DataFrame``
    ===========================  =========================================

    A vector comes back 1-D whichever way it was oriented in MATLAB, because
    ``[1 2 3]`` and ``[1;2;3]`` are the same three numbers to a researcher and
    the orientation is a MATLAB storage detail. Reshape in MATLAB when the
    orientation is itself the result.
    """
    eng = engine._eng
    kind = _matlab_class(eng, name)

    if kind in ("table", "timetable"):
        return pull_frame(engine, name, **kwargs)

    if kind == "char":
        return str(eng.workspace[name])

    if kind == "string":
        if bool(eng.eval(f"isscalar({name})", nargout=1)):
            return str(eng.eval(f"char({name})", nargout=1))
        return _as_str_list(eng.eval(f"cellstr({name}(:))", nargout=1))

    if kind == "cell":
        if bool(eng.eval(f"iscellstr({name})", nargout=1)):
            return _as_str_list(eng.eval(f"{name}(:)", nargout=1))
        raise DataTransferError(
            f"{name!r} is a MATLAB cell array of mixed types, which has no single "
            "Python equivalent.",
            engine="matlab",
            name=name,
            hint="Convert it in MATLAB first — cell2table, string(), or index the elements.",
        )

    if kind == "logical":
        raw = np.array(eng.workspace[name], dtype=bool)
        return bool(raw.ravel()[0]) if raw.size == 1 else _shaped(raw)

    if kind in _NUMERIC:
        return _numeric_value(eng, name, kind)

    raise DataTransferError(
        f"{name!r} is a MATLAB {kind}, which EconEnv cannot convert to Python.",
        engine="matlab",
        name=name,
        hint=(
            "Convert it in MATLAB first: struct2table for a struct, a table for mixed "
            "columns, or pull the fields you need one at a time."
        ),
    )


def _numeric_value(eng, name: str, kind: str) -> Any:
    """A numeric MATLAB variable as a scalar, 1-D array or 2-D array."""
    complex_valued = bool(eng.eval(f"isreal({name}) == 0", nargout=1))
    array = np.array(eng.workspace[name], dtype=complex if complex_valued else float)

    if array.size == 1:
        value = array.ravel()[0]
        if complex_valued:
            return complex(value)
        return int(value) if kind in _INTEGER else float(value)

    if kind in _INTEGER and not complex_valued:
        array = array.astype(np.int64)
    return _shaped(array)


def _shaped(array: np.ndarray) -> np.ndarray:
    """A MATLAB array with its Python shape: vectors flat, matrices as they are.

    MATLAB has no 1-D array — ``[1 2 3]`` is 1x3 and ``[1;2;3]`` is 3x1 — so
    keeping the singleton axis would hand Python a ``(1, 3)`` array for
    something every researcher reads as three numbers.
    """
    if array.ndim == 2 and 1 in array.shape:
        return array.ravel()
    return array


def push_value(engine, name: str, obj: Any, orientation: str = "column") -> None:
    """Send any supported Python value into the MATLAB workspace under *name*.

    ==============================  ===========================================
    Python                          MATLAB
    ==============================  ===========================================
    ``bool`` / ``numpy.bool_``      ``logical``
    ``int`` / ``float`` / NumPy     ``double``
    ``complex``                     complex ``double``
    ``str``                         ``char``
    list, tuple, 1-D array          ``double`` column (see *orientation*)
    2-D array                       ``double``, shape preserved
    list of ``str``                 ``string`` array
    ==============================  ===========================================

    The previous implementation called ``float(obj)`` on everything that was not
    a DataFrame, so a list, a tuple or any NumPy array with ``ndim > 0`` raised
    a ``TypeError`` from the float constructor instead of being converted.
    """
    import matlab

    eng = engine._eng

    if obj is None:
        raise DataTransferError(
            "MATLAB has no equivalent of None.",
            engine="matlab",
            name=name,
            hint="Use float('nan') for a missing number, or an empty list for [].",
        )

    if isinstance(obj, str):
        escaped = obj.replace("'", "''")
        eng.eval(f"{name} = '{escaped}';", nargout=0)
        return

    # bool before int: bool is a subclass of int, and MATLAB distinguishes them.
    if isinstance(obj, (bool, np.bool_)):
        eng.workspace[name] = matlab.logical([[bool(obj)]])
        eng.eval(f"{name} = {name}(1);", nargout=0)
        return

    if isinstance(obj, (int, float, np.integer, np.floating)):
        eng.workspace[name] = float(obj)
        return

    if isinstance(obj, (complex, np.complexfloating)):
        eng.workspace[name] = complex(obj)
        return

    if isinstance(obj, pd.Series):
        obj = obj.to_numpy()
    elif isinstance(obj, (list, tuple)):
        if len(obj) and all(isinstance(v, str) for v in obj):
            eng.workspace[name] = [str(v) for v in obj]
            eng.eval(f"{name} = string({name}(:));", nargout=0)
            return
        obj = np.asarray(obj)

    if isinstance(obj, np.ndarray):
        _push_array(eng, matlab, name, obj, orientation)
        return

    raise DataTransferError(
        f"EconEnv cannot send a {type(obj).__name__} to MATLAB.",
        engine="matlab",
        name=name,
        hint=(
            "Supported: numbers, bool, str, list/tuple, NumPy array, pandas Series and DataFrame."
        ),
    )


def _push_array(eng, matlab, name: str, array: np.ndarray, orientation: str) -> None:
    """A NumPy array as a MATLAB matrix, with the shape rules stated."""
    if array.ndim > 2:
        raise DataTransferError(
            f"{name!r} has {array.ndim} dimensions; MATLAB matrices here are 2-D.",
            engine="matlab",
            name=name,
            hint="Reshape it in Python first, or send each 2-D slice separately.",
        )

    if array.ndim == 0:
        eng.workspace[name] = float(array)
        return

    if array.dtype == bool:
        rows = [[bool(v)] for v in array.ravel()] if array.ndim == 1 else array.tolist()
        eng.workspace[name] = matlab.logical(rows)
    elif array.dtype.kind in "US":
        eng.workspace[name] = [str(v) for v in array.ravel().tolist()]
        eng.eval(f"{name} = string({name}(:));", nargout=0)
        return
    elif array.dtype.kind == "c":
        values = array.astype(complex)
        rows = [[complex(v)] for v in values] if values.ndim == 1 else values.tolist()
        eng.workspace[name] = matlab.double(rows, is_complex=True)
    else:
        values = array.astype(float)
        rows = [[float(v)] for v in values] if values.ndim == 1 else values.tolist()
        eng.workspace[name] = matlab.double(rows)

    # A 1-D sequence lands as a column by default: that is the orientation a
    # MATLAB table column, a regressor and a time series all already use.
    if array.ndim == 1 and orientation == "row":
        eng.eval(f"{name} = {name}.';", nargout=0)
