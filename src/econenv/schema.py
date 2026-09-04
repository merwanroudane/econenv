"""Canonical type system and dataset metadata (brief §11 and §12).

A ``pandas.DataFrame`` is the interchange object, but a DataFrame alone loses
things econometrics needs: which column is time, which is the panel unit, what
the frequency is, what a value label meant in Stata, whether a column *was* a
factor in R.

:class:`ColumnSchema` and :class:`DatasetMetadata` carry that alongside the
frame. :class:`ConversionReport` records what a transfer had to give up — and
nothing is allowed to give anything up quietly.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence

import numpy as np
import pandas as pd

from ._logging import get_logger

_log = get_logger("schema")


class LogicalType(str, Enum):
    """Engine-neutral column types.

    Deliberately coarse. It only needs to be fine enough that every adapter can
    make a faithful decision, and coarse enough that all four engines can
    actually express it.
    """

    BOOLEAN = "boolean"
    INTEGER = "integer"
    FLOAT = "float"
    STRING = "string"
    CATEGORICAL = "categorical"
    DATE = "date"
    DATETIME = "datetime"
    UNSUPPORTED = "unsupported"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class ConversionNote:
    """One thing that happened during a transfer."""

    column: Optional[str]
    severity: Severity
    message: str
    detail: Optional[str] = None

    def __str__(self) -> str:
        where = f"{self.column}: " if self.column else ""
        return f"[{self.severity.value}] {where}{self.message}"


@dataclass
class ConversionReport:
    """Everything a push/pull had to compromise on.

    Attached to :class:`~econenv.results.ExecutionResult` and to transferred
    frames so a lossy conversion is always traceable after the fact.
    """

    engine: str
    direction: str  # "push" | "pull"
    notes: List[ConversionNote] = field(default_factory=list)

    def add(
        self,
        severity: Severity,
        message: str,
        *,
        column: Optional[str] = None,
        detail: Optional[str] = None,
    ) -> None:
        self.notes.append(ConversionNote(column, severity, message, detail))

    @property
    def lossy(self) -> bool:
        return any(n.severity is not Severity.INFO for n in self.notes)

    @property
    def warnings(self) -> List[ConversionNote]:
        return [n for n in self.notes if n.severity is Severity.WARNING]

    @property
    def errors(self) -> List[ConversionNote]:
        return [n for n in self.notes if n.severity is Severity.ERROR]

    def emit(self) -> None:
        """Surface warnings through :mod:`warnings` so notebooks show them."""
        import warnings as _warnings

        for note in self.notes:
            if note.severity is Severity.WARNING:
                _warnings.warn(
                    f"EconEnv {self.direction} -> {self.engine}: {note}", UserWarning, stacklevel=3
                )
            elif note.severity is Severity.INFO:
                _log.debug("%s", note)

    def __str__(self) -> str:
        if not self.notes:
            return f"{self.engine} {self.direction}: lossless"
        lines = [f"{self.engine} {self.direction}:"]
        lines += [f"  {n}" for n in self.notes]
        return "\n".join(lines)


@dataclass
class ColumnSchema:
    """What EconEnv knows about one column."""

    name: str
    logical_type: LogicalType
    pandas_dtype: str
    nullable: bool = True
    categories: Optional[List[Any]] = None
    ordered: bool = False
    label: Optional[str] = None  # Stata variable label / R attr
    value_labels: Optional[Dict[Any, str]] = None
    tz: Optional[str] = None
    source_type: Optional[str] = None  # the engine's own type name

    def to_dict(self) -> Dict[str, Any]:
        out = dataclasses.asdict(self)
        out["logical_type"] = self.logical_type.value
        return out


@dataclass
class DatasetMetadata:
    """Econometric metadata travelling with a frame (brief §12)."""

    name: Optional[str] = None
    columns: List[ColumnSchema] = field(default_factory=list)
    time_var: Optional[str] = None
    panel_var: Optional[str] = None
    frequency: Optional[str] = None  # pandas offset alias, e.g. "QS", "M", "A"
    index_names: List[str] = field(default_factory=list)
    source_engine: Optional[str] = None
    history: List[str] = field(default_factory=list)
    notes: Dict[str, Any] = field(default_factory=dict)

    def column(self, name: str) -> Optional[ColumnSchema]:
        return next((c for c in self.columns if c.name == name), None)

    def record(self, event: str) -> None:
        self.history.append(event)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "columns": [c.to_dict() for c in self.columns],
            "time_var": self.time_var,
            "panel_var": self.panel_var,
            "frequency": self.frequency,
            "index_names": list(self.index_names),
            "source_engine": self.source_engine,
            "history": list(self.history),
            "notes": dict(self.notes),
        }


# --------------------------------------------------------------------------- #
# inference
# --------------------------------------------------------------------------- #
def logical_type_of(series: pd.Series) -> LogicalType:
    """Map a pandas dtype to a :class:`LogicalType`."""
    dtype = series.dtype
    if isinstance(dtype, pd.CategoricalDtype):
        return LogicalType.CATEGORICAL
    if pd.api.types.is_bool_dtype(dtype):
        return LogicalType.BOOLEAN
    if pd.api.types.is_datetime64_any_dtype(dtype):
        return LogicalType.DATETIME
    if isinstance(dtype, pd.PeriodDtype):
        return LogicalType.DATE
    if pd.api.types.is_integer_dtype(dtype):
        return LogicalType.INTEGER
    if pd.api.types.is_float_dtype(dtype):
        return LogicalType.FLOAT
    if pd.api.types.is_string_dtype(dtype) or pd.api.types.is_object_dtype(dtype):
        # object columns holding dates are common after a CSV round-trip
        non_null = series.dropna()
        if len(non_null) and all(isinstance(v, str) for v in non_null.head(50)):
            return LogicalType.STRING
        if len(non_null) == 0:
            return LogicalType.STRING
        return LogicalType.UNSUPPORTED
    return LogicalType.UNSUPPORTED


def describe_frame(
    df: pd.DataFrame,
    *,
    name: Optional[str] = None,
    source_engine: Optional[str] = None,
    time_var: Optional[str] = None,
    panel_var: Optional[str] = None,
) -> DatasetMetadata:
    """Build :class:`DatasetMetadata` by inspecting *df*.

    The index is inspected too: a ``DatetimeIndex`` or ``PeriodIndex`` sets
    ``time_var`` and ``frequency`` automatically, and a two-level MultiIndex is
    read as (panel unit, time) — the standard econometric layout.
    """
    meta = DatasetMetadata(name=name, source_engine=source_engine)
    meta.index_names = [str(n) for n in df.index.names if n is not None]

    index = df.index
    if isinstance(index, pd.MultiIndex) and index.nlevels == 2:
        levels = list(index.names)
        if levels[0] is not None:
            meta.panel_var = str(levels[0])
        if levels[1] is not None:
            meta.time_var = str(levels[1])
        second = index.get_level_values(1)
        meta.frequency = _frequency_of(second)
    elif isinstance(index, (pd.DatetimeIndex, pd.PeriodIndex)):
        meta.time_var = str(index.name) if index.name is not None else "index"
        meta.frequency = _frequency_of(index)

    if time_var is not None:
        meta.time_var = time_var
    if panel_var is not None:
        meta.panel_var = panel_var

    for column in df.columns:
        series = df[column]
        ltype = logical_type_of(series)
        schema = ColumnSchema(
            name=str(column),
            logical_type=ltype,
            pandas_dtype=str(series.dtype),
            nullable=bool(series.isna().any()),
        )
        if ltype is LogicalType.CATEGORICAL:
            schema.categories = list(series.cat.categories)
            schema.ordered = bool(series.cat.ordered)
        if ltype is LogicalType.DATETIME:
            tz = getattr(series.dtype, "tz", None)
            schema.tz = str(tz) if tz is not None else None
        meta.columns.append(schema)

        if meta.time_var is None and ltype in (LogicalType.DATE, LogicalType.DATETIME):
            meta.time_var = str(column)
    return meta


def _frequency_of(index: pd.Index) -> Optional[str]:
    freq = getattr(index, "freqstr", None)
    if freq:
        return str(freq)
    if isinstance(index, pd.DatetimeIndex) and len(index) > 2:
        try:
            inferred = pd.infer_freq(index)
        except (ValueError, TypeError):
            inferred = None
        return inferred
    return None


def numeric_matrix(df: pd.DataFrame) -> np.ndarray:
    """Float view of the numeric columns, used by the engine bridges."""
    numeric = df.select_dtypes(include=[np.number, "bool"])
    return numeric.to_numpy(dtype=float, copy=True)


def restore_categoricals(df: pd.DataFrame, meta: Optional[DatasetMetadata]) -> pd.DataFrame:
    """Re-apply categorical dtypes recorded in *meta* after a round-trip."""
    if meta is None:
        return df
    out = df
    for schema in meta.columns:
        if schema.logical_type is LogicalType.CATEGORICAL and schema.name in out.columns:
            if schema.categories is None:
                continue
            out = out.copy()
            out[schema.name] = pd.Categorical(
                out[schema.name], categories=schema.categories, ordered=schema.ordered
            )
    return out


def validate_names(names: Sequence[str], *, engine: str, reserved: Mapping[str, str]) -> List[str]:
    """Return the subset of *names* that clash with engine reserved words."""
    lowered = {r.lower() for r in reserved}
    return [n for n in names if str(n).lower() in lowered]
