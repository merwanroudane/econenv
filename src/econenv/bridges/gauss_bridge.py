"""pandas ↔ GAUSS.

GAUSS's native container is the numeric matrix: no column names, no mixed types,
no dates. A DataFrame is therefore *not* a lossless fit, and the honest design
is to say what was dropped rather than to invent a representation.

So a frame crosses as a numeric matrix plus a schema kept on the Python side:

* numeric columns cross as they are;
* booleans become 1/0, which GAUSS uses for logicals anyway;
* datetimes cross as a numeric column and are named in the report;
* text columns cannot cross at all and are reported by name, not silently
  dropped or coerced to codes that would look like data.

``csvWriteM`` and ``csvReadM`` carry the numbers — verified against GAUSS 26.1.1
— because a text file is the only interchange the CLI backend can use, and it
keeps full double precision when written with enough digits.

Missing values survive: GAUSS has a real missing value (``miss``/``ismiss``), so
NaN goes in as missing and comes back as NaN rather than as a sentinel number
that would quietly enter a regression.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, List, Optional

import numpy as np
import pandas as pd

from ..exceptions import DataTransferError
from ..schema import ConversionReport, Severity, describe_frame

#: GAUSS type codes, from ``type()``. Verified: 6 is a matrix, 13 a string.
TYPE_MATRIX = 6
TYPE_STRING = 13

#: Digits written to the exchange file. 17 round-trips an IEEE double exactly.
_DIGITS = 17


def _helper() -> str:
    """The GAUSS procedures the transfer needs, inlined into each program.

    Inlined rather than ``#include``d so the user's ``src_path`` cannot break
    it, and read from the package so the GAUSS source lives in a ``.gss`` file
    that a GAUSS programmer can actually read.
    """
    global _HELPER_CACHE
    if _HELPER_CACHE is None:
        resource = (
            Path(__file__).resolve().parents[1] / "resources" / "gauss" / "econenv_bridge.gss"
        )
        _HELPER_CACHE = resource.read_text(encoding="utf-8")
    return _HELPER_CACHE


_HELPER_CACHE: Optional[str] = None


def _gauss_path(path: Path) -> str:
    """A path GAUSS reads correctly — backslashes are escapes in its strings."""
    return str(path).replace("\\", "/")


def _session(engine) -> Path:
    """The backend's scratch directory, which both sides can see."""
    backend = engine._backend
    if backend is None:
        raise DataTransferError(
            "GAUSS is not started.", engine="gauss", hint="Run a cell first, or %econ start gauss."
        )
    return backend.session


def _persist(engine, name: str) -> str:
    """The GAUSS line that makes *name* available to the next cell.

    Stated explicitly for each pushed value rather than inferred by scanning
    the program for assignments: the transfer programs define helper
    procedures, and a scan cannot tell a procedure's local from a variable the
    user will want back.
    """
    return f'save path="{_gauss_path(_session(engine))}" {name};'


def _run(engine, code: str) -> str:
    """Run helper code, raising a data error rather than an execution one.

    ``carry=False``: these programs define procedures, and the cross-cell save
    logic would try to persist their locals.
    """
    text, error = engine._backend.execute(code, carry=False)
    if error:
        raise DataTransferError(error, engine="gauss")
    return text


# --------------------------------------------------------------------------- #
# frames
# --------------------------------------------------------------------------- #
def push_frame(engine, name: str, df: pd.DataFrame, **kwargs: Any) -> ConversionReport:
    """Send a DataFrame into GAUSS as a numeric matrix."""
    if df is None or not isinstance(df, pd.DataFrame):
        raise DataTransferError("push expects a pandas DataFrame.", engine="gauss", name=name)

    report = ConversionReport(engine="gauss", direction="push")
    frame = df.copy()

    if isinstance(frame.index, pd.DatetimeIndex):
        label = frame.index.name or "date"
        frame.insert(0, label, frame.index)
        report.add(
            Severity.INFO,
            f"index moved to a column named {label!r}; a GAUSS matrix has no index",
        )

    numeric = pd.DataFrame(index=frame.index)
    dropped: List[str] = []
    for column in frame.columns:
        series = frame[column]
        if pd.api.types.is_bool_dtype(series):
            numeric[column] = series.astype(float)
            report.add(Severity.INFO, f"{column!r}: booleans became 1/0")
        elif pd.api.types.is_numeric_dtype(series):
            numeric[column] = series.astype(float)
        elif pd.api.types.is_datetime64_any_dtype(series):
            numeric[column] = series.view("int64") / 1e9
            report.add(
                Severity.WARNING,
                f"{column!r}: datetime became seconds since 1970; GAUSS has no date type",
            )
        else:
            dropped.append(str(column))

    if dropped:
        # Named, not silently removed. A regression run on a frame that lost a
        # column without saying so is the worst outcome available here.
        report.add(
            Severity.WARNING,
            f"columns GAUSS cannot hold in a numeric matrix were not sent: {dropped}. "
            "Encode them as numbers in pandas first if you need them.",
        )
    if numeric.empty or not len(numeric.columns):
        raise DataTransferError(
            f"{name!r} has no numeric columns, and a GAUSS matrix holds only numbers.",
            engine="gauss",
            name=name,
            hint="Encode the columns you need as numbers before pushing.",
        )

    exchange = _session(engine) / f"{name}__push.csv"
    numeric.to_csv(exchange, index=False, header=False, na_rep="", float_format=f"%.{_DIGITS}g")

    # csvReadM reads the numbers; the empty fields become GAUSS missing values,
    # which is what NaN means and what packr/ismiss understand.
    _run(
        engine,
        f'{name} = csvReadM("{_gauss_path(exchange)}");\n' + _persist(engine, name),
    )
    engine._backend.remember(name, "matrix")

    # The column names live on the Python side, since the matrix cannot hold them.
    engine._frame_columns = getattr(engine, "_frame_columns", {})
    engine._frame_columns[name] = [str(c) for c in numeric.columns]
    report.emit()
    return report


def pull_frame(engine, name: str, **kwargs: Any) -> pd.DataFrame:
    """Read a GAUSS matrix back as a DataFrame."""
    values = pull_matrix(engine, name)
    if values.ndim == 1:
        values = values.reshape(-1, 1)

    known = getattr(engine, "_frame_columns", {}).get(name)
    if known and len(known) == values.shape[1]:
        columns = known
    else:
        # A matrix GAUSS built itself has no names, and inventing meaningful
        # ones would be a lie; positions are at least honest.
        columns = [str(i) for i in range(values.shape[1])]

    frame = pd.DataFrame(values, columns=columns)
    frame.attrs["econenv_metadata"] = describe_frame(frame, name=name, source_engine="gauss")
    return frame


# --------------------------------------------------------------------------- #
# matrices and scalars
# --------------------------------------------------------------------------- #
def pull_matrix(engine, name: str) -> np.ndarray:
    """A GAUSS matrix as a NumPy array, through a full-precision CSV."""
    exchange = _session(engine) / f"{name}__pull.csv"
    exchange.unlink(missing_ok=True)
    _run(
        engine,
        _helper() + f'\neconenv_write({name}, "{_gauss_path(exchange)}");',
    )
    if not exchange.exists():
        raise DataTransferError(
            f"GAUSS did not write {name!r} out; it may not be a numeric matrix.",
            engine="gauss",
            name=name,
            hint=f"Check its type with:  print type({name});   /* 6 is a matrix */",
        )

    rows: List[List[float]] = []
    with exchange.open(newline="", encoding="utf-8") as handle:
        for record in csv.reader(handle):
            if not record:
                continue
            rows.append([_to_float(cell) for cell in record])
    exchange.unlink(missing_ok=True)

    array = np.array(rows, dtype=float)
    if array.ndim == 2 and 1 in array.shape:
        # GAUSS has no 1-D array either, so a vector arrives as n x 1 or 1 x n.
        return array.ravel()
    return array


def _to_float(cell: str) -> float:
    """A CSV field as a number, with GAUSS's missing value becoming NaN."""
    text = cell.strip()
    if not text or text in (".", "-", "NA"):
        return float("nan")
    try:
        return float(text)
    except ValueError:
        return float("nan")


#: Names GAUSS already uses for built-ins. Assigning to one is a compile
#: error (G0276), and `vec` in particular is a name a researcher reaches for.
#: This is not the whole list — GAUSS reports the rest itself, and the backend
#: turns that report into a message that names the collision.
COMMON_BUILTINS = frozenset(
    {
        "vec",
        "vecr",
        "ones",
        "zeros",
        "eye",
        "rows",
        "cols",
        "sumc",
        "meanc",
        "stdc",
        "minc",
        "maxc",
        "det",
        "inv",
        "invpd",
        "chol",
        "diag",
        "seqa",
        "rndn",
        "rndu",
        "trim",
        "sortc",
        "counts",
        "recode",
        "date",
        "time",
        "print",
        "format",
        "let",
        "load",
        "save",
        "type",
        "miss",
        "packr",
    }
)


def push_value(engine, name: str, obj: Any) -> None:
    """Send a scalar, vector, matrix or string into the GAUSS workspace."""
    if name.lower() in COMMON_BUILTINS:
        raise DataTransferError(
            f"{name!r} is the name of a GAUSS built-in, so GAUSS will not let a variable take it.",
            engine="gauss",
            name=name,
            hint=f"Send it under another name:  econenv.push('gauss', 'my_{name}', {name})",
        )
    if obj is None:
        raise DataTransferError(
            "GAUSS has no equivalent of None.",
            engine="gauss",
            name=name,
            hint="Use float('nan'), which becomes a GAUSS missing value.",
        )

    if isinstance(obj, str):
        escaped = obj.replace('"', '\\"')
        _run(engine, f'{name} = "{escaped}";\n' + _persist(engine, name))
        engine._backend.remember(name, "string")
        return

    if isinstance(obj, (bool, np.bool_)):
        _run(engine, f"{name} = {1 if obj else 0};\n" + _persist(engine, name))
        engine._backend.remember(name, "matrix")
        return

    if isinstance(obj, (int, float, np.integer, np.floating)):
        _run(engine, f"{name} = {_literal(float(obj))};\n" + _persist(engine, name))
        engine._backend.remember(name, "matrix")
        return

    if isinstance(obj, pd.Series):
        obj = obj.to_numpy()
    elif isinstance(obj, (list, tuple)):
        obj = np.asarray(obj)

    if isinstance(obj, pd.DataFrame):
        push_frame(engine, name, obj)
        return

    if isinstance(obj, np.ndarray):
        array = np.asarray(obj, dtype=float)
        if array.ndim > 2:
            raise DataTransferError(
                f"{name!r} has {array.ndim} dimensions; a GAUSS matrix is 2-D.",
                engine="gauss",
                name=name,
                hint="Reshape it in Python first.",
            )
        if array.ndim == 0:
            _run(engine, f"{name} = {_literal(float(array))};\n" + _persist(engine, name))
        else:
            frame = pd.DataFrame(array if array.ndim == 2 else array.reshape(-1, 1))
            exchange = _session(engine) / f"{name}__push.csv"
            frame.to_csv(
                exchange, index=False, header=False, na_rep="", float_format=f"%.{_DIGITS}g"
            )
            _run(
                engine,
                f'{name} = csvReadM("{_gauss_path(exchange)}");\n' + _persist(engine, name),
            )
        engine._backend.remember(name, "matrix")
        return

    raise DataTransferError(
        f"EconEnv cannot send a {type(obj).__name__} to GAUSS.",
        engine="gauss",
        name=name,
        hint="Supported: numbers, bool, str, list/tuple, NumPy array, Series, DataFrame.",
    )


def _literal(value: float) -> str:
    """A GAUSS numeric literal, including its missing value."""
    if np.isnan(value):
        return "miss(0, 0)"
    if np.isinf(value):
        return "1e308" if value > 0 else "-1e308"
    return repr(value)


def pull_value(engine, name: str, **kwargs: Any) -> Any:
    """Read a GAUSS symbol back as its natural Python type.

    =====================  ==============================
    GAUSS                  Python
    =====================  ==============================
    scalar matrix (1x1)    ``float``
    row or column vector   1-D ``numpy.ndarray``
    matrix                 2-D ``numpy.ndarray``
    string                 ``str``
    =====================  ==============================
    """
    kind = _type_of(engine, name)
    if kind == TYPE_STRING:
        return _read_string(engine, name)
    if kind == TYPE_MATRIX:
        array = pull_matrix(engine, name)
        if array.size == 1:
            return float(array.ravel()[0])
        return array
    raise DataTransferError(
        f"{name!r} is a GAUSS type EconEnv cannot convert (type code {kind}).",
        engine="gauss",
        name=name,
        hint="Matrices and strings cross; convert other types in GAUSS first.",
    )


def _type_of(engine, name: str) -> int:
    """``type(name)`` in GAUSS, or a clear error if the symbol is absent."""
    text, error = engine._backend.execute(f'print "__ECONENV_TYPE2__ " type({name});', carry=False)
    if error:
        raise DataTransferError(
            f"{name!r} is not in the GAUSS workspace.",
            engine="gauss",
            name=name,
            hint="Check the spelling, and that the cell creating it ran without error.",
        )
    for token in text.replace("__ECONENV_TYPE2__", "").split():
        try:
            return int(float(token))
        except ValueError:
            continue
    return -1


def _read_string(engine, name: str) -> str:
    exchange = _session(engine) / f"{name}__str.txt"
    exchange.unlink(missing_ok=True)
    _run(
        engine,
        _helper() + f'\neconenv_write_string({name}, "{_gauss_path(exchange)}");',
    )
    if not exchange.exists():
        raise DataTransferError(
            f"GAUSS could not write the string {name!r} out.", engine="gauss", name=name
        )
    text = exchange.read_text(encoding="utf-8", errors="replace").rstrip("\n")
    exchange.unlink(missing_ok=True)
    return text


def evaluate(engine, expression: str) -> Any:
    """The value of a GAUSS expression, as a number where it is one."""
    text, error = engine._backend.execute(f'print "__ECONENV_EVAL__ " ({expression});', carry=False)
    if error:
        raise DataTransferError(error, engine="gauss")
    payload = text.replace("__ECONENV_EVAL__", "").strip()
    try:
        return float(payload.split()[0])
    except (ValueError, IndexError):
        return payload


def columns_of(engine, name: str) -> Optional[List[str]]:
    """The column names EconEnv remembers for a pushed frame, if any."""
    return getattr(engine, "_frame_columns", {}).get(name)
