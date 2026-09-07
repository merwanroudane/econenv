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
        self._target: Optional[Dict[str, str]] = None
        self._emitted_graphs: set = set()
        self._last_frame: Optional[str] = None
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

        # The registry says which EViews the ProgID will launch, so the version
        # and location are known before connecting rather than guessed from the
        # newest install on disk.
        wanted = self.options.get("progid") or _config.get_option("eviews", "progid")
        self._target = discovery.eviews_progid_target(wanted or "EViews.Manager")
        home = (self._target or {}).get("home")
        if home:
            self._home = home
            for install in self._installations:
                if str(install.home) == home:
                    self._executable = str(install.executable)
                    break
        self._backend = "comtypes"
        return True

    def _static_version(self) -> Optional[str]:
        target = (self._target or {}).get("version")
        if target:
            return target
        return self._installations[0].version if self._installations else None

    def _info_detail(self) -> Dict[str, Any]:
        return {
            "installations": [str(i) for i in self._installations],
            "progids": list(self._progids),
            "connected_progid": self._connected_progid,
            "progid_target": dict(self._target) if self._target else None,
            "note": (
                "The generic EViews.Manager ProgID binds to whichever install "
                "registered last; the version shown is the one its CLSID "
                "resolves to, confirmed against the connection once started."
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
                self._sync_home_to_connection()
                break

        if self._app is None:
            raise EngineStartError(
                "Could not connect to EViews through COM.",
                engine=self.name,
                raw=last,
                hint=(
                    "Open EViews once so it registers and validates its licence, "
                    "then retry. Pin a version with "
                    "`%econ config eviews.progid EViews.Manager.14`."
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
        self._emitted_graphs.clear()
        self._connected_progid = None
        self._cleanup_tempdir()
        import gc

        gc.collect()

    def _sync_home_to_connection(self) -> None:
        """Point `home` at the EViews that answered, not the newest installed.

        Detection sorts installs newest-first, so on a machine with 12/13/14 the
        location column said "EViews 14" while `EViews.Manager` had actually
        bound to 13.
        """
        connected = self._version()
        if not connected:
            return
        major = str(connected).split(".")[0]
        for install in self._installations:
            if str(install.version).split(".")[0] == major:
                self._home = str(install.home)
                self._executable = str(install.executable)
                return

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
        chunks: List[str] = []
        views: List[List[List[str]]] = []
        want_graphs = bool(kwargs.get("capture_graphs", True))
        for line in lines:
            if want_graphs:
                figure = self._capture_graph_command(line)
                if figure is not None:
                    result.figures.append(figure)
                    executed.append(line)
                    continue
                request = _forecast_request(line)
                if request is not None:
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
                    rebuilt = self._forecast_figure(request)
                    if rebuilt is not None:
                        result.figures.append(rebuilt)
                    else:
                        result.warnings.append(
                            f"{line}: the forecast series was created, but its graph could "
                            f"not be rebuilt. Plot it directly: line {request['target']}"
                        )
                    executed.append(line)
                    continue
            expression = _view_expression(line)
            captured = (
                self._capture_view(expression, graphs=want_graphs)
                if expression is not None
                else None
            )
            if captured is not None:
                if captured[0] == "table":
                    _, grid, truncated = captured
                    views.append(grid)
                    chunks.append(_render_grid(grid))
                    if truncated:
                        result.warnings.append(
                            f"{line}: output truncated; raise eviews.max_view_cells to see it all."
                        )
                elif captured[0] == "text":
                    chunks.append(captured[1])
                else:
                    result.figures.append(captured[1])
                executed.append(line)
                continue
            if expression is not None:
                # It froze — so it *was* a view — but produced nothing readable.
                # Silence is the failure mode that wastes the most time, so say so.
                result.warnings.append(
                    f"{line}: ran, but EconEnv could not read its output. "
                    f"Please report it: https://github.com/merwanroudane/econenv/issues"
                )
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

        result.stdout = "\n\n".join(chunk for chunk in chunks if chunk)
        result.metadata.update(
            {
                "views": views,
                "commands": executed,
                "workfile": self._eval("@wfname"),
                "page": self._eval("@pagename"),
                "progid": self._connected_progid,
            }
        )
        if want_graphs:
            seen = {(figure.name or "").upper() for figure in result.figures}
            result.figures.extend(
                figure
                for figure in self._collect_new_graphs(kwargs.get("graph_names"))
                if (figure.name or "").upper() not in seen
            )
        return result

    def _forecast_figure(self, request: Dict[str, str]) -> Optional[Figure]:
        """Rebuild the forecast plot EViews shows for ``forecast(g)``.

        The window EViews opens is not an object and cannot be exported, so the
        same picture is reconstructed: the forecast, plus and minus two
        standard errors. Every series used is temporary and removed afterwards,
        so the workfile is left exactly as the user's own command left it.
        """
        tag = uuid.uuid4().hex[:8]
        forecast, errors = f"_ee_f{tag}", f"_ee_s{tag}"
        upper, lower, graph = f"_ee_u{tag}", f"_ee_l{tag}", f"_ee_fg{tag}"
        temporaries = [forecast, errors, upper, lower, graph]
        try:
            self._run_command(
                f"{request['object']}.{request['proc']}({request['options']}) {forecast} {errors}"
            )
            self._run_command(f"series {upper} = {forecast} + 2*{errors}")
            self._run_command(f"series {lower} = {forecast} - 2*{errors}")
            self._run_command(f"graph {graph}.line {forecast} {upper} {lower}")
            figure = self.capture_graph(graph)
        except Exception as exc:
            self.log.debug("forecast graph rebuild failed: %s", com_message(exc) or exc)
            figure = None
        finally:
            for name in temporaries:
                with contextlib.suppress(Exception):
                    self._run_command(f"delete {name}")
        if figure is not None:
            figure.name = f"{request['object']}.{request['proc']} (forecast ± 2 s.e.)"
        return figure

    def _capture_graph_command(self, line: str) -> Optional[Figure]:
        """Run a standalone graph command as a named object so it can be shown.

        ``line x`` draws a plot in EViews' own window and leaves nothing in the
        workfile, so there was never anything for the figure sweep to find. It
        is run as ``graph <temp>.line x`` instead, exported, and the temporary
        object deleted.
        """
        suffix = _graph_command(line)
        if suffix is None:
            return None
        name = f"_ee_g{uuid.uuid4().hex[:8]}"
        try:
            self._run_command(f"graph {name}{suffix}")
        except Exception as exc:
            self.log.debug("not a graph command: %s (%s)", line, com_message(exc) or exc)
            return None
        try:
            figure = self.capture_graph(name)
        finally:
            with contextlib.suppress(Exception):
                self._run_command(f"delete {name}")
        if figure is not None:
            figure.name = line.strip()
        return figure

    def _capture_view(self, expression: str, graphs: bool = True) -> Optional[tuple]:
        """Freeze a display view and read it back — as text, or as an image.

        ``Run`` executes a command but returns nothing: EViews writes output to
        its own window, which is why an ``eq1.output`` cell used to come back
        empty. ``freeze`` turns any view into an object, and the object is then
        read over COM.

        A view freezes into one of two things. An estimation or statistics view
        becomes a **table**, whose cells ``Get`` can read. A plotting view such
        as ``x.line`` becomes a **graph**, which has no rows and must be
        exported as an image — and, crucially, leaves no named graph object
        behind, so the end-of-cell sweep over ``@wlookup("*","graph")`` never
        saw it. That is why plots produced the EViews way showed nothing.

        Returns ``("table", grid, truncated)``, ``("figure", figure)``, or
        ``None`` when the line was not a view after all, so the caller falls
        back to running it normally.
        """
        name = f"_ee_v{uuid.uuid4().hex[:8]}"
        try:
            self._run_command(f"freeze({name}) {expression}")
        except Exception as exc:
            self.log.debug("not a view: %s (%s)", expression, com_message(exc) or exc)
            return None
        try:
            kind = self._object_type(name)
            if kind in (None, "table"):
                table = self._read_table(name)
                if table is not None:
                    grid, truncated = table
                    return ("table", grid, truncated)
            if kind in (None, "graph") and graphs:
                figure = self.capture_graph(name)
                if figure is not None:
                    figure.name = expression
                    return ("figure", figure)
            if kind in (None, "text", "spool"):
                text = self._read_text_object(name)
                if text:
                    return ("text", text)
            return None
        finally:
            with contextlib.suppress(Exception):
                self._run_command(f"delete {name}")

    def _object_type(self, name: str) -> Optional[str]:
        """What ``freeze`` produced. Views become one of four object types."""
        for kind in ("table", "graph", "text", "spool"):
            hit = self._eval(f'@wlookup("{name}","{kind}")')
            if hit and str(hit).strip():
                return kind
        return None

    def _read_text_object(self, name: str) -> Optional[str]:
        """Read a frozen text or spool object.

        Estimation representations freeze into a ``text`` object and the
        cointegration tests into a ``spool``; neither has cells to read, so they
        go out to a temporary file and come straight back. Both used to produce
        nothing at all.
        """
        target = self._tempdir_path() / f"{name}-{uuid.uuid4().hex[:8]}.txt"
        try:
            self._run_command(f'{name}.save(t=txt) "{_native(target)}"')
        except Exception as exc:
            self.log.debug("text export failed for %s: %s", name, com_message(exc) or exc)
            return None
        if not target.exists():
            return None
        try:
            return target.read_text("utf-8", "replace").rstrip()
        finally:
            with contextlib.suppress(OSError):
                target.unlink()

    def _read_table(self, name: str) -> Optional[tuple]:
        """Read every cell of an EViews table object. ``None`` if not a table."""
        rows, cols = self._eval(f"@rows({name})"), self._eval(f"@columns({name})")
        if rows is None or cols is None:
            return None
        n_rows, n_cols = int(rows), int(cols)
        if n_rows <= 0 or n_cols <= 0:
            return None
        limit = int(_config.get_option("eviews", "max_view_cells", 20000))
        truncated = n_rows * n_cols > limit
        if truncated:
            n_rows = max(1, limit // n_cols)
        grid = []
        for i in range(1, n_rows + 1):
            row = []
            for j in range(1, n_cols + 1):
                value = self._eval(f"{name}({i},{j})")
                row.append("" if value is None else str(value).strip())
            grid.append(row)
        return grid, truncated

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
        # Remember it so `pull(name)` can round-trip. A push creates a *page* of
        # series, not an object called `name`, so without this the obvious
        # symmetric call fails while the same call works for R, Stata and MATLAB.
        self._last_frame = name

    def _pull_frame(self, name: Optional[str], **kwargs: Any) -> pd.DataFrame:
        from ..bridges.eviews_bridge import pull_frame

        # `pull("eviews", "macro")` after `push("eviews", "macro", df)` should
        # return the data, not fail: the name identified a page, and asking for
        # the page is what the user meant.
        if name and name == getattr(self, "_last_frame", None):
            listing = self._eval(f'@wlookup("{name}","series")')
            if not (listing and str(listing).strip()):
                return pull_frame(self, None, **kwargs)
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
        # Native separators, NOT as_posix(). EViews parses "C:/Users/..." as the
        # drive-relative path "C:Users\..." and writes nowhere, reporting success.
        command = f'{graph_name}.save(t={fmt}, w={width}, h={height}, u=in) "{_native(target)}"'
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
        """Export graphs this cell created — *new* ones, hence the name.

        The sweep looks at every graph in the workfile, so without a memory of
        what has already been shown one plot would reappear below every
        subsequent cell for the rest of the session. An explicit request
        (``--graph``, or a ``show`` line) bypasses the memory and always
        exports.
        """
        explicit_request = explicit is not None
        names = explicit if explicit is not None else self.graph_names()
        figures = []
        for graph in names:
            key = graph.upper()
            if not explicit_request and key in self._emitted_graphs:
                continue
            figure = self.capture_graph(graph)
            if figure is not None:
                figures.append(figure)
                self._emitted_graphs.add(key)
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


# A bare ``object.view`` line is a display view; ``eq1.ls y c x`` carries
# arguments and is an action. Only the former can be frozen into a table.
_VIEW_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z][A-Za-z0-9_]*(\([^()]*\))?$")

#: Views whose arguments follow a space rather than sitting in parentheses.
#:
#: ``_VIEW_RE`` anchors at the end of the options, so ``eq1.wald c(2)=0`` did not
#: look like a view and was run as a bare command — which displays in EViews'
#: own window and returns nothing here. The whole family of hypothesis tests was
#: therefore silent, which is the one outcome this adapter is not allowed to
#: have.
#:
#: An allow-list rather than a looser pattern, because a *proc* also takes
#: space-separated arguments: ``eq1.ls y c x1`` re-estimates the equation, and
#: freezing that would give a display command a side effect.
#:
#: ✓ = frozen to a table against EViews 13 through EconEnv.
_VIEW_WITH_ARGUMENTS = frozenset(
    {
        "wald",  # ✓ eq1.wald c(2)=0
        "testadd",  # ✓ eq1.testadd x3
        "testdrop",  # ✓ eq1.testdrop x2
        "chow",  # ✓ eq1.chow 60
        "facbreak",  # documented; needs a valid break point
        "ubreak",  # documented
        "cointrep",  # documented
        "testfit",
        "testby",
    }
)

#: ``object.view rest of the line``
_VIEW_ARGS_RE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*\.([A-Za-z][A-Za-z0-9_]*)(?:\([^()]*\))?\s+\S.*$"
)
_SHOW_RE = re.compile(r"^show\s+(.+)$", re.IGNORECASE)


def _native(path: Path) -> str:
    """Path in the form EViews accepts: native separators, no trailing slash."""
    return str(path)


def _view_expression(line: str) -> Optional[str]:
    """The view a command displays, or ``None`` if it displays nothing."""
    stripped = line.strip()
    match = _SHOW_RE.match(stripped)
    if match:
        return match.group(1).strip()
    if _VIEW_RE.match(stripped):
        return stripped
    match = _VIEW_ARGS_RE.match(stripped)
    if match and match.group(1).lower() in _VIEW_WITH_ARGUMENTS:
        return stripped
    return None


#: A cell EViews would right-align: a number, possibly signed, in decimal or
#: exponential form, and the (n) that follows a lag or a test statistic.
_NUMERIC_CELL = re.compile(r"^[-+]?(\d[\d,]*\.?\d*([eE][-+]?\d+)?|\.\d+)\)?$")


def _is_numeric_cell(cell: str) -> bool:
    return bool(_NUMERIC_CELL.match(cell.strip()))


def _is_heading(row: List[str]) -> bool:
    """A row of labels standing over columns of numbers."""
    filled = [cell.strip() for cell in row if cell.strip()]
    return bool(filled) and not any(_is_numeric_cell(cell) for cell in filled)


def _blocks(grid: List[List[str]]) -> List[List[int]]:
    """Row indices grouped into the blocks a blank row separates.

    An EViews regression output is not one table. The coefficient block has
    five columns; the summary block underneath has four, and its second column
    holds long labels like "Mean dependent var". Sizing every column across the
    whole grid therefore pads the coefficients to fit a label they have nothing
    to do with, which is what made the table look ragged.
    """
    groups: List[List[int]] = []
    current: List[int] = []
    for index, row in enumerate(grid):
        if any(cell.strip() for cell in row):
            current.append(index)
        elif current:
            groups.append(current)
            current = []
    if current:
        groups.append(current)

    # EViews puts a blank row between the column headings and the coefficients,
    # but they are one table and have to be sized together — otherwise
    # "Coefficient" sits over nothing in particular. Blocks that use the same
    # number of columns are therefore merged across the blank row.
    merged: List[List[int]] = []
    for group in groups:
        heading = (
            merged
            and len(merged[-1]) == 1
            and _column_count(grid, merged[-1]) == _column_count(grid, group) > 1
        )
        if heading:
            merged[-1] = merged[-1] + group
        else:
            merged.append(group)
    return merged


def _column_count(grid: List[List[str]], rows: List[int]) -> int:
    """How many columns the rows in this block actually fill."""
    return max(
        (max((i for i, cell in enumerate(grid[r]) if cell.strip()), default=-1) + 1 for r in rows),
        default=0,
    )


def _render_grid(grid: List[List[str]]) -> str:
    """Lay a frozen EViews table out as EViews itself would print it.

    Two things matter for a regression table to be readable: numbers are
    right-aligned so the decimal points line up, and each block is sized on its
    own columns rather than on the widest cell anywhere in the view.
    """
    if not grid:
        return ""

    lines = [""] * len(grid)
    for block in _blocks(grid):
        rows = [grid[i] for i in block]
        width = max(len(row) for row in rows)
        widths = [0] * width
        numeric = [True] * width
        # A heading row is words by definition, so judging the column on it
        # would left-align the numbers underneath it. Widths still come from
        # every row, so the heading is never clipped.
        data_rows = rows[1:] if len(rows) > 1 and _is_heading(rows[0]) else rows
        for row in rows:
            for index, cell in enumerate(row):
                widths[index] = max(widths[index], len(cell.strip()))
        for row in data_rows:
            for index, cell in enumerate(row):
                if cell.strip() and not _is_numeric_cell(cell):
                    numeric[index] = False

        for offset, row in zip(block, rows):
            last = max((i for i, cell in enumerate(row) if cell.strip()), default=-1)
            if last < 0:
                lines[offset] = ""
                continue
            pieces = []
            for i in range(last + 1):
                cell = row[i].strip() if i < len(row) else ""
                # The first column is the label column even when it happens to
                # hold only numbers, so it is never right-aligned.
                if numeric[i] and i > 0:
                    pieces.append(cell.rjust(widths[i]))
                else:
                    pieces.append(cell.ljust(widths[i]))
            lines[offset] = "  ".join(pieces).rstrip()
    return "\n".join(lines)


# EViews' standalone graph commands. `line x` draws a plot but is neither a
# view (freeze rejects it: "LINE is not a view") nor an object — it leaves
# nothing in the workfile — so it is rewritten to the object form, which can be
# exported. Kept in sync with the EViews command reference.
_GRAPH_COMMANDS = (
    "area",
    "band",
    "bar",
    "boxplot",
    "distplot",
    "dot",
    "errbar",
    "hilo",
    "line",
    "mixed",
    "pie",
    "plot",
    "qqplot",
    "scat",
    "scatmat",
    "seasplot",
    "spike",
    "xyarea",
    "xybar",
    "xyline",
    "xypair",
)
_GRAPH_CMD_RE = re.compile(
    r"^(" + "|".join(_GRAPH_COMMANDS) + r")(\([^()]*\))?\s+(\S.*)$",
    re.IGNORECASE,
)


def _graph_command(line: str) -> Optional[str]:
    """The object-form equivalent of a standalone graph command.

    ``line x`` -> ``.line x``; ``scat(s) x y`` -> ``.scat(s) x y``. The caller
    prefixes ``graph <name>``. Returns ``None`` when the line is not one.
    """
    match = _GRAPH_CMD_RE.match(line.strip())
    if not match:
        return None
    kind, options, arguments = match.groups()
    return f".{kind}{options or ''} {arguments.strip()}"


# `eq.forecast(g) yf` and `eq.fit(g) yf` draw a forecast graph that belongs to
# no object, so it cannot be exported. The graph is rebuilt from the forecast
# and its standard errors, which EViews *will* write to series.
_FORECAST_RE = re.compile(
    r"^(?P<obj>[A-Za-z_][A-Za-z0-9_]*)\.(?P<proc>forecast|fit)"
    r"(?:\((?P<options>[^()]*)\))?\s+(?P<names>\S.*)$",
    re.IGNORECASE,
)


def _forecast_request(line: str) -> Optional[Dict[str, str]]:
    """A ``forecast``/``fit`` call that asked for a graph, or ``None``.

    Only the ``g`` option means "show me the plot"; a forecast without it is
    just series arithmetic and must not gain an unasked-for figure.
    """
    match = _FORECAST_RE.match(line.strip())
    if not match:
        return None
    options = [o.strip().lower() for o in (match.group("options") or "").split(",") if o.strip()]
    if "g" not in options:
        return None
    return {
        "object": match.group("obj"),
        "proc": match.group("proc"),
        # `e` adds the standard-error series; `g` would only redraw the window.
        "options": ",".join([o for o in options if o != "g"] + ["e"]),
        "target": match.group("names").split()[0],
    }


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
