"""The Python engine (brief §6).

Python is the host kernel, so this engine deliberately does **not** build an
interpreter. It exists so that Python appears in ``%econ status``, in
reproducibility snapshots and — importantly — in the cross-engine comparison
table, where "what does statsmodels say" is one of the four answers being
compared.

Its "session" is the user's own namespace, so ``start``/``stop`` are bookkeeping
only and nothing the user typed is ever discarded.
"""

from __future__ import annotations

import importlib.metadata as _md
import io
import platform
import sys
from contextlib import redirect_stderr, redirect_stdout
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from ..exceptions import EngineExecutionError
from ..results import ExecutionResult, ModelResult
from ..schema import DatasetMetadata
from .base import BaseEngine, Capability, EngineState
from .registry import register

_INTERESTING = (
    "pandas",
    "numpy",
    "scipy",
    "statsmodels",
    "linearmodels",
    "matplotlib",
    "pyarrow",
    "ipython",
    "jupyterlab",
    "notebook",
)


@register
class PythonEngine(BaseEngine):
    """The host interpreter, exposed through the same interface as the others."""

    name = "python"
    display_name = "Python"
    declared_capabilities = (
        Capability.EXECUTE,
        Capability.PERSISTENT_SESSION,
        Capability.PUSH_FRAME,
        Capability.PULL_FRAME,
        Capability.PUSH_SCALAR,
        Capability.PULL_SCALAR,
        Capability.PULL_MATRIX,
        Capability.GRAPHICS,
        Capability.OLS,
        Capability.RESTART,
    )

    def __init__(self, **options: Any) -> None:
        super().__init__(**options)
        self._namespace: Dict[str, Any] = {"__name__": "econenv_python"}

    # -- lifecycle --------------------------------------------------------- #
    def _detect(self) -> bool:
        self._executable = sys.executable
        self._home = sys.prefix
        self._backend = platform.python_implementation().lower()
        self._state = EngineState.CONFIGURED
        return True

    def _start(self) -> None:
        self._namespace.setdefault("pd", pd)
        self._namespace.setdefault("np", np)

    def _stop(self) -> None:
        """No-op by design: killing the host interpreter is not ours to do."""

    def restart(self) -> None:
        """Clear only the EconEnv-managed namespace, never the user's kernel."""
        self._namespace = {"__name__": "econenv_python", "pd": pd, "np": np}
        self._state = EngineState.RUNNING

    def _version(self) -> Optional[str]:
        return platform.python_version()

    def _static_version(self) -> Optional[str]:
        return platform.python_version()

    def _info_detail(self) -> Dict[str, Any]:
        return {"prefix": sys.prefix, "packages": self.packages()}

    # -- execution --------------------------------------------------------- #
    def _execute(self, code: str, **kwargs: Any) -> ExecutionResult:
        namespace = kwargs.get("namespace") or self._namespace
        out, err = io.StringIO(), io.StringIO()
        result = ExecutionResult(engine=self.name, code=code)
        try:
            with redirect_stdout(out), redirect_stderr(err):
                compiled = compile(code, "<econenv-python>", "exec")
                exec(compiled, namespace)
        except Exception as exc:
            result.stdout, result.stderr = out.getvalue(), err.getvalue()
            raise EngineExecutionError(
                str(exc),
                engine=self.name,
                code=code,
                stdout=result.stdout,
                stderr=result.stderr,
                raw=exc,
            ) from exc
        result.stdout, result.stderr = out.getvalue(), err.getvalue()
        return result

    # -- data -------------------------------------------------------------- #
    def _push_frame(self, name: str, df: pd.DataFrame, **kwargs: Any) -> None:
        self._namespace[name] = df

    def _pull_frame(self, name: Optional[str], **kwargs: Any) -> pd.DataFrame:
        if name is None:
            frames = {k: v for k, v in self._namespace.items() if isinstance(v, pd.DataFrame)}
            if len(frames) != 1:
                raise EngineExecutionError(
                    f"Name a frame: the Python engine holds {len(frames)}.", engine=self.name
                )
            return next(iter(frames.values()))
        return self._namespace[name]

    def _push_scalar(self, name: str, value: Any, **kwargs: Any) -> None:
        self._namespace[name] = value

    def _pull_scalar(self, expression: str) -> Any:
        return eval(expression, self._namespace)

    def _pull_matrix(self, name: str) -> np.ndarray:
        return np.asarray(self._namespace[name])

    # -- models ------------------------------------------------------------ #
    def _fit_ols(
        self, spec, data: pd.DataFrame, meta: Optional[DatasetMetadata] = None
    ) -> ModelResult:
        """OLS through statsmodels, with the conventions spelled out.

        statsmodels' default is a non-robust (homoskedastic) covariance and it
        drops rows with any missing value in the used columns. Both are recorded
        on the result so the comparison table can attribute a difference rather
        than hide it.
        """
        try:
            import statsmodels.api as sm
        except ImportError as exc:  # pragma: no cover
            raise EngineExecutionError(
                "statsmodels is required for the Python OLS adapter.",
                engine=self.name,
                hint="pip install statsmodels",
                raw=exc,
            ) from exc

        columns = [spec.depvar, *spec.exog]
        frame = data.loc[:, columns].apply(pd.to_numeric, errors="coerce").dropna()
        y = frame[spec.depvar]
        X = frame[list(spec.exog)]  # noqa: N806 - design matrix, statistical convention
        if spec.constant:
            X = sm.add_constant(X, has_constant="add")  # noqa: N806
        cov_kwargs = {"cov_type": spec.vcov} if spec.vcov and spec.vcov != "nonrobust" else {}
        fit = sm.OLS(y, X).fit(**cov_kwargs)
        ci = fit.conf_int()
        return ModelResult.from_arrays(
            engine=self.name,
            model="OLS",
            terms=[_canonical_term(t) for t in fit.params.index],
            coef=fit.params.to_numpy(),
            std_err=fit.bse.to_numpy(),
            stat=fit.tvalues.to_numpy(),
            pvalue=fit.pvalues.to_numpy(),
            ci_lower=ci.iloc[:, 0].to_numpy(),
            ci_upper=ci.iloc[:, 1].to_numpy(),
            depvar=spec.depvar,
            nobs=int(fit.nobs),
            df_model=int(fit.df_model),
            df_resid=int(fit.df_resid),
            r2=float(fit.rsquared),
            r2_adj=float(fit.rsquared_adj),
            loglik=float(fit.llf),
            aic=float(fit.aic),
            bic=float(fit.bic),
            rmse=float(np.sqrt(fit.mse_resid)),
            fstat=float(fit.fvalue) if fit.fvalue is not None else None,
            fstat_pvalue=float(fit.f_pvalue) if fit.f_pvalue is not None else None,
            vcov_type=spec.vcov or "nonrobust",
            engine_version=platform.python_version(),
            command="statsmodels.api.OLS(...).fit()",
            raw=fit,
            notes=[
                "statsmodels AIC/BIC use -2*llf + 2k / -2*llf + k*ln(n); "
                "Stata and EViews normalise differently — see docs/comparison.md.",
            ],
        )

    # -- extras ------------------------------------------------------------ #
    @staticmethod
    def packages() -> Dict[str, Optional[str]]:
        """Versions of the packages worth recording in a snapshot."""
        out: Dict[str, Optional[str]] = {}
        for name in _INTERESTING:
            try:
                out[name] = _md.version(name)
            except _md.PackageNotFoundError:
                out[name] = None
        return out

    @staticmethod
    def all_packages() -> List[Dict[str, str]]:
        """Every installed distribution — the full reproducibility record."""
        seen: Dict[str, str] = {}
        for dist in _md.distributions():
            meta_name = dist.metadata["Name"]
            if meta_name:
                seen[meta_name] = dist.version or ""
        return [
            {"name": k, "version": v} for k, v in sorted(seen.items(), key=lambda kv: kv[0].lower())
        ]

    @property
    def namespace(self) -> Dict[str, Any]:
        return self._namespace


def _canonical_term(term: str) -> str:
    """Normalise the intercept name so engines line up in the comparison table."""
    return "_cons" if str(term) in {"const", "Intercept", "(Intercept)", "C"} else str(term)
