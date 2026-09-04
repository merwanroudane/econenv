"""Standardised result objects (brief §15, §16, §17).

Two levels:

* :class:`ExecutionResult` — what *any* engine returns for *any* code.
* :class:`ModelResult` — the econometric subset, harmonised across engines.

:class:`ModelResult` deliberately keeps :attr:`ModelResult.raw` alongside the
harmonised table. Brief §59: differences between programs are the point, not
something to paper over.
"""

from __future__ import annotations

import base64
import datetime as _dt
import html
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

import numpy as np
import pandas as pd

from .schema import ConversionReport, DatasetMetadata


@dataclass
class Figure:
    """A plot produced by an engine, ready for Jupyter's rich display."""

    data: bytes
    mimetype: str  # "image/png" | "image/svg+xml"
    engine: str
    name: Optional[str] = None

    def _repr_mimebundle_(self, include=None, exclude=None):
        if self.mimetype == "image/svg+xml":
            return {"image/svg+xml": self.data.decode("utf-8", "replace")}
        return {self.mimetype: base64.b64encode(self.data).decode("ascii")}


@dataclass
class ExecutionResult:
    """The outcome of running code in one engine."""

    engine: str
    code: str
    success: bool = True
    stdout: str = ""
    stderr: str = ""
    warnings: List[str] = field(default_factory=list)
    tables: List[pd.DataFrame] = field(default_factory=list)
    figures: List[Figure] = field(default_factory=list)
    scalars: Dict[str, Any] = field(default_factory=dict)
    matrices: Dict[str, np.ndarray] = field(default_factory=dict)
    value: Any = None  # the engine's own return value, when it has one
    metadata: Dict[str, Any] = field(default_factory=dict)
    conversions: List[ConversionReport] = field(default_factory=list)
    elapsed: float = 0.0
    timestamp: _dt.datetime = field(default_factory=lambda: _dt.datetime.now(_dt.timezone.utc))
    engine_version: Optional[str] = None
    error: Optional[str] = None

    # -- convenience ------------------------------------------------------- #
    @property
    def text(self) -> str:
        """stdout and stderr as the user would have seen them."""
        parts = [p for p in (self.stdout, self.stderr) if p]
        return "\n".join(parts)

    def table(self, index: int = 0) -> pd.DataFrame:
        return self.tables[index]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "engine": self.engine,
            "engine_version": self.engine_version,
            "success": self.success,
            "code": self.code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "warnings": list(self.warnings),
            "scalars": {k: _jsonable(v) for k, v in self.scalars.items()},
            "n_tables": len(self.tables),
            "n_figures": len(self.figures),
            "elapsed": round(self.elapsed, 6),
            "timestamp": self.timestamp.isoformat(),
            "error": self.error,
            "metadata": {k: _jsonable(v) for k, v in self.metadata.items()},
        }

    # -- display ----------------------------------------------------------- #
    def __repr__(self) -> str:
        state = "ok" if self.success else "FAILED"
        return (
            f"<ExecutionResult {self.engine} {state} "
            f"{self.elapsed:.3f}s tables={len(self.tables)} figures={len(self.figures)}>"
        )

    def _repr_mimebundle_(self, include=None, exclude=None):
        return {"text/plain": self._plain(), "text/html": self._html()}

    def _plain(self) -> str:
        header = f"[{self.engine}{' ' + self.engine_version if self.engine_version else ''}]"
        body = self.text
        if not self.success and self.error:
            body = f"{body}\nERROR: {self.error}".strip()
        return f"{header}\n{body}" if body else header

    def _html(self) -> str:
        badge_colour = "#2e7d32" if self.success else "#c62828"
        pieces = [
            "<div style='font-family:system-ui,sans-serif;font-size:13px'>",
            f"<div style='color:{badge_colour};font-weight:600'>"
            f"{html.escape(self.engine)}"
            f"{' ' + html.escape(self.engine_version) if self.engine_version else ''}"
            f" · {self.elapsed:.3f}s</div>",
        ]
        if self.text:
            pieces.append(
                "<pre style='white-space:pre-wrap;margin:4px 0;"
                "font-family:ui-monospace,Consolas,monospace'>"
                f"{html.escape(self.text)}</pre>"
            )
        if self.error:
            pieces.append(
                f"<pre style='color:#c62828;margin:4px 0'>{html.escape(self.error)}</pre>"
            )
        for note in self.warnings:
            pieces.append(f"<div style='color:#ef6c00'>⚠ {html.escape(note)}</div>")
        for table in self.tables:
            pieces.append(table.to_html(max_rows=25, border=0))
        pieces.append("</div>")
        return "".join(pieces)


@dataclass
class ModelResult:
    """Harmonised econometric output (brief §16).

    The common fields are filled where the engine reports them and left ``None``
    where it does not — an absent value is information, so it is never faked.
    """

    engine: str
    model: str  # "OLS", "Logit", ...
    depvar: Optional[str] = None
    coefficients: Optional[pd.DataFrame] = None  # index=term, cols per _COEF_COLUMNS
    nobs: Optional[int] = None
    df_model: Optional[int] = None
    df_resid: Optional[int] = None
    r2: Optional[float] = None
    r2_adj: Optional[float] = None
    loglik: Optional[float] = None
    aic: Optional[float] = None
    bic: Optional[float] = None
    rmse: Optional[float] = None
    fstat: Optional[float] = None
    fstat_pvalue: Optional[float] = None
    durbin_watson: Optional[float] = None
    vcov_type: Optional[str] = None
    engine_version: Optional[str] = None
    command: Optional[str] = None
    raw: Any = None  # the untouched engine object / text
    notes: List[str] = field(default_factory=list)
    dataset: Optional[DatasetMetadata] = None

    COEF_COLUMNS = ("coef", "std_err", "stat", "pvalue", "ci_lower", "ci_upper")

    @classmethod
    def from_arrays(
        cls,
        engine: str,
        model: str,
        terms: Sequence[Any],
        coef: Iterable[Any],
        std_err: Optional[Iterable[Any]] = None,
        stat: Optional[Iterable[Any]] = None,
        pvalue: Optional[Iterable[Any]] = None,
        ci_lower: Optional[Iterable[Any]] = None,
        ci_upper: Optional[Iterable[Any]] = None,
        **kwargs: Any,
    ) -> ModelResult:
        """Build from parallel arrays, the shape every adapter naturally has."""
        n = len(terms)

        def col(values: Optional[Iterable[Any]]) -> List[float]:
            if values is None:
                return [float("nan")] * n
            return [float(v) if v is not None else float("nan") for v in values]

        frame = pd.DataFrame(
            {
                "coef": col(coef),
                "std_err": col(std_err),
                "stat": col(stat),
                "pvalue": col(pvalue),
                "ci_lower": col(ci_lower),
                "ci_upper": col(ci_upper),
            },
            index=pd.Index([str(t) for t in terms], name="term"),
        )
        return cls(engine=engine, model=model, coefficients=frame, **kwargs)

    def summary_row(self) -> Dict[str, Any]:
        """One flat row per engine, used to build the comparison table."""
        return {
            "engine": self.engine,
            "version": self.engine_version,
            "model": self.model,
            "nobs": self.nobs,
            "r2": self.r2,
            "r2_adj": self.r2_adj,
            "loglik": self.loglik,
            "aic": self.aic,
            "bic": self.bic,
            "rmse": self.rmse,
            "vcov": self.vcov_type,
        }

    def to_dict(self) -> Dict[str, Any]:
        out = {
            k: _jsonable(v)
            for k, v in self.__dict__.items()
            if k not in {"coefficients", "raw", "dataset"}
        }
        out["coefficients"] = (
            self.coefficients.reset_index().to_dict("records")
            if self.coefficients is not None
            else None
        )
        out["dataset"] = self.dataset.to_dict() if self.dataset else None
        return out

    def __repr__(self) -> str:
        return f"<ModelResult {self.engine} {self.model} n={self.nobs} r2={self.r2}>"

    def _repr_mimebundle_(self, include=None, exclude=None):
        return {"text/plain": self._plain(), "text/html": self._html()}

    def _plain(self) -> str:
        head = f"{self.model} · {self.engine}"
        if self.engine_version:
            head += f" {self.engine_version}"
        lines = [head]
        if self.depvar:
            lines.append(f"Dependent variable: {self.depvar}")
        if self.coefficients is not None:
            lines.append(self.coefficients.to_string(float_format=lambda v: f"{v:12.6g}"))
        stats = {k: v for k, v in self.summary_row().items() if v is not None and k != "engine"}
        lines.append("  ".join(f"{k}={v}" for k, v in stats.items()))
        for note in self.notes:
            lines.append(f"note: {note}")
        return "\n".join(lines)

    def _html(self) -> str:
        pieces = [
            "<div style='font-family:system-ui,sans-serif;font-size:13px'>",
            f"<div style='font-weight:600'>{html.escape(self.model)} · "
            f"{html.escape(self.engine)}"
            f"{' ' + html.escape(self.engine_version) if self.engine_version else ''}</div>",
        ]
        if self.depvar:
            pieces.append(f"<div>Dependent variable: <code>{html.escape(self.depvar)}</code></div>")
        if self.coefficients is not None:
            pieces.append(self.coefficients.to_html(float_format=lambda v: f"{v:.6g}", border=0))
        stats = {k: v for k, v in self.summary_row().items() if v is not None and k != "engine"}
        if stats:
            pieces.append(
                "<div style='color:#555;margin-top:4px'>"
                + " · ".join(f"{html.escape(k)}={html.escape(str(v))}" for k, v in stats.items())
                + "</div>"
            )
        for note in self.notes:
            pieces.append(f"<div style='color:#ef6c00'>⚠ {html.escape(note)}</div>")
        pieces.append("</div>")
        return "".join(pieces)


def _jsonable(value: Any) -> Any:
    """Best-effort conversion to something ``json.dumps`` accepts."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (_dt.datetime, _dt.date)):
        return value.isoformat()
    if isinstance(value, pd.DataFrame):
        return value.to_dict("records")
    if isinstance(value, pd.Series):
        return value.to_dict()
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if isinstance(value, ConversionReport):
        return str(value)
    if isinstance(value, DatasetMetadata):
        return value.to_dict()
    return str(value)
