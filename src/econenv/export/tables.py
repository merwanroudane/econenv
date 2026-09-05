"""Regression tables, in the shape journals actually print them.

Two layouts, because the two audiences want different things.

**Journal** is what goes in a paper: one column per model, the coefficient with
significance stars, the standard error beneath it in parentheses, and a foot of
sample size and fit statistics. It is the layout every economics journal uses and
the one you cannot get from a bare ``summary()``.

**Full** is what goes in your own notes: every statistic the engine reported —
coefficient, standard error, test statistic, p-value and confidence interval —
one row per term, nothing folded away.

Neither invents anything. A statistic the engine did not report stays blank
rather than being computed here under different assumptions, because a table
that quietly mixes two engines' conventions is worse than one with a gap in it.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Union

import numpy as np
import pandas as pd

from ..results import ModelResult

#: Default thresholds. Economics convention; override with ``stars=``.
DEFAULT_STARS = ((0.01, "***"), (0.05, "**"), (0.10, "*"))

#: Fit statistics printed at the foot, in this order, when present.
FOOT_ORDER = (
    ("nobs", "Observations", "{:,.0f}"),
    ("r2", "R²", "{:.4f}"),
    ("r2_adj", "Adjusted R²", "{:.4f}"),
    ("rmse", "Residual s.e.", "{:.4f}"),
    ("fstat", "F statistic", "{:.3f}"),
    ("loglik", "Log likelihood", "{:.3f}"),
    ("aic", "AIC", "{:.3f}"),
    ("bic", "BIC", "{:.3f}"),
)


def stars_for(pvalue: Optional[float], levels: Sequence = DEFAULT_STARS) -> str:
    """Significance markers for *pvalue*, or "" when it is unknown."""
    if pvalue is None or (isinstance(pvalue, float) and np.isnan(pvalue)):
        return ""
    for threshold, mark in levels:
        if pvalue < threshold:
            return mark
    return ""


def _as_models(obj: Any) -> Dict[str, ModelResult]:
    """Accept a model, a list of them, a dict, or a ComparisonResult."""
    if isinstance(obj, ModelResult):
        return {obj.engine: obj}
    if isinstance(obj, dict):
        return dict(obj)
    if hasattr(obj, "results") and isinstance(obj.results, dict):
        return dict(obj.results)  # ComparisonResult
    if isinstance(obj, (list, tuple)):
        out: Dict[str, ModelResult] = {}
        for index, item in enumerate(obj):
            if not isinstance(item, ModelResult):
                raise TypeError(f"item {index} is a {type(item).__name__}, not a ModelResult")
            key = item.engine if item.engine not in out else f"{item.engine}_{index}"
            out[key] = item
        return out
    raise TypeError(
        f"Cannot build a table from {type(obj).__name__}. "
        "Give a ModelResult, a list of them, or a ComparisonResult."
    )


def journal_table(
    obj: Any,
    *,
    stars: Sequence = DEFAULT_STARS,
    digits: int = 4,
    se_in_parentheses: bool = True,
    column_labels: Optional[Sequence[str]] = None,
    foot: Sequence[str] = ("nobs", "r2", "r2_adj"),
) -> pd.DataFrame:
    """The layout a paper prints: estimate with stars, standard error beneath.

    Returns a DataFrame of strings — already formatted — because the whole point
    is the presentation. Use :func:`full_table` when you want numbers to compute
    with.
    """
    models = _as_models(obj)
    if not models:
        raise ValueError("No models to tabulate.")

    labels = list(column_labels) if column_labels else [_label(k, m) for k, m in models.items()]
    if len(labels) != len(models):
        raise ValueError(f"{len(labels)} column labels for {len(models)} models.")

    # Union of terms, in the order the first model lists them, then any extras.
    terms: List[str] = []
    for model in models.values():
        if model.coefficients is None:
            continue
        for term in model.coefficients.index:
            if term not in terms:
                terms.append(str(term))

    rows: List[List[str]] = []
    index: List[str] = []
    for term in terms:
        estimate_row, se_row = [], []
        for model in models.values():
            coef = _cell(model, term, "coef")
            pval = _cell(model, term, "pvalue")
            stderr = _cell(model, term, "std_err")
            if coef is None:
                estimate_row.append("")
                se_row.append("")
                continue
            estimate_row.append(f"{coef:.{digits}f}{stars_for(pval, stars)}")
            if stderr is None:
                se_row.append("")
            elif se_in_parentheses:
                se_row.append(f"({stderr:.{digits}f})")
            else:
                se_row.append(f"{stderr:.{digits}f}")
        index.append(term)
        rows.append(estimate_row)
        index.append("")  # the standard-error line carries no label
        rows.append(se_row)

    for key in foot:
        spec = next((f for f in FOOT_ORDER if f[0] == key), None)
        if spec is None:
            continue
        _, label, fmt = spec
        values = [getattr(model, key, None) for model in models.values()]
        if all(v is None for v in values):
            continue
        index.append(label)
        rows.append([("" if v is None else fmt.format(v)) for v in values])

    table = pd.DataFrame(rows, index=index, columns=labels)
    table.attrs["econenv_style"] = "journal"
    table.attrs["econenv_stars"] = list(stars)
    table.attrs["econenv_depvar"] = next((m.depvar for m in models.values() if m.depvar), None)
    return table


def full_table(obj: Any, *, digits: int = 6) -> pd.DataFrame:
    """Every statistic the engine reported, one row per term per model."""
    models = _as_models(obj)
    frames = []
    for key, model in models.items():
        if model.coefficients is None:
            continue
        frame = model.coefficients.copy()
        frame.insert(0, "term", frame.index.astype(str))
        frame.insert(0, "engine", key)
        frames.append(frame.reset_index(drop=True))
    if not frames:
        raise ValueError("None of these models reported coefficients.")
    table = pd.concat(frames, ignore_index=True)
    numeric = table.select_dtypes(include="number").columns
    table[numeric] = table[numeric].round(digits)
    table.attrs["econenv_style"] = "full"
    return table


def build_table(obj: Any, style: str = "journal", **kwargs: Any) -> pd.DataFrame:
    """``style="journal"`` or ``"full"``."""
    if style == "journal":
        return journal_table(obj, **kwargs)
    if style == "full":
        return full_table(obj, **kwargs)
    raise ValueError(f"Unknown table style {style!r}. Use 'journal' or 'full'.")


def star_note(stars: Sequence = DEFAULT_STARS) -> str:
    """The legend that belongs under a starred table."""
    parts = [f"{mark} p < {threshold:g}" for threshold, mark in stars]
    return "Standard errors in parentheses. " + ", ".join(parts) + "."


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _label(key: str, model: ModelResult) -> str:
    display = {
        "python": "Python",
        "r": "R",
        "stata": "Stata",
        "eviews": "EViews",
        "matlab": "MATLAB",
    }.get(key, key)
    return display


def _cell(model: ModelResult, term: str, column: str) -> Optional[float]:
    frame = model.coefficients
    if frame is None or term not in frame.index or column not in frame.columns:
        return None
    value = frame.loc[term, column]
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    try:
        return float(value)  # type: ignore[arg-type]  # a coefficient cell may be any dtype
    except (TypeError, ValueError):
        return None


TableLike = Union[pd.DataFrame, ModelResult]
