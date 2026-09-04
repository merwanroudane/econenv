"""Run one specification in several engines and compare (brief §22, §26, §59).

The comparison is built to *reveal* disagreement, not to smooth it over. Two
tolerances are applied — absolute and relative — because a 1e-14 difference in a
coefficient is floating-point arithmetic, not evidence that one program is
wrong. Anything that survives both tolerances is reported as a real difference,
with the defaults that could explain it listed alongside.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from .._logging import get_logger
from ..engines import registry as engine_registry
from ..exceptions import CapabilityError, EconEnvError
from ..results import ModelResult
from .registry import model_registry
from .spec import ModelSpec

_log = get_logger("compare")

DEFAULT_RTOL = 1e-8
DEFAULT_ATOL = 1e-10

#: Documented reasons two engines can legitimately disagree (brief §26).
KNOWN_DIVERGENCES = {
    "aic": (
        "AIC normalisation differs: statsmodels -2ll+2k; R counts sigma^2 as a "
        "parameter (k+1); EViews divides by n; Stata needs `estat ic`."
    ),
    "bic": "BIC follows the same normalisation differences as AIC.",
    "loglik": "Some engines report the concentrated log-likelihood.",
    "std_err": (
        "Robust covariance defaults differ: Stata `vce(robust)` is HC1, "
        "statsmodels `HC0` is HC0, EViews White is HC1 with a d.f. correction."
    ),
    "rmse": "Stata's Root MSE and R's residual standard error use the same d.f.; EViews' S.E. of regression matches.",
}


@dataclass
class ComparisonResult:
    """Side-by-side output of the same specification across engines."""

    spec: ModelSpec
    results: Dict[str, ModelResult] = field(default_factory=dict)
    failures: Dict[str, str] = field(default_factory=dict)
    rtol: float = DEFAULT_RTOL
    atol: float = DEFAULT_ATOL

    # -- tables ------------------------------------------------------------ #
    def coefficients(self, column: str = "coef") -> pd.DataFrame:
        """Terms down the rows, engines across the columns."""
        frames = {}
        for engine, result in self.results.items():
            if result.coefficients is not None and column in result.coefficients:
                frames[engine] = result.coefficients[column]
        if not frames:
            return pd.DataFrame()
        return pd.DataFrame(frames)

    def summary(self) -> pd.DataFrame:
        """One row per engine of the headline statistics."""
        if not self.results:
            return pd.DataFrame()
        return pd.DataFrame([r.summary_row() for r in self.results.values()]).set_index("engine")

    def differences(self, column: str = "coef") -> pd.DataFrame:
        """Max absolute and relative gap per term, and whether it clears tolerance."""
        table = self.coefficients(column)
        if table.empty or table.shape[1] < 2:
            return pd.DataFrame()
        values = table.to_numpy(dtype=float)
        with np.errstate(invalid="ignore"):
            spread = np.nanmax(values, axis=1) - np.nanmin(values, axis=1)
            scale = np.nanmax(np.abs(values), axis=1)
            relative = np.where(scale > 0, spread / scale, 0.0)
        out = pd.DataFrame(
            {"max_abs_diff": spread, "max_rel_diff": relative},
            index=table.index,
        )
        out["within_tolerance"] = (out["max_abs_diff"] <= self.atol) | (
            out["max_rel_diff"] <= self.rtol
        )
        return out

    @property
    def agree(self) -> bool:
        """Do all engines agree on every coefficient, within tolerance?"""
        diff = self.differences()
        return bool(diff.empty or diff["within_tolerance"].all())

    def explain(self) -> List[str]:
        """Plain-language notes on anything that differs, plus engine caveats."""
        notes: List[str] = []
        diff = self.differences()
        if not diff.empty and not diff["within_tolerance"].all():
            offenders = diff.index[~diff["within_tolerance"]].tolist()
            notes.append(
                f"Coefficients differ beyond tolerance for: {', '.join(offenders)}. "
                "Check the estimation sample and the covariance option in each engine."
            )
        summary = self.summary()
        for column, reason in KNOWN_DIVERGENCES.items():
            if column in summary.columns:
                series = summary[column].dropna()
                if len(series) > 1 and not np.allclose(
                    series.to_numpy(dtype=float), series.iloc[0], rtol=1e-6, atol=1e-8
                ):
                    notes.append(f"{column}: {reason}")
        for engine, result in self.results.items():
            notes.extend(f"{engine}: {note}" for note in result.notes)
        for engine, error in self.failures.items():
            notes.append(f"{engine}: not compared — {error}")
        return notes

    # -- display ----------------------------------------------------------- #
    def __repr__(self) -> str:
        engines = ", ".join(self.results)
        return f"<ComparisonResult {self.spec.estimator} [{engines}] agree={self.agree}>"

    def _repr_mimebundle_(self, include=None, exclude=None):
        return {"text/plain": self._plain(), "text/html": self._html()}

    def _plain(self) -> str:
        lines = [f"{self.spec}", ""]
        coefficients = self.coefficients()
        if not coefficients.empty:
            lines += [
                "Coefficients",
                coefficients.to_string(float_format=lambda v: f"{v:14.8g}"),
                "",
            ]
        summary = self.summary()
        if not summary.empty:
            lines += ["Summary statistics", summary.to_string(), ""]
        diff = self.differences()
        if not diff.empty:
            verdict = "all engines agree within tolerance" if self.agree else "DIFFERENCES FOUND"
            lines += [f"Agreement: {verdict}", diff.to_string(), ""]
        notes = self.explain()
        if notes:
            lines += ["Notes:"] + [f"  - {n}" for n in notes]
        return "\n".join(lines)

    def _html(self) -> str:
        import html as _html

        colour = "#2e7d32" if self.agree else "#c62828"
        verdict = "agree within tolerance" if self.agree else "differ beyond tolerance"
        pieces = [
            "<div style='font-family:system-ui,sans-serif;font-size:13px'>",
            f"<div style='font-weight:600'>{_html.escape(str(self.spec))}</div>",
            f"<div style='color:{colour}'>Engines {verdict} "
            f"(rtol={self.rtol:g}, atol={self.atol:g})</div>",
        ]
        coefficients = self.coefficients()
        if not coefficients.empty:
            pieces += [
                "<h4 style='margin:8px 0 2px'>Coefficients</h4>",
                coefficients.to_html(float_format=lambda v: f"{v:.8g}", border=0),
            ]
        summary = self.summary()
        if not summary.empty:
            pieces += [
                "<h4 style='margin:8px 0 2px'>Summary statistics</h4>",
                summary.to_html(float_format=lambda v: f"{v:.8g}", border=0),
            ]
        notes = self.explain()
        if notes:
            pieces.append("<h4 style='margin:8px 0 2px'>Notes</h4><ul>")
            pieces += [f"<li>{_html.escape(n)}</li>" for n in notes]
            pieces.append("</ul>")
        pieces.append("</div>")
        return "".join(pieces)


def run_spec(
    spec: ModelSpec,
    data: pd.DataFrame,
    engines: Optional[Sequence[str]] = None,
    *,
    rtol: float = DEFAULT_RTOL,
    atol: float = DEFAULT_ATOL,
    strict: bool = False,
) -> ComparisonResult:
    """Estimate *spec* on *data* in each engine and collect the results.

    An engine that is missing or fails is recorded in
    :attr:`ComparisonResult.failures` and the rest still run — a machine without
    EViews should still be able to compare the other three. ``strict=True``
    re-raises instead.
    """
    definition = model_registry.get(spec.estimator)
    targets = (
        list(engines) if engines else [e for e in engine_registry.names() if definition.supports(e)]
    )

    missing = [column for column in spec.variables if column not in data.columns]
    if missing:
        raise EconEnvError(f"Columns not in the data: {', '.join(missing)}")

    comparison = ComparisonResult(spec=spec, rtol=rtol, atol=atol)
    for engine_name in targets:
        if not definition.supports(engine_name):
            comparison.failures[engine_name] = (
                f"{definition.display_name} has no {engine_name} adapter."
            )
            continue
        try:
            engine = engine_registry.get(engine_name)
            if not engine.available:
                comparison.failures[engine_name] = engine.info().error or "not installed"
                continue
            engine.ensure_started()
            comparison.results[engine_name] = engine._fit_ols(spec, data)
        except (EconEnvError, CapabilityError) as exc:
            if strict:
                raise
            comparison.failures[engine_name] = str(exc).replace("\n", " ")
            _log.info("%s could not run the model: %s", engine_name, exc)
        except Exception as exc:
            if strict:
                raise
            comparison.failures[engine_name] = f"{type(exc).__name__}: {exc}"
            _log.info("%s failed: %s", engine_name, exc)
    return comparison


def compare_ols(
    data: pd.DataFrame,
    formula: Optional[str] = None,
    *,
    depvar: Optional[str] = None,
    exog: Optional[Sequence[str]] = None,
    engines: Optional[Sequence[str]] = None,
    constant: bool = True,
    vcov: Optional[str] = None,
    **kwargs: Any,
) -> ComparisonResult:
    """Estimate the same OLS in every available engine.

    >>> compare_ols(df, "y ~ x1 + x2")                        # doctest: +SKIP
    >>> compare_ols(df, depvar="y", exog=["x1", "x2"])        # doctest: +SKIP
    """
    if formula:
        spec = ModelSpec.from_formula(formula, vcov=vcov)
        if not constant:
            spec.constant = False
    elif depvar:
        spec = ModelSpec(depvar=depvar, exog=list(exog or []), constant=constant, vcov=vcov)
    else:
        raise EconEnvError("Give either a formula or depvar/exog.")
    return run_spec(spec, data, engines, **kwargs)
