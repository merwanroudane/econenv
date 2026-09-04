"""EViews via COM automation (brief §9).

Written directly against the ``IApplication`` COM interface using ``comtypes``.
``pyeviews`` is **not** a dependency: on a modern Python it fails at import
(``from pkg_resources import get_distribution``) — see the Phase 0 audit §5.6.
Its connection recipe (``EViews.Manager`` → ``GetApplication(0|1|2)``) is
reused; nothing else is.

Behaviours measured on EViews, not read off a doc page:

* ``Get("expr")`` is evaluated as a **series/genr** expression. Scalars and
  strings need an ``=`` prefix: ``Get("=@vernum")``. Without it EViews raises
  "... is not a Genr or series expression function".
* ``Run`` **raises** ``COMError`` on a bad command, and the readable EViews
  message is in ``exc.args[2][0]``. That is the error channel;
  ``@lasterrornum`` is not available as a genr function.
* There is no ``Quit``. Shutdown means releasing the COM reference.
* The version behind the generic ``EViews.Manager`` ProgID is whichever install
  registered last — it is **not** necessarily the newest on disk. The connected
  version is always reported instead of the one found by the file scan.
"""

from __future__ import annotations

import contextlib
import os
import platform
import re
import tempfile
import time
import uuid
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
    com_message,
)
from ..results import ExecutionResult, Figure, ModelResult
from ..schema import DatasetMetadata
from .base import BaseEngine, Capability
from .registry import register

#: ``GetApplication`` instance codes, straight from the EViews COM interface.
_INSTANCE_CODES = {"new": 0, "either": 1, "existing": 2}

# fmt: off
#: Frequency letter reported by ``@pagefreq`` -> pandas offset alias.
FREQ_TO_PANDAS = {
    "A": "YS", "Y": "YS", "S": "6MS", "Q": "QS", "M": "MS",
    "W": "W", "D": "D", "D5": "B", "D7": "D", "H": "h", "U": None,
}
#: ...and back, for pushing a dated frame into a new workfile.
PANDAS_TO_FREQ = {
    "YS": "A", "YE": "A", "A": "A", "Y": "A",
    "QS": "Q", "QE": "Q", "Q": "Q",
    "MS": "M", "ME": "M", "M": "M",
    "W": "W", "D": "D", "B": "D5", "h": "H", "H": "H",
}
# fmt: on


@register
class EViewsEngine(BaseEngine):
    """Adapter over the EViews COM ``IApplication`` object."""

    name = "eviews"
    display_name = "EViews"
    supported_platforms = ("Windows",)
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
        self._app: Any = None
        self._installations: List[discovery.Installation] = []
        self._progids: List[str] = []
        self._connected_progid: Optional[str] = None
        self._tempdir: Optional[Path] = None

    # ------------------------------------------------------------------ #
    # detection
    # ------------------------------------------------------------------ #
    def _detect(self) -> bool:
        if platform.system() != "Windows":
            self._detect_error = "EViews automation needs Windows COM."
            return False
        try:
            import comtypes  # noqa: F401
        except ImportError:
            self._detect_error = "comtypes is not installed."
            return False

        self._installations = discovery.find_eviews()
        self._progids = discovery.eviews_progids()
        if not self._progids:
            self._detect_error = (
                "No EViews COM ProgID is registered. EViews is installed but its "
                "automation server is not registered."
            )
            return False
        if self._installations:
            self._home = str(self._installations[0].home)
            self._executable = str(self._installations[0].executable)
        self._backend = "comtypes"
        return True

    def _static_version(self) -> Optional[str]:
        return self._installations[0].version if self._installations else None

    def _info_detail(self) -> Dict[str, Any]:
        return {
            "installations": [str(i) for i in self._installations],
            "progids": list(self._progids),
            "connected_progid": self._connected_progid,
            "note": (
                "The generic EViews.Manager ProgID binds to whichever install "
                "registered last; `version` is the one actually connected."
            ),
        }

    # ------------------------------------------------------------------ #
    # lifecycle
    # ------------------------------------------------------------------ #
    def _start(self) -> None:
        try:
            from comtypes.client import CreateObject
        except ImportError as exc:  # pragma: no cover
            raise EngineUnavailableError(
                "comtypes is required for EViews automation.",
                engine=self.name,
                raw=exc,
                hint="pip install 'econenv[eviews]'",
            ) from exc

        wanted = self.options.get("progid") or _config.get_option("eviews", "progid")
        order = [wanted] + [p for p in self._progids if p != wanted] if wanted else self._progids
        instance = str(
            self.options.get("instance") or _config.get_option("eviews", "instance", "either")
        ).lower()
        code = _INSTANCE_CODES.get(instance, 1)

        last: Optional[BaseException] = None
        for progid in order:
            try:
                manager = CreateObject(progid)
                app = manager.GetApplication(code)
            except Exception as exc:
                last = exc
                self.log.debug("ProgID %s failed: %s", progid, exc)
                continue
            if app is not None:
                self._app = app
                self._connected_progid = progid
                break

        if self._app is None:
            raise EngineStartError(
                "Could not connect to EViews through COM.",
                engine=self.name,
                raw=last,
                hint=(
                    "Open EViews once so it registers and validates its licence, "
                    "then retry. Pin a version with "
                    "`%econ config eviews.progid EViews14.Manager`."
                ),
            )

        if bool(
            self.options.get("show_window", _config.get_option("eviews", "show_window", False))
        ):
            self._safe(self._app.Show)
        else:
            self._safe(self._app.Hide)

    def set_visible(self, visible: bool = True) -> None:
        """Show or hide the EViews application window.

        Public because the magic needs it; going through the engine keeps the
        COM handle inside the adapter, which is the rule the whole design rests
        on (brief §4, §58).
        """
        self.ensure_started()
        self._safe(self._app.Show if visible else self._app.Hide)

    def _stop(self) -> None:
        """Release the COM reference — the interface exposes no ``Quit``."""
        self._app = None
        self._connected_progid = None
        self._cleanup_tempdir()
        import gc

        gc.collect()

    def _version(self) -> Optional[str]:
        value = self._eval("@vernum")
        if value is None:
            return None
        text = str(value)
        return text[:-2] if text.endswith(".0") else text

    # ------------------------------------------------------------------ #
    # execution
    # ------------------------------------------------------------------ #
    def _execute(self, code: str, **kwargs: Any) -> ExecutionResult:
        """Run EViews commands line by line.

        ``Run`` takes one command at a time; running line by line means a
        failure reports *which* line failed instead of "the cell failed".
        Continuation lines ending in ``_`` are joined first, as EViews does.
        """
        result = ExecutionResult(engine=self.name, code=code)
        lines = _split_commands(code)
        executed: List[str] = []
        for line in lines:
            try:
                self._run_command(line)
            except Exception as exc:
                message = com_message(exc) or str(exc)
                raise EngineExecutionError(
                    f"{message}\n  in: {line}",
                    engine=self.name,
                    code=code,
                    stdout="\n".join(executed),
                    raw=exc,
                    hint=_execution_hint(message, len(executed), len(lines)),
                ) from exc
            executed.append(line)

        result.stdout = ""
        result.metadata.update(
            {
                "commands": executed,
                "workfile": self._eval("@wfname"),
                "page": self._eval("@pagename"),
                "progid": self._connected_progid,
            }
        )
        if kwargs.get("capture_graphs", True):
            result.figures.extend(self._collect_new_graphs(kwargs.get("graph_names")))
        return result

    def _run_command(self, line: str) -> None:
        """``Run`` one command, waiting out a transient "currently busy".

        EViews rejects automation calls with *EViews is currently busy* while it
        is mid-operation or showing a modal dialog. That is a timing condition,
        not a bad command, so it is retried with a short backoff before being
        reported. A genuine syntax error raises on the first attempt and is not
        retried.
        """
        attempts = max(1, int(_config.get_option("eviews", "busy_retries", 5)))
        delay = 0.25
        for attempt in range(attempts):
            try:
                self._app.Run(line)
                return
            except Exception as exc:
                if not _is_busy(exc) or attempt == attempts - 1:
                    raise
                self.log.debug(
                    "EViews busy, retrying in %.2fs (%d/%d)", delay, attempt + 1, attempts
                )
                time.sleep(delay)
                delay = min(delay * 2, 4.0)

    # ------------------------------------------------------------------ #
    # evaluation helpers
    # ------------------------------------------------------------------ #
    def _eval(self, expression: str) -> Any:
        """Evaluate a scalar/string expression.

        The leading ``=`` is what tells EViews this is not a series expression.
        Returns ``None`` rather than raising, because this is used for optional
        metadata lookups all over the adapter.
        """
        if self._app is None:
            return None
        expr = expression if expression.startswith("=") else f"={expression}"
        try:
            return self._app.Get(expr)
        except Exception as exc:
            self.log.debug("eval %s failed: %s", expr, com_message(exc) or exc)
            return None

    def _pull_scalar(self, expression: str) -> Any:
        expr = expression if expression.startswith("=") else f"={expression}"
        try:
            return self._app.Get(expr)
        except Exception as exc:
            raise EngineExecutionError(
                com_message(exc) or str(exc), engine=self.name, code=expression, raw=exc
            ) from exc

    def _push_scalar(self, name: str, value: Any, **kwargs: Any) -> None:
        if isinstance(value, str):
            escaped = value.replace('"', '""')
            self.execute(f'%{name} = "{escaped}"')
        else:
            self.execute(f"!{name} = {float(value)!r}")

    # ------------------------------------------------------------------ #
    # data
    # ------------------------------------------------------------------ #
    def _push_frame(self, name: str, df: pd.DataFrame, **kwargs: Any) -> None:
        from ..bridges.eviews_bridge import push_frame

        push_frame(self, name, df, **kwargs)

    def _pull_frame(self, name: Optional[str], **kwargs: Any) -> pd.DataFrame:
        from ..bridges.eviews_bridge import pull_frame

        return pull_frame(self, name, **kwargs)

    def _pull_matrix(self, name: str) -> np.ndarray:
        rows = self._eval(f"@rows({name})")
        cols = self._eval(f"@columns({name})")
        if rows is None or cols is None:
            raise EngineExecutionError(
                f"{name!r} is not a matrix in the active workfile.", engine=self.name
            )
        n_rows, n_cols = int(rows), int(cols)
        out = np.full((n_rows, n_cols), np.nan)
        for i in range(n_rows):
            for j in range(n_cols):
                value = self._eval(f"{name}({i + 1},{j + 1})")
                if value is not None:
                    out[i, j] = float(value)
        return out

    # ------------------------------------------------------------------ #
    # graphics
    # ------------------------------------------------------------------ #
    def _tempdir_path(self) -> Path:
        if self._tempdir is None:
            self._tempdir = Path(tempfile.mkdtemp(prefix="econenv-eviews-"))
        return self._tempdir

    def _cleanup_tempdir(self) -> None:
        if self._tempdir is None or _config.get_option("eviews", "keep_temp", False):
            return
        import shutil

        shutil.rmtree(self._tempdir, ignore_errors=True)
        self._tempdir = None

    def capture_graph(self, graph_name: str) -> Optional[Figure]:
        """Export one EViews graph object and read it back as bytes.

        EViews can only write a graph to a file, so it goes into a private temp
        directory, is read into memory, and the file is deleted immediately
        (brief §18).
        """
        fmt = str(_config.get_option("eviews", "graphics", "png")).lower()
        if fmt == "off":
            return None
        width = _config.get_option("eviews", "width", 6.0)
        height = _config.get_option("eviews", "height", 4.0)
        target = self._tempdir_path() / f"{graph_name}-{uuid.uuid4().hex[:8]}.{fmt}"
        command = f'{graph_name}.save(t={fmt}, w={width}, h={height}, u=in) "{target.as_posix()}"'
        try:
            self._app.Run(command)
        except Exception as exc:
            self.log.debug("graph export failed for %s: %s", graph_name, com_message(exc) or exc)
            return None
        if not target.exists():
            return None
        try:
            payload = target.read_bytes()
        finally:
            with_suppress = getattr(os, "remove", None)
            if with_suppress is not None:
                with contextlib.suppress(OSError):
                    target.unlink()
        mimetype = "image/svg+xml" if fmt == "svg" else "image/png"
        return Figure(data=payload, mimetype=mimetype, engine=self.name, name=graph_name)

    def graph_names(self) -> List[str]:
        listing = self._eval('@wlookup("*","graph")')
        return str(listing).split() if listing else []

    def _collect_new_graphs(self, explicit: Optional[List[str]] = None) -> List[Figure]:
        names = explicit if explicit is not None else self.graph_names()
        figures = []
        for graph in names:
            figure = self.capture_graph(graph)
            if figure is not None:
                figures.append(figure)
        return figures

    # ------------------------------------------------------------------ #
    # models
    # ------------------------------------------------------------------ #
    def _fit_ols(
        self, spec, data: pd.DataFrame, meta: Optional[DatasetMetadata] = None
    ) -> ModelResult:
        """``equation.ls`` with the coefficients read out of the equation object.

        EViews puts the constant **first** (``ls y c x1 x2``), so the term order
        is normalised to match the other engines before comparison.
        """
        from ..bridges.eviews_bridge import push_frame

        columns = [spec.depvar, *spec.exog]
        push_frame(self, "__econenv_ols", data.loc[:, columns], new_workfile=True)

        eq_name = f"eq_{uuid.uuid4().hex[:6]}"
        regressors = ("c " if spec.constant else "") + " ".join(spec.exog)
        command = f"equation {eq_name}.ls {spec.depvar} {regressors}"
        if spec.vcov and spec.vcov.lower() in {"hc0", "hc1", "hc2", "hc3", "robust"}:
            command += "  @cov(white)"
        self.execute(command, capture_graphs=False)

        n_coef = int(self._eval(f"{eq_name}.@ncoef") or 0)
        raw_terms = self._equation_terms(eq_name, n_coef, spec)

        def series(member: str) -> List[float]:
            out = []
            for i in range(1, n_coef + 1):
                value = self._eval(f"{eq_name}.@{member}({i})")
                out.append(float(value) if value is not None else float("nan"))
            return out

        coef = series("coefs")
        std_err = series("stderrs")
        stat = series("tstats")
        pvalue = series("pvals")

        order = _reorder_constant_last(raw_terms)
        terms = [raw_terms[i] for i in order]
        return ModelResult.from_arrays(
            engine=self.name,
            model="OLS",
            terms=terms,
            coef=[coef[i] for i in order],
            std_err=[std_err[i] for i in order],
            stat=[stat[i] for i in order],
            pvalue=[pvalue[i] for i in order],
            depvar=spec.depvar,
            nobs=_as_int(self._eval(f"{eq_name}.@regobs")),
            df_resid=_as_int(self._eval(f"{eq_name}.@df")),
            r2=_as_float(self._eval(f"{eq_name}.@r2")),
            r2_adj=_as_float(self._eval(f"{eq_name}.@rbar2")),
            loglik=_as_float(self._eval(f"{eq_name}.@logl")),
            aic=_as_float(self._eval(f"{eq_name}.@aic")),
            bic=_as_float(self._eval(f"{eq_name}.@schwarz")),
            rmse=_as_float(self._eval(f"{eq_name}.@se")),
            fstat=_as_float(self._eval(f"{eq_name}.@f")),
            durbin_watson=_as_float(self._eval(f"{eq_name}.@dw")),
            vcov_type=spec.vcov or "ols",
            engine_version=self.version(),
            command=command,
            raw=eq_name,
            notes=[
                "EViews lists the constant first; term order is normalised here.",
                "EViews AIC/BIC are divided by the number of observations, "
                "unlike statsmodels — see docs/comparison.md.",
            ],
        )

    def _equation_terms(self, eq_name: str, n_coef: int, spec) -> List[str]:
        """Coefficient names in EViews' own order."""
        terms = ["_cons"] if spec.constant else []
        terms += list(spec.exog)
        if len(terms) == n_coef:
            return terms
        return [f"C({i})" for i in range(1, n_coef + 1)]

    # ------------------------------------------------------------------ #
    @staticmethod
    def _safe(fn) -> None:
        with contextlib.suppress(Exception):
            fn()


def _is_busy(exc: BaseException) -> bool:
    """True when EViews rejected the call because it is mid-operation."""
    message = (com_message(exc) or str(exc)).lower()
    return "busy" in message


def _execution_hint(message: str, done: int, total: int) -> str:
    """Turn a raw EViews message into advice."""
    lowered = message.lower()
    if "busy" in lowered:
        return (
            "EViews is busy — usually another session holds it, or a modal dialog "
            "is open in the EViews window. EconEnv defaults to its own instance; "
            "check `%econ config eviews.instance` if you changed it, and raise "
            "`eviews.busy_retries` for a slow machine."
        )
    if "not defined" in lowered or "illegal command" in lowered:
        return f"{done} of {total} command(s) ran before this one."
    if "licen" in lowered:
        return "EViews reported a licence problem. Open EViews once to validate the licence."
    return f"{done} of {total} command(s) ran before this one."


def _split_commands(code: str) -> List[str]:
    """Split a cell into EViews commands, honouring ``_`` continuations."""
    lines: List[str] = []
    buffer = ""
    for raw in code.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.strip().startswith("'"):
            continue
        if line.endswith("_"):
            buffer += line[:-1].rstrip() + " "
            continue
        lines.append((buffer + line.strip()).strip())
        buffer = ""
    if buffer.strip():
        lines.append(buffer.strip())
    return lines


def _reorder_constant_last(terms: List[str]) -> List[int]:
    """Indices that move ``_cons`` to the end, matching Stata/statsmodels."""
    order = [i for i, t in enumerate(terms) if t != "_cons"]
    order += [i for i, t in enumerate(terms) if t == "_cons"]
    return order


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


def parse_frequency(page_freq: Optional[str]) -> Optional[str]:
    """``@pagefreq`` letter -> pandas offset alias."""
    if not page_freq:
        return None
    key = str(page_freq).strip().upper()
    if key in FREQ_TO_PANDAS:
        return FREQ_TO_PANDAS[key]
    match = re.match(r"^([A-Z])", key)
    return FREQ_TO_PANDAS.get(match.group(1)) if match else None
