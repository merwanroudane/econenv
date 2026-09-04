"""pandas <-> EViews, over COM.

The single most important thing in this module is :func:`_variant`.

Measured behaviour (Phase 0 audit §5.5)::

    app.PutSeries("zz", [1.0, 2.0, 3.0])   # returns without error
    app.GetSeries("zz")  ->  (None, None, None)     # every value lost

A plain Python list marshals into a VARIANT that EViews reads as empty, and
nothing anywhere reports a problem. Wrapping the values in an explicit
``comtypes.automation.VARIANT`` fixes it. Because a silent all-NA dataset is the
worst possible failure mode for an econometrics tool, every push is also **read
back and verified** before it is called a success.

The other EViews-specific pieces here:

* ``GetSeries`` returns ``None`` for ``NA`` — mapped to ``NaN``.
* ``GetGroup`` needs a BSTR SAFEARRAY and rejects a Python list, so transfers go
  series by series.
* A dated pandas index becomes a dated workfile page (``create q 2000Q1 2010Q4``)
  and comes back through ``@otod`` so the dates survive the round trip.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd

from ..exceptions import DataTransferError, LossyConversionError, com_message
from ..schema import (
    ConversionReport,
    LogicalType,
    Severity,
    describe_frame,
    logical_type_of,
)

#: EViews object names are limited to 24 characters and cannot be a command.
MAX_NAME_LEN = 24
# fmt: off
EVIEWS_RESERVED = {
    "c", "resid", "abs", "log", "exp", "sqr", "d", "dlog", "na", "nrnd", "rnd",
    "trend", "obs", "mean", "sum", "var", "cor", "cov", "series", "equation",
    "group", "matrix", "scalar", "vector", "sample", "smpl",
}
# fmt: on


def sanitise_name(name: str, taken: Optional[set] = None) -> str:
    """Return an EViews-legal object name derived from *name*."""
    import re

    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", str(name))
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"v_{cleaned}"
    cleaned = cleaned[:MAX_NAME_LEN]
    if cleaned.lower() in EVIEWS_RESERVED:
        cleaned = f"{cleaned}_"[:MAX_NAME_LEN]
    if taken is not None:
        base, suffix = cleaned, 1
        while cleaned.lower() in taken:
            tail = f"_{suffix}"
            cleaned = base[: MAX_NAME_LEN - len(tail)] + tail
            suffix += 1
        taken.add(cleaned.lower())
    return cleaned


def _variant(values: Iterable[Any]):
    """Wrap *values* in a COM VARIANT.

    Not optional and not a style preference: passing a bare Python list to
    ``PutSeries`` writes NA for every observation without raising. See the
    module docstring.
    """
    from comtypes.automation import VARIANT

    variant = VARIANT()
    variant.value = [float(v) if v is not None and not _isnan(v) else None for v in values]
    return variant


def _isnan(value: Any) -> bool:
    try:
        return bool(math.isnan(float(value)))
    except (TypeError, ValueError):
        return False


# --------------------------------------------------------------------------- #
# workfile creation
# --------------------------------------------------------------------------- #
def _page_spec(index: pd.Index, n: int) -> str:
    """The ``create`` argument for a workfile matching *index*."""
    from ..engines.eviews_engine import PANDAS_TO_FREQ

    if isinstance(index, pd.PeriodIndex):
        index = index.to_timestamp()
    if isinstance(index, pd.DatetimeIndex) and len(index):
        freq = getattr(index, "freqstr", None) or pd.infer_freq(index)
        letter = PANDAS_TO_FREQ.get(str(freq).split("-")[0]) if freq else None
        if letter:
            return f"{letter} {_eviews_date(index[0], letter)} {_eviews_date(index[-1], letter)}"
    return f"u {n}"


def _eviews_date(stamp: pd.Timestamp, letter: str) -> str:
    """Format a timestamp the way EViews writes that frequency."""
    if letter == "A":
        return f"{stamp.year}"
    if letter == "Q":
        return f"{stamp.year}Q{stamp.quarter}"
    if letter == "M":
        return f"{stamp.year}M{stamp.month:02d}"
    return stamp.strftime("%m/%d/%Y")


# --------------------------------------------------------------------------- #
# push
# --------------------------------------------------------------------------- #
def push_frame(
    engine,
    name: str,
    df: pd.DataFrame,
    *,
    new_workfile: bool = True,
    page: Optional[str] = None,
    verify: bool = True,
    **kwargs: Any,
) -> ConversionReport:
    """Create an EViews workfile page from *df* and write every column into it.

    Parameters
    ----------
    new_workfile:
        Create a fresh workfile. When False the active page is reused and must
        already have at least as many observations as *df*.
    verify:
        Read every numeric series back and compare. On by default — see the
        module docstring for why.
    """
    report = ConversionReport(engine="eviews", direction="push")
    app = engine._app
    if app is None:
        raise DataTransferError("The EViews session is not running.", engine="eviews", name=name)

    n = len(df)
    if n == 0:
        raise DataTransferError("Refusing to push an empty frame.", engine="eviews", name=name)

    frame = df
    if not isinstance(frame.index, pd.RangeIndex) and not isinstance(
        frame.index, (pd.DatetimeIndex, pd.PeriodIndex)
    ):
        frame = frame.reset_index()
        report.add(Severity.INFO, "non-date index written as ordinary column(s)")

    if new_workfile:
        spec = _page_spec(frame.index, n)
        engine.execute(f"create {spec}", capture_graphs=False)
        report.add(Severity.INFO, f"created workfile page: create {spec}")
        if spec.startswith("u "):
            report.add(
                Severity.WARNING,
                "the frame has no recognised date index, so the page is undated; "
                "EViews time-series operators (d(), lags, @trend on dates) will "
                "treat observations as unordered",
            )
    if page:
        engine.execute(f"pageselect {page}", capture_graphs=False)

    taken: set = set()
    written: Dict[str, str] = {}
    for column in frame.columns:
        series = frame[column]
        target = sanitise_name(column, taken)
        if target != str(column):
            report.add(Severity.WARNING, f"renamed to {target!r} for EViews", column=str(column))

        ltype = logical_type_of(series)
        if ltype in (LogicalType.FLOAT, LogicalType.INTEGER, LogicalType.BOOLEAN):
            values = pd.to_numeric(series, errors="coerce").astype(float).to_numpy()
            if ltype is LogicalType.BOOLEAN:
                report.add(Severity.INFO, "boolean stored as 0/1", column=str(column))
            _put_series(engine, target, values, report, str(column))
        elif ltype is LogicalType.CATEGORICAL:
            codes = series.cat.codes.astype(float).replace(-1.0, np.nan).to_numpy()
            _put_series(engine, target, codes, report, str(column))
            levels = list(series.cat.categories)
            report.add(
                Severity.WARNING,
                "categorical stored as integer codes; EViews has no factor type",
                column=str(column),
                detail=f"codes 0..{len(levels) - 1} = {levels[:10]}",
            )
            report.notes[-1].detail = f"codes 0..{len(levels) - 1} = {levels[:10]}"
        elif ltype is LogicalType.STRING:
            _put_alpha(engine, target, series, report, str(column))
        elif ltype in (LogicalType.DATE, LogicalType.DATETIME):
            stamps = pd.to_datetime(series, errors="coerce")
            # EViews date numbers are days since 01/01/0001 (its @dateval basis).
            values = (stamps - pd.Timestamp("1970-01-01")).dt.total_seconds() / 86400.0
            _put_series(engine, target, values.to_numpy(), report, str(column))
            report.add(
                Severity.WARNING,
                "datetime stored as days since 1970-01-01 (a plain numeric series)",
                column=str(column),
            )
        else:
            raise DataTransferError(
                f"dtype {series.dtype} cannot be represented in EViews",
                engine="eviews",
                name=str(column),
            )
        written[str(column)] = target

    if verify:
        _verify(engine, frame, written, report)

    report.add(Severity.INFO, f"{n} observations x {len(written)} series written")
    report.emit()
    return report


def _put_series(
    engine, target: str, values: np.ndarray, report: ConversionReport, column: str
) -> None:
    try:
        engine._app.PutSeries(target, _variant(values))
    except Exception as exc:
        raise DataTransferError(
            com_message(exc) or str(exc), engine="eviews", name=column, raw=exc
        ) from exc


def _put_alpha(
    engine, target: str, series: pd.Series, report: ConversionReport, column: str
) -> None:
    """Write a string column as an EViews alpha series.

    There is no ``PutAlpha``, so the values go in through ``@recode``-free
    per-observation assignment. That is slow, so it is capped and reported.
    """
    values = series.astype(object).where(series.notna(), None).tolist()
    limit = 5000
    if len(values) > limit:
        raise LossyConversionError(
            f"string column has {len(values)} rows; EViews alpha transfer is capped at {limit}",
            engine="eviews",
            name=column,
            hint="Encode it as a categorical first, or drop the column before pushing.",
        )
    engine.execute(f"alpha {target}", capture_graphs=False)
    for i, value in enumerate(values, start=1):
        if value is None:
            continue
        escaped = str(value).replace('"', '""')
        engine.execute(f'{target}({i}) = "{escaped}"', capture_graphs=False)
    report.add(
        Severity.INFO,
        "string column written as an EViews alpha series, one observation at a time",
        column=column,
    )


def _verify(engine, frame: pd.DataFrame, written: Dict[str, str], report: ConversionReport) -> None:
    """Read the numeric series back and fail loudly on any mismatch."""
    for original, target in written.items():
        series = frame[original]
        if logical_type_of(series) not in (
            LogicalType.FLOAT,
            LogicalType.INTEGER,
            LogicalType.BOOLEAN,
        ):
            continue
        expected = pd.to_numeric(series, errors="coerce").astype(float).to_numpy()
        try:
            actual = np.array(
                [np.nan if v is None else float(v) for v in engine._app.GetSeries(target)],
                dtype=float,
            )
        except Exception as exc:
            raise DataTransferError(
                f"could not read {target!r} back for verification: {com_message(exc) or exc}",
                engine="eviews",
                name=original,
                raw=exc,
            ) from exc
        if actual.size != expected.size:
            raise DataTransferError(
                f"EViews stored {actual.size} observations, expected {expected.size}",
                engine="eviews",
                name=original,
                hint="The active page is shorter than the frame; push with new_workfile=True.",
            )
        if np.isnan(actual).all() and not np.isnan(expected).all():
            raise DataTransferError(
                "EViews stored NA for every observation — the COM VARIANT marshalling failed",
                engine="eviews",
                name=original,
                hint="This is the known PutSeries trap; report it as an EconEnv bug.",
            )
        if not np.allclose(actual, expected, rtol=1e-12, atol=0.0, equal_nan=True):
            worst = float(np.nanmax(np.abs(actual - expected)))
            report.add(
                Severity.WARNING,
                f"values differ after the round trip by up to {worst:.3g}",
                column=original,
            )


# --------------------------------------------------------------------------- #
# pull
# --------------------------------------------------------------------------- #
def pull_frame(
    engine,
    name: Optional[str] = None,
    *,
    columns: Optional[Sequence[str]] = None,
    dated_index: bool = True,
    **kwargs: Any,
) -> pd.DataFrame:
    """Read the active EViews page (or the named series) back into pandas."""
    app = engine._app
    if app is None:
        raise DataTransferError("The EViews session is not running.", engine="eviews", name=name)

    if columns is not None:
        names = list(columns)
    elif name and name not in {"*", "page", "workfile"}:
        names = name.split()
    else:
        listing = engine._eval('@wlookup("*","series")')
        names = str(listing).split() if listing else []

    if not names:
        raise DataTransferError(
            "The active EViews page contains no series.", engine="eviews", name=name
        )

    n_obs = engine._eval("@obsrange")
    n = int(n_obs) if n_obs else 0

    data: Dict[str, List[float]] = {}
    for series_name in names:
        try:
            raw = app.GetSeries(series_name)
        except Exception as exc:
            raise DataTransferError(
                com_message(exc) or str(exc), engine="eviews", name=series_name, raw=exc
            ) from exc
        data[series_name] = [np.nan if v is None else float(v) for v in raw]

    df = pd.DataFrame(data)
    if dated_index:
        index = _date_index(engine, n or len(df))
        if index is not None and len(index) == len(df):
            df.index = index

    report = ConversionReport(engine="eviews", direction="pull")
    report.add(Severity.INFO, "EViews NA read as NaN")
    report.add(
        Severity.INFO,
        "alpha (string) series are not returned by GetSeries; "
        "read them with `%eviews_pull` per observation if needed",
    )
    df.attrs["econenv_conversion"] = report

    meta = describe_frame(df, name=name, source_engine="eviews")
    meta.frequency = _pandas_freq(engine)
    meta.notes["workfile"] = engine._eval("@wfname")
    meta.notes["page"] = engine._eval("@pagename")
    df.attrs["econenv_metadata"] = meta
    return df


def _date_index(engine, n: int) -> Optional[pd.Index]:
    """Rebuild a pandas index from EViews' own observation labels."""
    freq = engine._eval("@pagefreq")
    if not freq or str(freq).upper().startswith("U"):
        return None
    labels = []
    for i in range(1, n + 1):
        label = engine._eval(f"@otod({i})")
        if label is None:
            return None
        labels.append(str(label))
    try:
        return pd.PeriodIndex(labels, freq=_period_freq(str(freq))).to_timestamp()
    except (ValueError, TypeError):
        try:
            return pd.to_datetime(labels)
        except (ValueError, TypeError):
            return None


def _period_freq(page_freq: str) -> str:
    letter = page_freq.strip().upper()[:1]
    return {"A": "Y", "Q": "Q", "M": "M", "W": "W", "D": "D", "H": "h"}.get(letter, "D")


def _pandas_freq(engine) -> Optional[str]:
    from ..engines.eviews_engine import parse_frequency

    return parse_frequency(engine._eval("@pagefreq"))
