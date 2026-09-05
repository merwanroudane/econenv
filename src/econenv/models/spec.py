"""The engine-neutral model specification (brief §23, §24).

A :class:`ModelSpec` is an **intermediate representation**, not a string to be
regex-mangled into four dialects. Brief §24 is explicit about that, and for good
reason: ``y ~ x1 + x2`` is easy, but ``y ~ x1*x2 + factor(id) | z1`` is where a
regex approach starts silently producing the wrong model.

So the spec holds structured fields, and each engine's adapter renders them into
its own syntax. v0.1 renders OLS; the shape generalises, and
:mod:`econenv.models.registry` is where further estimators are added.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from ..exceptions import ModelSpecificationError

_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")


@dataclass
class ModelSpec:
    """What to estimate, independently of which program estimates it.

    Parameters
    ----------
    depvar:
        Dependent variable name.
    exog:
        Explanatory variable names, excluding the constant.
    estimator:
        Registry key — ``"ols"`` in v0.1.
    constant:
        Include an intercept.
    vcov:
        ``None``/``"nonrobust"`` for the classical covariance, or one of
        ``hc0``-``hc3``/``robust``. Engines differ in which HC variant they call
        "robust" and that difference is reported, not hidden.
    weights, cluster, time_var, panel_var, options:
        Carried for the estimators that need them; ignored by OLS.
    """

    depvar: str
    exog: List[str] = field(default_factory=list)
    estimator: str = "ols"
    constant: bool = True
    vcov: Optional[str] = None
    weights: Optional[str] = None
    cluster: Optional[str] = None
    time_var: Optional[str] = None
    panel_var: Optional[str] = None
    options: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.depvar = str(self.depvar).strip()
        self.exog = [str(v).strip() for v in self.exog if str(v).strip()]
        self.validate()

    # ------------------------------------------------------------------ #
    @classmethod
    def from_formula(cls, formula: str, **kwargs: Any) -> ModelSpec:
        """Parse a deliberately restricted ``y ~ x1 + x2`` formula.

        Only plain additive terms are accepted. Interactions, transforms and
        factor expansions are **rejected with a clear message** rather than
        half-supported — an engine-specific escape hatch (write the command
        yourself in ``%%stata`` / ``%%R``) is more honest than a translation
        that quietly differs between programs.
        """
        if "~" not in formula:
            raise ModelSpecificationError(
                f"{formula!r} is not a formula. Expected something like 'y ~ x1 + x2'."
            )
        lhs, rhs = formula.split("~", 1)
        depvar = lhs.strip()
        rhs = rhs.strip()

        constant = True
        rhs = rhs.replace("- 1", "-1").replace("+ 0", "+0")
        if "-1" in rhs or "+0" in rhs:
            constant = False
            rhs = rhs.replace("-1", "").replace("+0", "")

        terms = [t.strip() for t in rhs.split("+") if t.strip() and t.strip() != "1"]
        for term in terms:
            if not _NAME.match(term):
                raise ModelSpecificationError(
                    f"Term {term!r} is not a plain variable name.\n"
                    "ModelSpec.from_formula supports additive terms only, on purpose: "
                    "interactions and transforms mean different things in "
                    "statsmodels, R, Stata and EViews. Build the column first, or "
                    "write the command directly in that engine's cell magic."
                )
        kwargs.setdefault("constant", constant)
        return cls(depvar=depvar, exog=terms, **kwargs)

    # ------------------------------------------------------------------ #
    def validate(self) -> None:
        if not self.depvar:
            raise ModelSpecificationError("A dependent variable is required.")
        for name in [self.depvar, *self.exog]:
            if not _NAME.match(name):
                raise ModelSpecificationError(
                    f"{name!r} is not a usable variable name across all five engines."
                )
        if not self.exog and not self.constant:
            raise ModelSpecificationError("A model with no regressors and no constant is empty.")
        duplicates = {v for v in self.exog if self.exog.count(v) > 1}
        if duplicates:
            raise ModelSpecificationError(f"Repeated regressor(s): {sorted(duplicates)}")
        if self.depvar in self.exog:
            raise ModelSpecificationError(f"{self.depvar!r} appears on both sides of the equation.")
        if self.vcov is not None and self.vcov.lower() not in {
            "nonrobust",
            "robust",
            "hc0",
            "hc1",
            "hc2",
            "hc3",
        }:
            raise ModelSpecificationError(
                f"Unknown vcov {self.vcov!r}. Use nonrobust, robust, or hc0-hc3."
            )

    # ------------------------------------------------------------------ #
    @property
    def variables(self) -> List[str]:
        """Every column the estimation needs."""
        extra = [v for v in (self.weights, self.cluster, self.time_var, self.panel_var) if v]
        return [self.depvar, *self.exog, *extra]

    @property
    def formula(self) -> str:
        rhs = " + ".join(self.exog) if self.exog else "1"
        return f"{self.depvar} ~ {rhs}" + ("" if self.constant else " - 1")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "estimator": self.estimator,
            "depvar": self.depvar,
            "exog": list(self.exog),
            "constant": self.constant,
            "vcov": self.vcov,
            "weights": self.weights,
            "cluster": self.cluster,
            "time_var": self.time_var,
            "panel_var": self.panel_var,
            "options": dict(self.options),
        }

    def __str__(self) -> str:
        return f"{self.estimator.upper()}: {self.formula}" + (
            f" [vcov={self.vcov}]" if self.vcov else ""
        )


def parse_spec(text: str, **kwargs: Any) -> ModelSpec:
    """Parse either a formula or the ``%econ ols`` positional form ``y x1 x2``."""
    if "~" in text:
        return ModelSpec.from_formula(text, **kwargs)
    parts: Sequence[str] = text.split()
    if not parts:
        raise ModelSpecificationError("Nothing to estimate.")
    return ModelSpec(depvar=parts[0], exog=list(parts[1:]), **kwargs)
