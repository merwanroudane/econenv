"""pandas <-> Stata, through PyStata's own data API.

PyStata already exposes ``pdataframe_to_data`` / ``pdataframe_from_data`` and
they handle Stata's storage types properly, so this module does not re-encode
anything. Its job is the layer PyStata does not cover: reporting what the
transfer cost.

Two Stata facts drive the conversion report:

* Stata variable names are limited to 32 characters and to
  ``[A-Za-z_][A-Za-z0-9_]*``; anything else is renamed, and the rename is
  reported rather than done quietly.
* Stata has 27 *extended* missing values (``.a`` … ``.z`` plus ``.``). pandas has
  one ``NaN``. Pulling data therefore collapses them, and that is stated
  explicitly instead of being discovered later.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from ..exceptions import DataTransferError
from ..schema import (
    ConversionReport,
    LogicalType,
    Severity,
    describe_frame,
    logical_type_of,
)

# fmt: off
#: Names Stata will not accept as a variable.
STATA_RESERVED = {
    "_all", "_b", "byte", "_coef", "_cons", "double", "float", "if", "in",
    "int", "long", "_n", "_N", "_pi", "_pred", "_rc", "_skip", "str", "using", "with",
}
# fmt: on
_VALID_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,31}$")
#: A Stata stored-result reference such as ``e(b)`` or ``r(table)``.
_RESULT_REF = re.compile(r"^([ers])\(([A-Za-z_][A-Za-z0-9_]*)\)$")
MAX_STR_LEN = 2045  # str# limit before Stata promotes to strL


def sanitise_name(name: str, taken: Optional[set] = None) -> str:
    """Return a Stata-legal variable name derived from *name*."""
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", str(name))
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"v_{cleaned}"
    cleaned = cleaned[:32]
    if cleaned.lower() in STATA_RESERVED:
        cleaned = f"{cleaned}_"[:32]
    if taken is not None:
        base, suffix = cleaned, 1
        while cleaned.lower() in taken:
            tail = f"_{suffix}"
            cleaned = base[: 32 - len(tail)] + tail
            suffix += 1
        taken.add(cleaned.lower())
    return cleaned


def prepare(df: pd.DataFrame, report: ConversionReport) -> pd.DataFrame:
    """Make *df* acceptable to Stata, recording every change in *report*."""
    out = df.copy()

    if not isinstance(out.index, pd.RangeIndex):
        index_frame = out.index.to_frame(index=False)
        index_frame.columns = [
            str(c) if c is not None else f"index_{i}" for i, c in enumerate(index_frame.columns)
        ]
        out = pd.concat([index_frame, out.reset_index(drop=True)], axis=1)
        report.add(
            Severity.INFO,
            f"index moved into column(s) {list(index_frame.columns)} — "
            "Stata datasets have no index",
        )

    taken: set = set()
    renames: Dict[str, str] = {}
    for column in out.columns:
        safe = sanitise_name(column, taken)
        if safe != str(column):
            renames[column] = safe
    if renames:
        out = out.rename(columns=renames)
        for original, new in renames.items():
            report.add(
                Severity.WARNING,
                f"renamed to {new!r} for Stata",
                column=str(original),
                detail="Stata names: <=32 chars, letters/digits/underscore, no reserved words.",
            )

    for column in out.columns:
        series = out[column]
        ltype = logical_type_of(series)

        if ltype is LogicalType.CATEGORICAL:
            # PyStata cannot take a pandas Categorical directly; send the labels
            # and say so, so nobody assumes value labels survived.
            out[column] = series.astype(object).where(series.notna(), None)
            report.add(
                Severity.WARNING,
                "categorical sent as a string column; Stata value labels are not created",
                column=str(column),
                detail=f"categories: {list(series.cat.categories)[:10]}",
            )
        elif ltype is LogicalType.BOOLEAN:
            out[column] = series.astype("float64")
            report.add(
                Severity.INFO,
                "boolean stored as 0/1 (Stata has no logical type)",
                column=str(column),
            )
        elif ltype is LogicalType.DATETIME:
            tz = getattr(series.dtype, "tz", None)
            values = series.dt.tz_convert("UTC").dt.tz_localize(None) if tz else series
            # Stata %tc is milliseconds since 1960-01-01.
            epoch = pd.Timestamp("1960-01-01")
            out[column] = (values - epoch).dt.total_seconds() * 1000.0
            report.add(
                Severity.WARNING,
                "datetime converted to Stata %tc (ms since 1960-01-01); "
                "apply `format ... %tc` in Stata to display it as a date",
                column=str(column),
                detail=f"timezone {tz} dropped" if tz else None,
            )
        elif ltype is LogicalType.STRING:
            lengths = series.dropna().astype(str).str.len()
            if len(lengths) and lengths.max() > MAX_STR_LEN:
                report.add(
                    Severity.WARNING,
                    f"strings up to {int(lengths.max())} characters will become strL",
                    column=str(column),
                )
        elif ltype is LogicalType.UNSUPPORTED:
            raise DataTransferError(
                f"dtype {series.dtype} has no Stata equivalent",
                engine="stata",
                name=str(column),
                hint="Cast the column to a numeric, string, boolean or datetime dtype first.",
            )
    return out


def push_frame(
    engine, name: str, df: pd.DataFrame, *, clear: bool = True, **kwargs: Any
) -> ConversionReport:
    """Load *df* into Stata's dataset in memory.

    Stata holds one dataset per frame, so *name* becomes the Stata **frame**
    name; the default frame is used when *name* is falsy or ``"default"``.
    """
    report = ConversionReport(engine="stata", direction="push")
    prepared = prepare(df, report)

    stata = engine._stata
    if stata is None:
        raise DataTransferError("The Stata session is not running.", engine="stata", name=name)

    use_frame = bool(name) and name not in {"default", "data"}
    try:
        if use_frame:
            # Stata refuses to drop the frame it is currently in (r(110) on the
            # subsequent create), so step back to `default` before dropping.
            engine.execute("capture frame change default", quietly=True)
            engine.execute(f"capture frame drop {name}", quietly=True)
            engine.execute(f"frame create {name}", quietly=True)
            engine.execute(f"frame change {name}", quietly=True)
        elif clear:
            engine.execute("clear", quietly=True)
        stata.pdataframe_to_data(prepared, force=True)
    except Exception as exc:
        raise DataTransferError(
            f"PyStata refused the frame: {exc}", engine="stata", name=name, raw=exc
        ) from exc

    report.add(
        Severity.INFO,
        f"{len(prepared)} observations x {len(prepared.columns)} variables loaded"
        + (f" into frame {name}" if use_frame else ""),
    )
    report.emit()
    return report


def pull_frame(
    engine, name: Optional[str] = None, *, columns: Optional[List[str]] = None, **kwargs: Any
) -> pd.DataFrame:
    """Read Stata's current dataset (or a named frame) back into pandas."""
    stata = engine._stata
    if stata is None:
        raise DataTransferError("The Stata session is not running.", engine="stata", name=name)
    try:
        if name and name not in {"default", "data"}:
            df = stata.pdataframe_from_frame(name, var=columns)
        else:
            df = stata.pdataframe_from_data(var=columns)
    except Exception as exc:
        raise DataTransferError(
            f"Could not read Stata data: {exc}", engine="stata", name=name, raw=exc
        ) from exc

    report = ConversionReport(engine="stata", direction="pull")
    report.add(
        Severity.INFO,
        "Stata's extended missing values (.a-.z) all arrive as NaN — "
        "pandas has a single missing marker",
    )
    df.attrs["econenv_conversion"] = report
    df.attrs["econenv_metadata"] = describe_frame(df, name=name, source_engine="stata")
    return df


def pull_matrix(engine, name: str) -> np.ndarray:
    """Read a Stata matrix (``r(table)``, ``e(b)``, ``e(V)``, a named matrix) as an ndarray.

    ``sfi.Matrix.get`` returns the stored doubles. The stored-result dictionaries
    are tried first because they are the documented path for ``r()``/``e()``;
    both preserve full precision, which reading through ``display`` would not.
    """
    stata = engine._stata
    if stata is None:
        raise DataTransferError("The Stata session is not running.", engine="stata", name=name)

    match = _RESULT_REF.match(name.strip())
    if match:
        getter = {
            "r": stata.get_return,
            "e": stata.get_ereturn,
            "s": stata.get_sreturn,
        }[match.group(1)]
        try:
            value = getter().get(name)
        except Exception:
            value = None
        if value is not None:
            return np.atleast_2d(np.asarray(value, dtype=float))

    try:
        return np.atleast_2d(np.asarray(engine._sfi.Matrix.get(name), dtype=float))
    except Exception as exc:
        raise DataTransferError(
            f"Could not read Stata matrix {name!r}: {exc}",
            engine="stata",
            name=name,
            raw=exc,
            hint="Check the matrix exists — `matrix list` in Stata shows what is defined.",
        ) from exc
