"""MATLAB, through the official MATLAB Engine API for Python.

MathWorks ships a Python package inside every MATLAB installation
(``extern/engines/python``) and publishes the same thing on PyPI as
``matlabengine``, versioned to match the release: ``24.1.x`` for R2024a,
``25.1.x`` for R2025a. EconEnv drives that rather than a console subprocess,
because it is the supported interface and it exchanges arrays natively instead
of through printed text.

Two things about it shape this adapter.

**Starting MATLAB is slow** — around a minute cold. So the session is started
once and reused, and ``detect()`` never starts anything: it reads the disk and
the registry only, which is what makes ``%econ status`` safe to run.

**The engine version must match the interpreter.** R2024a's engine supports
Python 3.9-3.11 and refuses anything newer, so a mismatch produces an import
error rather than a wrong answer. The diagnostic says which pin is needed
instead of leaving the user to work it out.
"""

from __future__ import annotations

import contextlib
import glob
import io
import os
import platform
import re
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from .. import config as _config
from ..exceptions import (
    DataTransferError,
    EngineExecutionError,
    EngineStartError,
    EngineUnavailableError,
)
from ..results import ExecutionResult, Figure
from .base import BaseEngine, Capability
from .registry import register

#: Release folders, e.g. ``R2024a``. Sorted newest-first by year then letter.
_RELEASE_RE = re.compile(r"^R(\d{4})([ab])$", re.IGNORECASE)

#: Engine-API series that matches each release, for the pip hint.
_ENGINE_SERIES = {"2024a": "24.1", "2024b": "24.2", "2025a": "25.1", "2025b": "25.2"}


def _release_key(name: str) -> tuple:
    match = _RELEASE_RE.match(name)
    if not match:
        return (0, "")
    return (int(match.group(1)), match.group(2).lower())


def find_matlab() -> List[Path]:
    """MATLAB installation roots, newest release first."""
    roots: List[Path] = []
    configured = _config.get_option("matlab", "home", None)
    if configured:
        roots.append(Path(configured))
    if env := os.environ.get("MATLAB_ROOT"):
        roots.append(Path(env))

    if platform.system() == "Windows":
        bases = [
            Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "MATLAB",
            Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "MATLAB",
        ]
    elif platform.system() == "Darwin":
        bases = [Path("/Applications")]
    else:
        bases = [Path("/usr/local/MATLAB"), Path("/opt/MATLAB")]

    for base in bases:
        if not base.is_dir():
            continue
        for match in glob.glob(str(base / "R20*")) + glob.glob(str(base / "MATLAB_R20*.app")):
            roots.append(Path(match))

    seen, out = set(), []
    for root in roots:
        if root.is_dir() and str(root).lower() not in seen:
            seen.add(str(root).lower())
            out.append(root)
    out.sort(key=lambda p: _release_key(p.name), reverse=True)
    return out


def engine_api_release() -> Optional[str]:
    """Which MATLAB release the installed Engine API will start.

    The pip package is versioned to the release — ``24.1.x`` is R2024a — and it
    starts *that* MATLAB, not the newest one on disk. Reporting the newest
    install would repeat the mistake the EViews adapter used to make: naming a
    version the user is not actually running.
    """
    import importlib.metadata as md

    try:
        version = md.version("matlabengine")
    except Exception:
        return None
    parts = version.split(".")
    if len(parts) < 2 or not parts[0].isdigit():
        return None
    for release, series in _ENGINE_SERIES.items():
        if series == f"{parts[0]}.{parts[1]}":
            return f"R{release}"
    return None


def _engine_importable() -> tuple:
    """``(importable, error)`` for ``matlab.engine``, without starting MATLAB."""
    try:
        import matlab.engine  # noqa: F401

        return True, None
    except Exception as exc:  # ImportError, and MathWorks' own version errors
        return False, f"{type(exc).__name__}: {exc}"


@register
class MatlabEngine(BaseEngine):
    """MATLAB as an EconEnv engine."""

    name = "matlab"
    display_name = "MATLAB"
    declared_capabilities = (
        Capability.EXECUTE,
        Capability.PERSISTENT_SESSION,
        Capability.PUSH_FRAME,
        Capability.PULL_FRAME,
        Capability.PUSH_SCALAR,
        Capability.PULL_SCALAR,
        Capability.PULL_MATRIX,
        Capability.GRAPHICS,
        Capability.RESTART,
        Capability.OLS,
    )

    def __init__(self, **options: Any) -> None:
        super().__init__(**options)
        self._eng: Any = None
        self._installs: List[Path] = []
        self._tempdir: Optional[Path] = None
        self._seen_figures: set = set()
        self._release: Optional[str] = None

    # ------------------------------------------------------------------ #
    # detection
    # ------------------------------------------------------------------ #
    def _detect(self) -> bool:
        self._installs = find_matlab()
        importable, error = _engine_importable()

        if not self._installs and not importable:
            self._detect_error = "No MATLAB installation found and matlab.engine is not importable."
            return False

        if self._installs:
            # Prefer the release the Engine API will actually start over the
            # newest one installed; they are frequently not the same.
            target = engine_api_release()
            chosen = next(
                (p for p in self._installs if target and p.name.lower() == target.lower()),
                self._installs[0],
            )
            self._home = str(chosen)
            exe = chosen / "bin" / ("matlab.exe" if platform.system() == "Windows" else "matlab")
            self._executable = str(exe) if exe.exists() else None
            self._release = chosen.name

        if not importable:
            release = self._installs[0].name if self._installs else "your release"
            series = _ENGINE_SERIES.get(release.lower().lstrip("r"), "")
            pin = (
                f'pip install "matlabengine=={series}.*"' if series else "pip install matlabengine"
            )
            self._detect_error = (
                f"MATLAB {release} is installed but the Engine API for Python is not: "
                f"{error}. The engine version must match the release: {pin}"
            )
            return False

        self._backend = "matlab.engine"
        return True

    def _static_version(self) -> Optional[str]:
        return getattr(self, "_release", None) or (
            self._installs[0].name if self._installs else None
        )

    def _info_detail(self) -> Dict[str, Any]:
        importable, error = _engine_importable()
        return {
            "installations": [str(p) for p in self._installs],
            "engine_api": "matlab.engine" if importable else f"unavailable ({error})",
            "engine_api_release": engine_api_release() or "unknown",
            "note": (
                "Starting MATLAB takes about a minute; the session is reused until "
                "you stop or restart it."
            ),
        }

    # ------------------------------------------------------------------ #
    # lifecycle
    # ------------------------------------------------------------------ #
    def _start(self) -> None:
        try:
            import matlab.engine
        except Exception as exc:
            raise EngineUnavailableError(
                "The MATLAB Engine API for Python is not importable.",
                engine=self.name,
                raw=exc,
                hint=self._detect_error or 'pip install "matlabengine==24.1.*"',
            ) from exc

        options = str(
            self.options.get("startup") or _config.get_option("matlab", "startup", "-nodesktop")
        )
        shared = self.options.get("shared") or _config.get_option("matlab", "shared", None)
        try:
            if shared:
                # Attach to a MATLAB the user already has open, if they ran
                # `matlab.engine.shareEngine` in it. Much faster than a cold start.
                self._eng = matlab.engine.connect_matlab(str(shared))
            else:
                self._eng = matlab.engine.start_matlab(options)
        except Exception as exc:
            raise EngineStartError(
                "Could not start MATLAB.",
                engine=self.name,
                raw=exc,
                hint=(
                    "A cold start takes about a minute. If MATLAB is already open, "
                    "run `matlab.engine.shareEngine` in it and set "
                    "`%econ config matlab.shared MATLAB_shared` to attach instead."
                ),
            ) from exc

    def _stop(self) -> None:
        if self._eng is not None:
            with contextlib.suppress(Exception):
                self._eng.quit()
        self._eng = None
        self._seen_figures.clear()
        self._cleanup_tempdir()

    def _version(self) -> Optional[str]:
        if self._eng is None:
            return None
        with contextlib.suppress(Exception):
            return str(self._eng.eval("matlabRelease.Release", nargout=1))
        return None

    # ------------------------------------------------------------------ #
    # execution
    # ------------------------------------------------------------------ #
    def _execute(self, code: str, **kwargs: Any) -> ExecutionResult:
        """Run a block of MATLAB, capturing text and any figures it draws."""
        result = ExecutionResult(engine=self.name, code=code)
        out, err = io.StringIO(), io.StringIO()
        want_graphs = bool(kwargs.get("capture_graphs", True))

        try:
            self._eng.eval(self._as_block(code), nargout=0, stdout=out, stderr=err)
        except Exception as exc:
            message = (err.getvalue() or str(exc)).strip()
            raise EngineExecutionError(
                message,
                engine=self.name,
                code=code,
                stdout=out.getvalue(),
                raw=exc,
                hint=_execution_hint(message),
            ) from exc

        result.stdout = out.getvalue()
        result.stderr = err.getvalue()
        if want_graphs:
            result.figures.extend(self._collect_figures())
        return result

    @staticmethod
    def _as_block(code: str) -> str:
        """MATLAB's ``eval`` takes one string; a cell is many lines.

        Newlines are legal inside an eval string, so the block is passed whole
        rather than line by line — which keeps ``for``/``end`` and ``if``/``end``
        working, unlike a per-line loop.
        """
        return code.strip()

    # ------------------------------------------------------------------ #
    # graphics
    # ------------------------------------------------------------------ #
    def _tempdir_path(self) -> Path:
        if self._tempdir is None:
            self._tempdir = Path(tempfile.mkdtemp(prefix="econenv-matlab-"))
        return self._tempdir

    def _cleanup_tempdir(self) -> None:
        if self._tempdir is None or _config.get_option("matlab", "keep_temp", False):
            return
        import shutil

        shutil.rmtree(self._tempdir, ignore_errors=True)
        self._tempdir = None

    def _collect_figures(self) -> List[Figure]:
        """Export figures this cell created.

        MATLAB keeps figures open until closed, so without a memory of what has
        already been shown one plot would reappear under every later cell — the
        same trap the EViews adapter has.
        """
        fmt = str(_config.get_option("matlab", "graphics", "png")).lower()
        if fmt == "off":
            return []
        try:
            handles = self._eng.eval(
                "arrayfun(@(h) double(h.Number), findall(0,'Type','figure'))", nargout=1
            )
        except Exception:
            return []
        numbers = _as_number_list(handles)
        figures: List[Figure] = []
        for number in sorted(numbers):
            if number in self._seen_figures:
                continue
            figure = self.capture_figure(number, fmt=fmt)
            if figure is not None:
                figures.append(figure)
                self._seen_figures.add(number)
        return figures

    def capture_figure(self, number: int, fmt: str = "png") -> Optional[Figure]:
        """Export one MATLAB figure and read it back as bytes."""
        target = self._tempdir_path() / f"fig{number}-{uuid.uuid4().hex[:8]}.{fmt}"
        dpi = int(_config.get_option("matlab", "dpi", 150))
        command = (
            f"exportgraphics(figure({int(number)}), '{target.as_posix()}', 'Resolution', {dpi})"
        )
        try:
            self._eng.eval(command, nargout=0)
        except Exception as exc:
            self.log.debug("figure %s export failed: %s", number, exc)
            return None
        if not target.exists():
            return None
        try:
            payload = target.read_bytes()
        finally:
            with contextlib.suppress(OSError):
                target.unlink()
        mimetype = {"svg": "image/svg+xml", "pdf": "application/pdf"}.get(fmt, "image/png")
        return Figure(data=payload, mimetype=mimetype, engine=self.name, name=f"figure {number}")

    # ------------------------------------------------------------------ #
    # data
    # ------------------------------------------------------------------ #
    def _push_frame(self, name: str, df: pd.DataFrame, **kwargs: Any) -> None:
        from ..bridges.matlab_bridge import push_frame

        push_frame(self, name, df, **kwargs)

    def _pull_frame(self, name: Optional[str], **kwargs: Any) -> pd.DataFrame:
        from ..bridges.matlab_bridge import pull_frame

        target = name or getattr(self, "_last_frame", None)
        if target is None:
            raise DataTransferError(
                "MATLAB has no current dataset, so `pull` needs a name: "
                "econenv.pull('matlab', 'mytable').",
                engine=self.name,
                hint="Push one first, or name a table in the MATLAB workspace.",
            )
        return pull_frame(self, target, **kwargs)

    def _push_scalar(self, name: str, value: Any, **kwargs: Any) -> None:
        if isinstance(value, str):
            escaped = value.replace("'", "''")
            self._eng.eval(f"{name} = '{escaped}';", nargout=0)
        else:
            self._eng.workspace[name] = float(value)

    def _pull_scalar(self, expression: str) -> Any:
        try:
            return self._eng.eval(expression, nargout=1)
        except Exception as exc:
            raise EngineExecutionError(
                str(exc), engine=self.name, code=expression, raw=exc
            ) from exc

    def _fit_ols(self, spec, data: pd.DataFrame, meta: Any = None):
        """``fitlm`` — MATLAB's own OLS, so the comparison uses its numbers.

        MATLAB reports AIC and BIC through ``ModelCriterion`` with the same
        normalisation statsmodels uses, and its default is a classical
        covariance with listwise deletion — which is why it lands on the same
        coefficients as R, Stata and EViews rather than merely close ones.
        """
        from ..results import ModelResult

        columns = [spec.depvar, *spec.exog]
        self.push("econenv_ols_data", data.loc[:, columns])

        rhs = " + ".join(spec.exog) if spec.exog else "1"
        formula = f"{spec.depvar} ~ {rhs}" + ("" if spec.constant else " - 1")
        script = (
            f"eeFit = fitlm(econenv_ols_data, '{formula}');\n"
            "eeCoef = eeFit.Coefficients;\n"
            "eeCI = coefCI(eeFit);\n"
            "eeTerms = eeCoef.Properties.RowNames;\n"
            "eeCrit = eeFit.ModelCriterion;\n"
        )
        exec_result = self.execute(script, capture_graphs=False)

        terms = [_canonical_matlab_term(t) for t in _as_str_list(self._eng.eval("eeTerms", 1))]
        get = self._eng.eval

        def column(expr: str) -> np.ndarray:
            return np.array(get(expr, nargout=1), dtype=float).ravel()

        return ModelResult.from_arrays(
            engine=self.name,
            model="OLS",
            terms=terms,
            coef=column("eeCoef.Estimate"),
            std_err=column("eeCoef.SE"),
            stat=column("eeCoef.tStat"),
            pvalue=column("eeCoef.pValue"),
            ci_lower=column("eeCI(:,1)"),
            ci_upper=column("eeCI(:,2)"),
            depvar=spec.depvar,
            nobs=int(float(get("eeFit.NumObservations", nargout=1))),
            df_model=int(float(get("eeFit.NumCoefficients", nargout=1)))
            - (1 if spec.constant else 0),
            df_resid=int(float(get("eeFit.DFE", nargout=1))),
            r2=float(get("eeFit.Rsquared.Ordinary", nargout=1)),
            r2_adj=float(get("eeFit.Rsquared.Adjusted", nargout=1)),
            loglik=float(get("eeFit.LogLikelihood", nargout=1)),
            aic=float(get("eeCrit.AIC", nargout=1)),
            bic=float(get("eeCrit.BIC", nargout=1)),
            rmse=float(get("eeFit.RMSE", nargout=1)),
            fstat=float(get("eeFit.ModelFitVsNullModel.Fstat", nargout=1)),
            vcov_type=spec.vcov or "nonrobust",
            engine_version=self.version(),
            command=f"fitlm(data, '{formula}')",
            raw=exec_result.stdout,
            notes=[
                "MATLAB's fitlm reports AIC/BIC on the same -2ll+2k basis as "
                "statsmodels, so those agree where R's and EViews' differ.",
            ],
        )

    def _pull_matrix(self, name: str) -> np.ndarray:
        try:
            return np.array(self._eng.workspace[name], dtype=float)
        except Exception as exc:
            raise DataTransferError(
                f"{name!r} is not a numeric matrix in the MATLAB workspace.",
                engine=self.name,
                name=name,
                raw=exc,
            ) from exc


def _as_number_list(value: Any) -> List[int]:
    """MATLAB returns a scalar, a matlab.double, or nothing. Normalise all three."""
    if value is None:
        return []
    if isinstance(value, (int, float)):
        return [int(value)]
    try:
        flat = np.array(value, dtype=float).ravel()
    except Exception:
        return []
    return [int(v) for v in flat if np.isfinite(v)]


def _canonical_matlab_term(term: str) -> str:
    """MATLAB names the intercept ``(Intercept)``; EconEnv uses ``_cons``."""
    return "_cons" if term.strip() == "(Intercept)" else term.strip()


def _as_str_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value]


def _execution_hint(message: str) -> str:
    lowered = message.lower()
    if "undefined function" in lowered or "unrecognized function" in lowered:
        return (
            "MATLAB could not find that function. It may be in a toolbox you do not "
            "have, or on a path MATLAB has not been told about: "
            "`addpath('C:/path/to/code')`."
        )
    if "out of memory" in lowered:
        return "MATLAB ran out of memory. Clear large variables with `clear` and retry."
    return ""
