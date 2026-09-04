"""Stata via PyStata (brief §8).

Two facts from the Phase 0 audit shape this adapter:

* ``pystata`` is **not on PyPI**. It ships inside the Stata installation at
  ``<STATA_HOME>/utilities/pystata``. EconEnv puts that directory on
  ``sys.path`` itself; ``stata_setup`` is used when present but is not required.
* PyStata already provides ``%stata`` / ``%%stata`` / ``%mata`` and a Stata
  completer. Brief §8 and §61 say do not reimplement those, so EconEnv
  **delegates** to them and confines itself to discovery, edition detection,
  lifecycle, data transfer and result wrapping.

``pystata.config.init()`` can be called **once per process**. There is no
supported way to re-initialise it against a different edition, so ``restart()``
resets EconEnv's view and Stata's data, and says plainly that a full swap needs
a fresh kernel.
"""

from __future__ import annotations

import io
import re
import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from .. import config as _config
from .. import discovery
from ..exceptions import (
    EngineExecutionError,
    EngineStartError,
    EngineUnavailableError,
)
from ..results import ExecutionResult, ModelResult
from ..schema import DatasetMetadata
from .base import BaseEngine, Capability
from .registry import register


@register
class StataEngine(BaseEngine):
    """Adapter around StataCorp's own ``pystata`` package."""

    name = "stata"
    display_name = "Stata"
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
    )

    def __init__(self, **options: Any) -> None:
        super().__init__(**options)
        self._installation: Optional[discovery.Installation] = None
        self._candidates: List[discovery.Installation] = []
        self._pystata: Any = None
        self._stata: Any = None
        self._sfi_module: Any = None
        self._magics_loaded = False

    # ------------------------------------------------------------------ #
    # detection
    # ------------------------------------------------------------------ #
    def _detect(self) -> bool:
        configured = self.options.get("home") or _config.get_option("stata", "home")
        self._candidates = discovery.find_stata(configured)
        usable = [i for i in self._candidates if i.detail.get("pystata")]
        if not usable:
            if self._candidates:
                paths = ", ".join(str(i.home) for i in self._candidates)
                self._detect_error = (
                    f"Stata found at {paths}, but none contains utilities/pystata. "
                    "PyStata needs Stata 17 or newer."
                )
            return False
        self._installation = usable[0]
        self._home = str(self._installation.home)
        self._executable = str(self._installation.executable)
        self._backend = "pystata"
        return True

    def _edition(self) -> Optional[str]:
        override = self.options.get("edition") or _config.get_option("stata", "edition")
        if override:
            return str(override).lower()
        return self._installation.edition if self._installation else None

    def _static_version(self) -> Optional[str]:
        return self._installation.version if self._installation else None

    def _info_detail(self) -> Dict[str, Any]:
        detail: Dict[str, Any] = {
            "candidates": [str(i) for i in self._candidates],
            "pystata_path": self._installation.detail.get("pystata")
            if self._installation
            else None,
            "magics": "pystata (%stata, %%stata, %mata, %%mata)"
            if self._magics_loaded
            else "not loaded",
        }
        if self._pystata is not None:
            detail["pystata_version"] = getattr(
                self._pystata, "__version__", None
            ) or _pystata_version(self._pystata)
        return detail

    # ------------------------------------------------------------------ #
    # lifecycle
    # ------------------------------------------------------------------ #
    def _start(self) -> None:
        if self._installation is None:
            raise EngineUnavailableError(
                "No Stata installation with PyStata was found.",
                engine=self.name,
                hint='Set it explicitly: %econ config stata.home "C:/Program Files/Stata19"',
            )
        utilities = str(Path(self._installation.home) / "utilities")
        if utilities not in sys.path:
            sys.path.insert(0, utilities)

        try:
            import pystata
        except ImportError as exc:
            raise EngineStartError(
                f"Could not import pystata from {utilities}.",
                engine=self.name,
                raw=exc,
                hint="Check that Stata 17+ is installed and utilities/pystata exists.",
            ) from exc

        self._pystata = pystata
        edition = self._edition() or "be"
        splash = bool(self.options.get("splash", _config.get_option("stata", "splash", False)))

        if not pystata.config.is_stata_initialized():
            try:
                # Silence the banner; PyStata prints it even with splash=False.
                with redirect_stdout(io.StringIO()):
                    pystata.config.init(edition, splash=splash)
            except Exception as exc:
                raise EngineStartError(
                    f"pystata.config.init({edition!r}) failed: {exc}",
                    engine=self.name,
                    raw=exc,
                    hint=(
                        "Check the edition is the one you are licensed for "
                        "(be / se / mp) — `%econ config stata.edition mp`."
                    ),
                ) from exc

        from pystata import stata as _stata

        self._stata = _stata

        graph_format = _config.get_option("stata", "graph_format", "svg")
        if graph_format:
            try:
                pystata.config.set_graph_format(graph_format)
            except Exception as exc:
                self.log.debug("set_graph_format(%s) failed: %s", graph_format, exc)

    def _stop(self) -> None:
        """Drop EconEnv's handles.

        ``pystata.config.shutdown()`` is deliberately not called: PyStata cannot
        be re-initialised afterwards in the same process, so calling it would
        turn ``%econ stop stata`` into "restart your kernel".
        """
        self._stata = None

    def restart(self) -> None:
        """Clear Stata's data and reset the session, in-process.

        A true re-init (e.g. switching edition) is impossible without a new
        kernel; that limitation is reported rather than worked around.
        """
        if self.running and self._stata is not None:
            try:
                self._stata.run("clear all", quietly=True)
            except Exception as exc:
                self.log.debug("clear all failed: %s", exc)
            return
        super().restart()

    def _version(self) -> Optional[str]:
        value = self._scalar("c(stata_version)")
        return str(value) if value is not None else None

    # ------------------------------------------------------------------ #
    # execution
    # ------------------------------------------------------------------ #
    def _execute(self, code: str, **kwargs: Any) -> ExecutionResult:
        quietly = bool(kwargs.get("quietly", False))
        echo = bool(kwargs.get("echo", False))
        buffer = io.StringIO()
        result = ExecutionResult(engine=self.name, code=code)
        try:
            with redirect_stdout(buffer):
                self._stata.run(code, quietly=quietly, echo=echo)
        except Exception as exc:
            result.stdout = buffer.getvalue()
            raise EngineExecutionError(
                _clean_stata_error(exc),
                engine=self.name,
                code=code,
                stdout=result.stdout,
                raw=exc,
                hint="Run the command with `set trace on` in Stata for a full traceback.",
            ) from exc
        result.stdout = buffer.getvalue()
        rc = self._scalar("c(rc)")
        if rc not in (None, 0, 0.0):
            result.success = False
            result.error = f"Stata return code r({int(rc)})"
        result.metadata["rc"] = rc
        return result

    # ------------------------------------------------------------------ #
    # data
    # ------------------------------------------------------------------ #
    def _push_frame(self, name: str, df: pd.DataFrame, **kwargs: Any) -> None:
        from ..bridges.stata_bridge import push_frame

        push_frame(self, name, df, **kwargs)

    def _pull_frame(self, name: Optional[str], **kwargs: Any) -> pd.DataFrame:
        from ..bridges.stata_bridge import pull_frame

        return pull_frame(self, name, **kwargs)

    def _push_scalar(self, name: str, value: Any, **kwargs: Any) -> None:
        if isinstance(value, str):
            escaped = value.replace('"', '""')
            self._stata.run(f'global {name} "{escaped}"', quietly=True)
        else:
            self._stata.run(f"scalar {name} = {float(value)!r}", quietly=True)

    def _pull_scalar(self, expression: str) -> Any:
        value = self._scalar(expression)
        if value is None:
            raise EngineExecutionError(
                f"Stata could not evaluate {expression!r}.", engine=self.name, code=expression
            )
        return value

    def _pull_matrix(self, name: str) -> np.ndarray:
        from ..bridges.stata_bridge import pull_matrix

        return pull_matrix(self, name)

    @property
    def _sfi(self) -> Any:
        """Stata's own Function Interface, importable once PyStata is initialised."""
        if self._sfi_module is None:
            import sfi

            self._sfi_module = sfi
        return self._sfi_module

    def _scalar(self, expression: str) -> Any:
        """Evaluate a Stata expression at **full precision**.

        ``display`` is not used for numbers: it formats to Stata's default
        significant digits, which silently rounds a coefficient to about nine
        figures — enough to make two engines look like they disagree when they
        do not. The Stata Function Interface returns the stored double instead,
        and ``get_return``/``get_ereturn`` return r()/e() as numpy values.

        Returns ``None`` rather than raising: callers use this for optional
        metadata lookups.
        """
        if self._stata is None:
            return None
        expression = expression.strip()

        match = _RESULT_REF.match(expression)
        if match:
            kind, key = match.group(1), expression
            getter = {
                "e": self._stata.get_ereturn,
                "r": self._stata.get_return,
                "s": self._stata.get_sreturn,
            }[kind]
            try:
                value = getter().get(key)
            except Exception as exc:
                self.log.debug("%s lookup failed: %s", key, exc)
                value = None
            if value is not None:
                return value
            # Macro-valued e() results (e(cmd), e(vcetype)) are not in the dict.
            try:
                text = self._sfi.Macro.getGlobal(key)
            except Exception:
                return None
            return text or None

        try:
            sfi = self._sfi
        except ImportError:  # pragma: no cover - PyStata always ships sfi
            return None

        if expression.startswith("c(") or expression.startswith("`"):
            try:
                text = sfi.Macro.getGlobal(expression)
            except Exception:
                text = ""
            return _numeric_or_text(text) if text else None

        try:
            value = sfi.Scalar.getValue(expression)
        except Exception:
            value = None
        if value is not None:
            return value

        # Anything else — an arbitrary expression — still needs Stata to
        # evaluate it. %21x is the exact hexadecimal double, so nothing rounds.
        buffer = io.StringIO()
        try:
            with redirect_stdout(buffer):
                self._stata.run(f"display %21x ({expression})", quietly=False)
        except Exception as exc:
            self.log.debug("scalar %s failed: %s", expression, exc)
            return None
        text = buffer.getvalue().strip().splitlines()
        if not text:
            return None
        return _from_hex_double(text[-1].strip())

    # ------------------------------------------------------------------ #
    # models
    # ------------------------------------------------------------------ #
    def _fit_ols(
        self, spec, data: pd.DataFrame, meta: Optional[DatasetMetadata] = None
    ) -> ModelResult:
        """``regress`` with the results read out of ``e()``.

        Stata drops missing rows listwise and defaults to a classical
        (non-robust) VCE, matching statsmodels' default; ``vce(robust)`` is
        requested when the spec asks for a robust covariance.
        """
        from ..bridges.stata_bridge import push_frame

        columns = [spec.depvar, *spec.exog]
        push_frame(self, "__econenv_ols", data.loc[:, columns], clear=True)

        command = f"regress {spec.depvar} {' '.join(spec.exog)}"
        if not spec.constant:
            command += ", noconstant"
        if spec.vcov and spec.vcov.lower() in {"hc0", "hc1", "hc2", "hc3", "robust"}:
            command += (", " if spec.constant else " ") + "vce(robust)"
        exec_result = self.execute(command, quietly=True)

        # r(table) rows: b, se, t, pvalue, ll, ul, df, crit, eform.
        # Read through sfi so the values keep full double precision.
        names = self._matrix_colnames("r(table)") or self._matrix_colnames("e(b)")
        table = self._pull_matrix("r(table)")
        terms = [_canonical_stata_term(n) for n in names]
        criteria = self._information_criteria()

        return ModelResult.from_arrays(
            engine=self.name,
            model="OLS",
            terms=terms,
            coef=table[0],
            std_err=table[1],
            stat=table[2],
            pvalue=table[3],
            ci_lower=table[4],
            ci_upper=table[5],
            depvar=spec.depvar,
            nobs=_as_int(self._scalar("e(N)")),
            df_model=_as_int(self._scalar("e(df_m)")),
            df_resid=_as_int(self._scalar("e(df_r)")),
            r2=_as_float(self._scalar("e(r2)")),
            r2_adj=_as_float(self._scalar("e(r2_a)")),
            loglik=_as_float(self._scalar("e(ll)")),
            aic=criteria["aic"],
            bic=criteria["bic"],
            rmse=_as_float(self._scalar("e(rmse)")),
            fstat=_as_float(self._scalar("e(F)")),
            vcov_type=str(self._scalar("e(vcetype)") or "nonrobust"),
            engine_version=self.version(),
            command=command,
            raw=exec_result.stdout,
            notes=[
                "AIC/BIC come from `estat ic`; Stata's normalisation is "
                "-2ll + 2k with k = e(rank) + 1, which differs from statsmodels "
                "and from EViews — see docs/comparison.md.",
            ],
        )

    def _matrix_colnames(self, name: str) -> List[str]:
        """Column names of a Stata matrix, via the Function Interface."""
        try:
            return [str(n) for n in self._sfi.Matrix.getColNames(name)]
        except Exception as exc:
            self.log.debug("colnames(%s) failed: %s", name, exc)
            return []

    def _information_criteria(self) -> Dict[str, Optional[float]]:
        """AIC and BIC from ``estat ic``.

        Stata does not put them in ``e()`` after ``regress`` — they only exist
        once ``estat ic`` has run, which is why other tools report them as
        missing for Stata. Running it here means the comparison table has a
        real number instead of a hole, and the note explaining Stata's
        normalisation still travels with the result.
        """
        try:
            self.execute("estat ic", quietly=True)
            table = np.asarray(self._sfi.Matrix.get("r(S)"), dtype=float)
            names = [str(n).lower() for n in self._sfi.Matrix.getColNames("r(S)")]
        except Exception as exc:
            self.log.debug("estat ic unavailable: %s", exc)
            return {"aic": None, "bic": None, "loglik": None}
        row = table[0] if table.ndim == 2 else table

        def pick(label: str) -> Optional[float]:
            return float(row[names.index(label)]) if label in names else None

        return {"aic": pick("aic"), "bic": pick("bic"), "loglik": pick("ll")}

    # ------------------------------------------------------------------ #
    # magics delegation
    # ------------------------------------------------------------------ #
    def load_official_magics(self, ipython: Any) -> bool:
        """Make sure PyStata's own magics are live. Returns True when they are.

        PyStata has no ``load_ipython_extension``. ``pystata.config.init()``
        imports ``pystata.ipython.stpymagic``, whose module body calls
        ``get_ipython().register_magics(PyStataMagic)`` — so starting the engine
        inside an IPython session registers ``%stata`` as a side effect. When
        the engine was started outside one, importing that module here does the
        registration.

        Either way the result is **checked against the magics manager** rather
        than assumed, because EconEnv reports magic ownership to the user and a
        wrong claim there is worse than no claim.
        """
        if self._magics_loaded:
            return True
        self.ensure_started()
        try:
            import pystata.ipython.stpymagic  # noqa: F401
        except Exception as exc:
            self.log.warning("could not import pystata's magics: %s", exc)
            return False

        manager: Any = getattr(ipython, "magics_manager", None)
        registered = manager is not None and "stata" in manager.magics.get("cell", {})
        if not registered:
            # Started headless: register explicitly against this shell.
            try:
                from pystata.ipython.stpymagic import PyStataMagic

                ipython.register_magics(PyStataMagic)
                registered = True
            except Exception as exc:
                self.log.warning("could not register pystata's magics: %s", exc)
                return False

        self._magics_loaded = registered
        return registered


#: Matches a Stata stored-result reference such as ``e(N)`` or ``r(table)``.
_RESULT_REF = re.compile(r"^([ers])\(([A-Za-z_][A-Za-z0-9_]*)\)$")


def _numeric_or_text(text: str) -> Any:
    """Cast a Stata macro's text to a number when it is one."""
    try:
        return int(text) if text.lstrip("-").isdigit() else float(text)
    except ValueError:
        return text


def _from_hex_double(text: str) -> Any:
    """Decode Stata's ``%21x`` hexadecimal double format without losing bits."""
    token = text.strip()
    try:
        return float.fromhex(token)
    except ValueError:
        return _numeric_or_text(token)


def _pystata_version(module: Any) -> Optional[str]:
    try:
        from pystata import version as _v

        return getattr(_v, "version", None)
    except Exception:
        return None


def _clean_stata_error(exc: BaseException) -> str:
    """Turn PyStata's ``SystemError`` text into something readable."""
    text = str(exc).strip()
    text = re.sub(r"^Exception occurred\.\s*", "", text)
    match = re.search(r"r\((\d+)\)", text)
    if match:
        return f"{text} (Stata return code r({match.group(1)}); `help r({match.group(1)})`)"
    return text or "Stata rejected the command."


def _canonical_stata_term(term: str) -> str:
    return "_cons" if term == "_cons" else term


def _as_int(value: Any) -> Optional[int]:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> Optional[float]:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return None if np.isnan(result) else result
