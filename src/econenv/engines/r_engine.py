"""R with two interchangeable backends (brief §7).

The brief assumed ``rpy2``. The Phase 0 audit found that rpy2 publishes **no
Windows wheels** for any 3.6.x release, so on the author's own platform it is not
installable without a source build. Making the flagship R integration depend on
that would be a design flaw, so the R engine has two backends:

``subprocess`` (default, always available)
    One long-lived ``Rterm``/``R`` child process fed over stdin. Persistent
    session, no compiler, identical behaviour on Windows, Linux and macOS. Each
    execution sinks R's output and message streams to a private file and prints
    a one-time token, so output is captured exactly and never interleaves.

``rpy2`` (used automatically when importable)
    In-process, faster, and — importantly — EconEnv then **loads rpy2's own
    ``%R``/``%%R`` magics rather than shadowing them**, per brief §3 and §7.

Both backends satisfy the same :class:`~econenv.engines.base.BaseEngine`
contract, so nothing above this module knows which one is live.
"""

from __future__ import annotations

import contextlib
import os
import platform
import queue
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from .. import config as _config
from .. import discovery
from ..exceptions import (
    DataTransferError,
    EngineExecutionError,
    EngineStartError,
    EngineTimeoutError,
    SessionError,
)
from ..results import ExecutionResult, Figure, ModelResult
from ..schema import DatasetMetadata
from .base import BaseEngine, Capability
from .registry import register

#: Bootstrap sourced once per session. It defines the execution protocol:
#: sink stdout+messages to a file, run the cell, write a status file, then print
#: the token so the Python side knows the cell is finished.
_BOOTSTRAP = r"""
.econenv <- new.env()
.econenv$version <- "0.1.0"

.econenv_status <- function(path, key, value) {
  cat(key, "\t", gsub("[\r\n]+", " ", paste(value, collapse=" | ")), "\n",
      sep = "", file = path, append = TRUE)
}

.econenv_run <- function(codefile, outfile, statusfile, token,
                         plotdir = NA, plotfmt = "svg",
                         width = 7, height = 4.5, dpi = 110) {
  file.create(statusfile)
  warnings_seen <- character(0)
  messages_seen <- character(0)
  plots_before <- character(0)
  if (!is.na(plotdir)) {
    dir.create(plotdir, showWarnings = FALSE, recursive = TRUE)
    plots_before <- list.files(plotdir)
    dev_ok <- TRUE
    tryCatch({
      if (identical(plotfmt, "svg")) {
        if (requireNamespace("svglite", quietly = TRUE)) {
          svglite::svglite(file.path(plotdir, "econenv-%03d.svg"),
                           width = width, height = height)
        } else {
          grDevices::svg(file.path(plotdir, "econenv-%03d.svg"),
                         width = width, height = height, onefile = FALSE)
        }
      } else {
        grDevices::png(file.path(plotdir, "econenv-%03d.png"),
                       width = width * dpi, height = height * dpi, res = dpi)
      }
    }, error = function(e) { dev_ok <<- FALSE })
    if (!dev_ok) plotdir <- NA
  }

  con <- file(outfile, open = "wt", encoding = "UTF-8")
  sink(con)
  sink(con, type = "message")
  status <- "ok"
  errmsg <- ""
  result <- tryCatch(
    withCallingHandlers(
      source(codefile, echo = FALSE, print.eval = TRUE, local = globalenv(),
             encoding = "UTF-8", max.deparse.length = Inf),
      warning = function(w) {
        warnings_seen <<- c(warnings_seen, conditionMessage(w))
        invokeRestart("muffleWarning")
      },
      message = function(m) {
        messages_seen <<- c(messages_seen, sub("\n$", "", conditionMessage(m)))
        invokeRestart("muffleMessage")
      }
    ),
    error = function(e) {
      status <<- "error"
      errmsg <<- conditionMessage(e)
      NULL
    }
  )
  sink(type = "message")
  sink()
  close(con)

  plots <- character(0)
  if (!is.na(plotdir)) {
    try(grDevices::dev.off(), silent = TRUE)
    after <- list.files(plotdir)
    plots <- setdiff(after, plots_before)
  }

  .econenv_status(statusfile, "status=", status)
  if (nzchar(errmsg))               .econenv_status(statusfile, "error=", errmsg)
  for (w in warnings_seen)          .econenv_status(statusfile, "warning=", w)
  for (m in messages_seen)          .econenv_status(statusfile, "message=", m)
  for (p in plots)                  .econenv_status(statusfile, "plot=", p)
  .econenv_status(statusfile, "value_class=", paste(class(result$value), collapse = ","))

  cat(token, "\n", sep = "")
  flush(stdout())
  invisible(NULL)
}

.econenv_typeof <- function(x) {
  if (is.factor(x)) "categorical"
  else if (inherits(x, "Date")) "date"
  else if (inherits(x, "POSIXct")) "datetime"
  else if (is.logical(x)) "boolean"
  else if (is.integer(x)) "integer"
  else if (is.numeric(x)) "float"
  else if (is.character(x)) "string"
  else "unsupported"
}

options(warn = 1, stringsAsFactors = FALSE, width = 100)
"""


@register
class REngine(BaseEngine):
    """R, driven either through a persistent child process or through rpy2."""

    name = "r"
    display_name = "R"
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
        self._installations: List[discovery.Installation] = []
        self._process: Optional[subprocess.Popen] = None
        self._reader: Optional[threading.Thread] = None
        self._queue: queue.Queue[str] = queue.Queue()
        self._tempdir: Optional[Path] = None
        self._rpy2: Any = None
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ #
    # detection
    # ------------------------------------------------------------------ #
    def _detect(self) -> bool:
        configured = self.options.get("home") or _config.get_option("r", "home")
        self._installations = discovery.find_r(configured)
        if not self._installations:
            self._detect_error = (
                "No R installation found. Set R_HOME, put R on PATH, or run "
                '`%econ config r.home "C:/Program Files/R/R-4.5.2"`.'
            )
            return False
        install = self._installations[0]
        self._home = str(install.home)
        self._executable = str(self._console_executable(install.home) or install.executable)
        self._backend = self._choose_backend()
        self._last_frame: Optional[str] = None
        return True

    @staticmethod
    def _console_executable(home: Path) -> Optional[Path]:
        """The front-end that accepts piped stdin.

        On Windows that is ``Rterm.exe`` — plain ``R.exe`` is a launcher that
        can spawn its own console instead of talking to our pipe.
        """
        home = Path(home)
        if platform.system() == "Windows":
            for candidate in (home / "bin" / "x64" / "Rterm.exe", home / "bin" / "Rterm.exe"):
                if candidate.is_file():
                    return candidate
            return None
        candidate = home / "bin" / "R"
        return candidate if candidate.is_file() else None

    def _choose_backend(self) -> str:
        requested = str(
            self.options.get("backend") or _config.get_option("r", "backend", "auto")
        ).lower()
        if requested == "subprocess":
            return "subprocess"
        if requested == "rpy2":
            return "rpy2"
        return "rpy2" if _rpy2_importable() else "subprocess"

    def _static_version(self) -> Optional[str]:
        return self._installations[0].version if self._installations else None

    def _info_detail(self) -> Dict[str, Any]:
        return {
            "installations": [str(i) for i in self._installations],
            "backend": self._backend,
            "rpy2_available": _rpy2_importable(),
            "console_executable": self._executable,
            "magics": (
                "rpy2 %R / %%R (official)" if self._backend == "rpy2" else "EconEnv %Rec / %%Rec"
            ),
        }

    # ------------------------------------------------------------------ #
    # lifecycle
    # ------------------------------------------------------------------ #
    def _start(self) -> None:
        if self._backend == "rpy2":
            self._start_rpy2()
        else:
            self._start_subprocess()

    def _stop(self) -> None:
        if self._backend == "rpy2":
            self._rpy2 = None
        else:
            self._stop_subprocess()
        self._cleanup_tempdir()

    # -- rpy2 backend ------------------------------------------------------ #
    def _start_rpy2(self) -> None:
        try:
            import rpy2.robjects as robjects
        except ImportError as exc:
            self._backend = "subprocess"
            self.log.info("rpy2 unavailable, falling back to the subprocess backend")
            self._start_subprocess()
            _ = exc
            return
        if self._home and not os.environ.get("R_HOME"):
            os.environ["R_HOME"] = self._home
        self._rpy2 = robjects

    # -- subprocess backend ------------------------------------------------ #
    def _start_subprocess(self) -> None:
        executable = self._executable
        if not executable or not Path(executable).is_file():
            raise EngineStartError(
                "No R console executable (Rterm/R) was found.",
                engine=self.name,
                hint='Set it with `%econ config r.home "<R install directory>"`.',
            )
        env = dict(os.environ)
        if self._home:
            env["R_HOME"] = self._home
        env.setdefault("R_LIBS_USER", env.get("R_LIBS_USER", ""))
        env["LANGUAGE"] = "en"  # keep R's messages parseable

        creationflags = 0
        if platform.system() == "Windows":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        try:
            self._process = subprocess.Popen(
                [executable, "--vanilla", "--no-echo", "--no-save", "--no-restore"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=env,
                cwd=str(self._tempdir_path()),
                creationflags=creationflags,
            )
        except OSError as exc:
            raise EngineStartError(
                f"Could not launch {executable}: {exc}", engine=self.name, raw=exc
            ) from exc

        self._queue = queue.Queue()
        self._reader = threading.Thread(target=self._pump, daemon=True, name="econenv-r-reader")
        self._reader.start()

        from ..bridges.r_bridge import SCHEMA_HELPERS

        ready = '\ncat("ECONENV_R_READY\\n"); flush(stdout())\n'
        self._write(_BOOTSTRAP + SCHEMA_HELPERS + ready)
        if not self._await_token("ECONENV_R_READY", timeout=90):
            stderr = self._drain_stderr()
            self._stop_subprocess()
            raise EngineStartError(
                "R started but never reported ready.",
                engine=self.name,
                hint=stderr or "Try running R yourself to check the installation.",
            )

    def _stop_subprocess(self) -> None:
        process, self._process = self._process, None
        if process is None:
            return
        try:
            if process.stdin and not process.stdin.closed:
                process.stdin.write("q(save='no')\n")
                process.stdin.flush()
                process.stdin.close()
        except OSError:
            pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    def _pump(self) -> None:
        process = self._process
        if process is None or process.stdout is None:
            return
        for line in process.stdout:
            self._queue.put(line.rstrip("\n"))
        self._queue.put(None)  # type: ignore[arg-type]

    def _write(self, text: str) -> None:
        process = self._process
        if process is None or process.stdin is None:
            raise SessionError("The R session is not running.", engine=self.name)
        try:
            process.stdin.write(text if text.endswith("\n") else text + "\n")
            process.stdin.flush()
        except OSError as exc:
            raise SessionError(
                "The R session closed unexpectedly.",
                engine=self.name,
                raw=exc,
                hint="`%econ restart r` starts a fresh one.",
            ) from exc

    def _await_token(self, token: str, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                line = self._queue.get(timeout=0.2)
            except queue.Empty:
                if self._process is not None and self._process.poll() is not None:
                    return False
                continue
            if line is None:
                return False
            if line.strip() == token:
                return True
        return False

    def _drain_stderr(self) -> str:
        process = self._process
        if process is None or process.stderr is None:
            return ""
        try:
            import select

            _ = select
        except ImportError:  # pragma: no cover
            pass
        # Non-blocking best effort: only used on the failure path.
        with contextlib.suppress(OSError, ValueError):
            process.stderr.flush()
        return ""

    # ------------------------------------------------------------------ #
    # execution
    # ------------------------------------------------------------------ #
    def _execute(self, code: str, **kwargs: Any) -> ExecutionResult:
        if self._backend == "rpy2":
            return self._execute_rpy2(code, **kwargs)
        return self._execute_subprocess(code, **kwargs)

    def _execute_rpy2(self, code: str, **kwargs: Any) -> ExecutionResult:
        import rpy2.rinterface_lib.callbacks as callbacks
        import rpy2.robjects as robjects

        captured: List[str] = []
        errors: List[str] = []
        old_out, old_err = callbacks.consolewrite_print, callbacks.consolewrite_warnerror
        callbacks.consolewrite_print = captured.append
        callbacks.consolewrite_warnerror = errors.append
        result = ExecutionResult(engine=self.name, code=code)
        try:
            value = robjects.r(code)
            result.value = value
        except Exception as exc:
            raise EngineExecutionError(
                str(exc),
                engine=self.name,
                code=code,
                stdout="".join(captured),
                stderr="".join(errors),
                raw=exc,
            ) from exc
        finally:
            callbacks.consolewrite_print = old_out
            callbacks.consolewrite_warnerror = old_err
        result.stdout = "".join(captured)
        result.stderr = "".join(errors)
        return result

    def _execute_subprocess(self, code: str, **kwargs: Any) -> ExecutionResult:
        with self._lock:
            token = f"ECONENV_DONE_{uuid.uuid4().hex}"
            work = self._tempdir_path()
            code_file = work / f"cell_{token[-8:]}.R"
            out_file = work / f"out_{token[-8:]}.txt"
            status_file = work / f"status_{token[-8:]}.txt"
            plot_dir = work / f"plots_{token[-8:]}"

            code_file.write_text(code if code.endswith("\n") else code + "\n", encoding="utf-8")

            graphics = str(
                kwargs.get("graphics") or _config.get_option("r", "graphics", "svg")
            ).lower()
            plot_arg = "NA" if graphics == "off" else f'"{plot_dir.as_posix()}"'
            call = (
                f'.econenv_run("{code_file.as_posix()}", "{out_file.as_posix()}", '
                f'"{status_file.as_posix()}", "{token}", {plot_arg}, "{graphics}", '
                f"{float(_config.get_option('r', 'width', 7.0))}, "
                f"{float(_config.get_option('r', 'height', 4.5))}, "
                f"{int(_config.get_option('r', 'dpi', 110))})"
            )
            self._write(call)

            timeout = float(kwargs.get("timeout") or _config.get_option("core", "timeout", 300.0))
            if not self._await_token(token, timeout=timeout):
                if self._process is not None and self._process.poll() is not None:
                    raise SessionError(
                        "The R session died while running this cell.",
                        engine=self.name,
                        hint="`%econ restart r` starts a fresh one.",
                    )
                raise EngineTimeoutError(
                    f"R did not finish within {timeout:g}s.",
                    engine=self.name,
                    hint="Raise it with `%econ config core.timeout 900`.",
                )

            output = (
                out_file.read_text(encoding="utf-8", errors="replace") if out_file.exists() else ""
            )
            status = _parse_status(status_file)
            result = ExecutionResult(engine=self.name, code=code, stdout=output)
            result.warnings = status.get("warning", [])
            messages = status.get("message", [])
            if messages:
                result.stderr = "\n".join(messages)
            classes = status.get("value_class") or []
            result.metadata["value_class"] = classes[0] if classes else None

            if (status.get("status") or ["ok"])[0] == "error":
                message = (status.get("error") or ["R reported an error."])[0]
                raise EngineExecutionError(
                    message,
                    engine=self.name,
                    code=code,
                    stdout=output,
                    stderr=result.stderr,
                )

            for plot_name in status.get("plot", []):
                figure = _read_plot(plot_dir / plot_name, self.name)
                if figure is not None:
                    result.figures.append(figure)

            for path in (code_file, out_file, status_file):
                _unlink(path)
            if plot_dir.exists():
                shutil.rmtree(plot_dir, ignore_errors=True)
            return result

    def _version(self) -> Optional[str]:
        if self._backend == "rpy2" and self._rpy2 is not None:
            try:
                return str(self._rpy2.r('paste(R.version$major, R.version$minor, sep=".")')[0])
            except Exception:
                return None
        try:
            result = self._execute_subprocess(
                'cat(paste(R.version$major, R.version$minor, sep="."))', graphics="off"
            )
        except Exception:
            return None
        return result.stdout.strip() or None

    # ------------------------------------------------------------------ #
    # data
    # ------------------------------------------------------------------ #
    def _push_frame(self, name: str, df: pd.DataFrame, **kwargs: Any) -> None:
        from ..bridges.r_bridge import push_frame

        push_frame(self, name, df, **kwargs)
        self._last_frame = name

    def _pull_frame(self, name: Optional[str], **kwargs: Any) -> pd.DataFrame:
        """Read a data frame out of R.

        Unlike Stata and EViews, R has no "current dataset": every frame is
        just a variable. The old default was ``.Last.value``, the last
        top-level expression — which after a plot or a model fit is not a data
        frame at all, and quietly produced an empty result. So the default is
        the frame EconEnv last transferred, and when there is none the user is
        told what R actually holds rather than handed an empty frame.
        """
        from ..bridges.r_bridge import pull_frame

        target = name or self._last_frame
        if target is None:
            raise DataTransferError(
                "R has no current data frame, so `pull` needs a name: econenv.pull('r', 'mydata').",
                engine=self.name,
                hint=self._frames_hint(),
            )
        frame = pull_frame(self, target, **kwargs)
        if name:
            self._last_frame = name
        return frame

    def _frames_hint(self) -> str:
        """Name the data frames R currently holds, so the error is actionable."""
        try:
            listing = self.execute(
                "cat(paste(Filter(function(n) is.data.frame(get(n)), ls()), collapse=' '))",
                graphics="off",
            ).stdout.strip()
        except Exception:  # pragma: no cover - diagnostics must never raise
            return "Push one first with `%%R -i df`, or name an existing frame."
        if not listing:
            return "R currently holds no data frames. Send one with `%%R -i df`."
        return f"Data frames in R: {listing}"

    def _push_scalar(self, name: str, value: Any, **kwargs: Any) -> None:
        self.execute(f"{name} <- {_r_literal(value)}", graphics="off")

    def _pull_scalar(self, expression: str) -> Any:
        result = self.execute(f"cat(format({expression}, digits=17))", graphics="off")
        text = result.stdout.strip()
        try:
            return float(text)
        except ValueError:
            return text

    def _pull_matrix(self, name: str) -> np.ndarray:
        frame = self._pull_frame(f"as.data.frame({name})")
        return frame.to_numpy(dtype=float)

    # ------------------------------------------------------------------ #
    # models
    # ------------------------------------------------------------------ #
    def _fit_ols(
        self, spec, data: pd.DataFrame, meta: Optional[DatasetMetadata] = None
    ) -> ModelResult:
        """``lm()`` with the coefficient table read back as a data frame.

        R's ``lm`` uses ``na.action = na.omit`` (listwise deletion) and a
        classical covariance — the same defaults as statsmodels and Stata, which
        is why the three normally agree to machine precision.
        """
        from ..bridges.r_bridge import pull_frame, push_frame

        columns = [spec.depvar, *spec.exog]
        push_frame(self, "econenv_ols_data", data.loc[:, columns])

        rhs = " + ".join(spec.exog) if spec.exog else "1"
        formula = f"{spec.depvar} ~ {rhs}" + ("" if spec.constant else " - 1")
        script = f"""
econenv_ols_fit <- lm({formula}, data = econenv_ols_data)
econenv_ols_sum <- summary(econenv_ols_fit)
econenv_ols_tab <- as.data.frame(econenv_ols_sum$coefficients)
names(econenv_ols_tab) <- c("coef", "std_err", "stat", "pvalue")
econenv_ols_ci <- as.data.frame(confint(econenv_ols_fit))
names(econenv_ols_ci) <- c("ci_lower", "ci_upper")
econenv_ols_tab <- cbind(term = rownames(econenv_ols_tab), econenv_ols_tab, econenv_ols_ci)
econenv_ols_stats <- data.frame(
  nobs = length(econenv_ols_fit$residuals),
  df_model = econenv_ols_sum$fstatistic[["numdf"]],
  df_resid = econenv_ols_fit$df.residual,
  r2 = econenv_ols_sum$r.squared,
  r2_adj = econenv_ols_sum$adj.r.squared,
  loglik = as.numeric(logLik(econenv_ols_fit)),
  aic = AIC(econenv_ols_fit),
  bic = BIC(econenv_ols_fit),
  rmse = econenv_ols_sum$sigma,
  fstat = econenv_ols_sum$fstatistic[["value"]]
)
"""
        exec_result = self.execute(script, graphics="off")
        table = pull_frame(self, "econenv_ols_tab")
        stats = pull_frame(self, "econenv_ols_stats").iloc[0]

        terms = [_canonical_r_term(t) for t in table["term"]]
        return ModelResult.from_arrays(
            engine=self.name,
            model="OLS",
            terms=terms,
            coef=table["coef"].to_numpy(),
            std_err=table["std_err"].to_numpy(),
            stat=table["stat"].to_numpy(),
            pvalue=table["pvalue"].to_numpy(),
            ci_lower=table["ci_lower"].to_numpy(),
            ci_upper=table["ci_upper"].to_numpy(),
            depvar=spec.depvar,
            nobs=int(stats["nobs"]),
            df_model=int(stats["df_model"]),
            df_resid=int(stats["df_resid"]),
            r2=float(stats["r2"]),
            r2_adj=float(stats["r2_adj"]),
            loglik=float(stats["loglik"]),
            aic=float(stats["aic"]),
            bic=float(stats["bic"]),
            rmse=float(stats["rmse"]),
            fstat=float(stats["fstat"]),
            vcov_type=spec.vcov or "nonrobust",
            engine_version=self.version(),
            command=f"lm({formula})",
            raw=exec_result.stdout,
            notes=[
                "R's AIC/BIC count the error variance as a parameter (k+1), so "
                "they sit one parameter above statsmodels' — see docs/comparison.md.",
            ],
        )

    # ------------------------------------------------------------------ #
    def _tempdir_path(self) -> Path:
        if self._tempdir is None:
            self._tempdir = Path(tempfile.mkdtemp(prefix="econenv-r-"))
        return self._tempdir

    def _cleanup_tempdir(self) -> None:
        if self._tempdir is not None:
            shutil.rmtree(self._tempdir, ignore_errors=True)
            self._tempdir = None

    def r_packages(self) -> List[Dict[str, str]]:
        """Installed R packages and versions, for the reproducibility snapshot."""
        try:
            result = self.execute(
                'ip <- installed.packages()[, c("Package","Version")]; '
                'cat(paste(ip[,1], ip[,2], sep="\\t", collapse="\\n"))',
                graphics="off",
            )
        except Exception as exc:
            self.log.debug("package listing failed: %s", exc)
            return []
        out = []
        for line in result.stdout.strip().splitlines():
            if "\t" in line:
                pkg, version = line.split("\t", 1)
                out.append({"name": pkg.strip(), "version": version.strip()})
        return out

    def has_r_package(self, package: str) -> bool:
        try:
            result = self.execute(
                f'cat(requireNamespace("{package}", quietly=TRUE))', graphics="off"
            )
        except Exception:
            return False
        return result.stdout.strip().upper() == "TRUE"


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
_RPY2_IMPORTABLE: Optional[bool] = None
_RPY2_ERROR: Optional[str] = None


def _rpy2_importable() -> bool:
    """Whether rpy2 can actually be imported — not merely whether it is present.

    A spec-only check disagreed with the magic loader, which does a real import:
    an rpy2 that is installed but cannot find R (common in conda environments)
    has a spec but raises on import. `%econ status` then reported backend
    "rpy2" in the same session whose banner said "rpy2 not installed".

    The import is attempted once and cached; rpy2 loads R itself, so repeating
    it on every status call would be expensive.
    """
    global _RPY2_IMPORTABLE, _RPY2_ERROR
    if _RPY2_IMPORTABLE is None:
        import importlib.util

        try:
            if importlib.util.find_spec("rpy2") is None:
                _RPY2_IMPORTABLE, _RPY2_ERROR = False, None
            else:
                import rpy2.robjects  # noqa: F401

                _RPY2_IMPORTABLE, _RPY2_ERROR = True, None
        except Exception as exc:
            _RPY2_IMPORTABLE = False
            _RPY2_ERROR = f"{type(exc).__name__}: {exc}"
    return _RPY2_IMPORTABLE


def rpy2_state() -> tuple:
    """``(installed, importable, error)`` — the three states, not two.

    "Installed" and "usable" are different things, and conflating them made
    ``doctor`` report PASS for an rpy2 that raises on import. A version built
    for an older Python is present, has a spec, and cannot be used.
    """
    import importlib.util

    installed = importlib.util.find_spec("rpy2") is not None
    importable = _rpy2_importable()
    return installed, importable, _RPY2_ERROR


def _parse_status(path: Path) -> Dict[str, List[str]]:
    """Read the ``key=<TAB>value`` status file written by ``.econenv_run``."""
    out: Dict[str, List[str]] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "\t" not in line:
            continue
        key, value = line.split("\t", 1)
        out.setdefault(key.rstrip("="), []).append(value)
    return out


#: Below this a device file holds only the SVG/PNG header, not a drawing.
_MIN_PLOT_BYTES = 512


def _read_plot(path: Path, engine: str) -> Optional[Figure]:
    """Read a plot file, skipping the empty one R's device always creates.

    Opening a graphics device writes the file immediately, so a cell that draws
    nothing still leaves a stub behind. Rendering it would put a blank frame in
    the notebook after every non-plotting R cell.
    """
    if not path.exists():
        return None
    payload = path.read_bytes()
    if len(payload) < _MIN_PLOT_BYTES:
        return None
    mimetype = "image/svg+xml" if path.suffix.lower() == ".svg" else "image/png"
    return Figure(data=payload, mimetype=mimetype, engine=engine, name=path.name)


def _unlink(path: Path) -> None:
    with contextlib.suppress(OSError):
        path.unlink()


def _r_literal(value: Any) -> str:
    """Render a Python scalar as R source."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, np.integer)):
        return f"{int(value)}L"
    if isinstance(value, (float, np.floating)):
        return "NA_real_" if np.isnan(value) else repr(float(value))
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, (list, tuple)):
        return "c(" + ", ".join(_r_literal(v) for v in value) + ")"
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _canonical_r_term(term: str) -> str:
    return "_cons" if str(term) == "(Intercept)" else str(term)
