"""Model registry and the capability matrix (brief §23, §25).

The registry answers "which estimator, in which engine, on this machine".
That last part matters: theoretical support is not the same as *runtime*
support. ``linearmodels`` may not be installed; EViews may not be licensed for
the module; the Stata edition may not include the command. So
:meth:`ModelRegistry.matrix` combines

* what the estimator declares each engine can do in principle, with
* whether that engine is actually available right now,

and reports both, rather than a static table that goes stale.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import pandas as pd

from ..exceptions import CapabilityError
from ..results import ModelResult


@dataclass
class ModelDefinition:
    """One estimator and the engines that claim to support it."""

    key: str
    display_name: str
    engines: Dict[str, str] = field(default_factory=dict)  # engine -> command shown to the user
    runner: Optional[Callable[..., ModelResult]] = None
    notes: str = ""
    status: str = "supported"  # supported | planned

    def supports(self, engine: str) -> bool:
        return engine in self.engines


class ModelRegistry:
    """Extensible collection of :class:`ModelDefinition`."""

    def __init__(self) -> None:
        self._models: Dict[str, ModelDefinition] = {}

    def add(self, definition: ModelDefinition) -> ModelDefinition:
        self._models[definition.key] = definition
        return definition

    def get(self, key: str) -> ModelDefinition:
        try:
            return self._models[key.lower()]
        except KeyError:
            raise CapabilityError(
                f"No estimator registered as {key!r}. Registered: {', '.join(self.keys())}"
            ) from None

    def keys(self) -> List[str]:
        return sorted(self._models)

    def definitions(self) -> List[ModelDefinition]:
        return [self._models[k] for k in self.keys()]

    def matrix(self, *, runtime: bool = True) -> pd.DataFrame:
        """The capability matrix, combining declared support with availability.

        Cell values: ``yes`` (declared and the engine is usable now),
        ``engine unavailable`` (declared, engine missing), ``planned``, ``—``.
        """
        from ..engines import registry as engine_registry

        available = set(engine_registry.available()) if runtime else set(engine_registry.names())
        engines = engine_registry.names()
        rows = []
        for definition in self.definitions():
            row = {"estimator": definition.display_name, "key": definition.key}
            for engine in engines:
                if not definition.supports(engine):
                    row[engine] = "—"
                elif definition.status == "planned":
                    row[engine] = "planned"
                elif runtime and engine not in available:
                    row[engine] = "engine unavailable"
                else:
                    row[engine] = "yes"
            rows.append(row)
        return pd.DataFrame(rows).set_index("key")


model_registry = ModelRegistry()

model_registry.add(
    ModelDefinition(
        key="ols",
        display_name="Linear regression (OLS)",
        engines={
            "python": "statsmodels.api.OLS(...).fit()",
            "r": "lm(y ~ x, data)",
            "stata": "regress y x",
            "eviews": "equation eq.ls y c x",
        },
        notes=(
            "All four use listwise deletion and a classical covariance by default. "
            "AIC/BIC normalisations differ — see docs/comparison.md."
        ),
    )
)

# Declared but not implemented in v0.1. Listed so the capability matrix is honest
# about the roadmap instead of silently omitting them (brief §23).
for key, display, engines in [
    (
        "logit",
        "Logistic regression",
        {"python": "sm.Logit", "r": "glm(binomial)", "stata": "logit", "eviews": "binary(l)"},
    ),
    (
        "probit",
        "Probit regression",
        {"python": "sm.Probit", "r": "glm(probit)", "stata": "probit", "eviews": "binary(n)"},
    ),
    (
        "iv2sls",
        "IV / 2SLS",
        {
            "python": "linearmodels.IV2SLS",
            "r": "AER::ivreg",
            "stata": "ivregress 2sls",
            "eviews": "tsls",
        },
    ),
    (
        "panel_fe",
        "Panel fixed effects",
        {
            "python": "linearmodels.PanelOLS",
            "r": "plm(within)",
            "stata": "xtreg, fe",
            "eviews": "ls(cx=f)",
        },
    ),
    (
        "panel_re",
        "Panel random effects",
        {
            "python": "linearmodels.RandomEffects",
            "r": "plm(random)",
            "stata": "xtreg, re",
            "eviews": "ls(cx=r)",
        },
    ),
    (
        "arima",
        "ARIMA",
        {
            "python": "sm.tsa.ARIMA",
            "r": "stats::arima",
            "stata": "arima",
            "eviews": "ls with ar/ma",
        },
    ),
    (
        "var",
        "Vector autoregression",
        {"python": "sm.tsa.VAR", "r": "vars::VAR", "stata": "var", "eviews": "var"},
    ),
    (
        "vecm",
        "Vector error correction",
        {"python": "sm.tsa.VECM", "r": "urca::cajorls", "stata": "vec", "eviews": "var(ec)"},
    ),
    (
        "ardl",
        "ARDL",
        {"python": "sm.tsa.ARDL", "r": "ARDL::ardl", "stata": "ardl", "eviews": "ardl"},
    ),
    (
        "garch",
        "GARCH",
        {"python": "arch.arch_model", "r": "rugarch", "stata": "arch", "eviews": "arch"},
    ),
    (
        "unitroot",
        "Unit-root tests",
        {"python": "sm.tsa.adfuller", "r": "urca::ur.df", "stata": "dfuller", "eviews": "uroot"},
    ),
    (
        "coint",
        "Cointegration tests",
        {
            "python": "sm.tsa.coint_johansen",
            "r": "urca::ca.jo",
            "stata": "vecrank",
            "eviews": "coint",
        },
    ),
    ("gmm", "GMM", {"python": "sm.sandbox.gmm", "r": "gmm::gmm", "stata": "gmm", "eviews": "gmm"}),
    (
        "did",
        "Difference-in-differences",
        {
            "python": "statsmodels formula",
            "r": "fixest::feols",
            "stata": "didregress",
            "eviews": "ls with dummies",
        },
    ),
    (
        "qreg",
        "Quantile regression",
        {"python": "sm.QuantReg", "r": "quantreg::rq", "stata": "qreg", "eviews": "qreg"},
    ),
]:
    model_registry.add(
        ModelDefinition(key=key, display_name=display, engines=engines, status="planned")
    )
