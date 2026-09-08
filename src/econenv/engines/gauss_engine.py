"""GAUSS as an EconEnv engine.

GAUSS is driven through its terminal executable. A native binding to the GAUSS
Engine C API would give a persistent workspace and faster transfers, and the
architecture here leaves room for it — :class:`GaussEngine` selects a *backend*
rather than talking to a process directly — but the CLI is what exists today and
it is honest about what it cannot do.

**Which installation runs.** More than one GAUSS can be installed and they do
not all work; on the machine this was developed against, ``gauss24`` and
``gauss25`` are present and only ``gauss26`` runs. So detection reports the
installation EconEnv will *actually* use and lists the rest, rather than naming
the newest directory on disk and hoping. That is the same mistake the EViews
adapter used to make with ProgIDs, and the MATLAB adapter with engine releases.

**Detection does not start GAUSS.** Finding the executable and reading its
banner costs milliseconds; starting a session does not. ``%econ status`` stays
fast, and ``%econ doctor gauss --deep`` is where a real round trip happens.
"""

from __future__ import annotations

import glob
import os
import platform
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from .. import config as _config
from ..exceptions import DataTransferError, EngineExecutionError
from ..results import ExecutionResult
from ._gauss_cli import GaussCliBackend, describe, find_executable, probe_version
from .base import BaseEngine, Capability
from .registry import register

#: GAUSS's plotting calls. A cell that contains none of these drew nothing, and
#: asking GAUSS to save a plot anyway would write out whatever was last drawn —
#: so the same figure would reappear under every later cell, which is the trap
#: the EViews and MATLAB adapters both had to be taught to avoid.
_PLOT_CALL = re.compile(
    r"\bplot(?:XY|Scatter|Hist|HistP|HistF|Bar|Area|Box|Surface|Contour|TS|"
    r"LogLog|SemiLogX|SemiLogY|Polar|Line|OpenWindow|Add\w*)\s*\(",
    re.IGNORECASE,
)

#: Formats GAUSS's plotSave writes, and the mime type each becomes.
_GRAPHICS_MIME = {
    "svg": "image/svg+xml",
    "png": "image/png",
    "pdf": "application/pdf",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
}

#: Formats GAUSS's plotSave refuses. Naming them turns its bare "Program
#: execute failed" into something a user can act on.
_UNSUPPORTED_PLOT = {"eps", "ps", "tif", "tiff", "gif", "bmp"}

#: ``plotSave("file.svg", 800 | 600, "px")`` — the filename the cell saves to.
#: Matched across newlines because the call is usually written over several
#: lines, which is exactly how it appeared in the report that prompted this.
_PLOT_SAVE = re.compile(
    r"""\bplotSave\s*\(\s*["']([^"']+)["']""",
    re.IGNORECASE | re.VERBOSE,
)

#: ``plotSave`` takes a size AND a unit, and the unit is not optional in
#: practice. Measured against GAUSS 26.1.1:
#:
#:     plotSave(f, 12 | 9)           ->  4.2mm x 3.2mm   (raw units)
#:     plotSave(f, 12 | 9, "in")     ->  508mm x 381mm
#:     plotSave(f, 800 | 600, "px")  ->  282mm x 212mm
#:
#: Omitting it wrote a file full of valid path data onto a four-millimetre
#: canvas — big enough to look right by file size, and microscopic on screen.
#: So the unit is always stated: inches for vector, pixels for raster.
_VECTOR_INCHES = (12, 9)
_RASTER_PIXELS = (1200, 900)

#: ``gauss26``, ``GAUSS 24``, ``gauss24.0`` — the version in a directory name.
_VERSION_IN_NAME = re.compile(r"(\d+)(?:[._](\d+))?\s*$")


def _version_key(path: Path) -> tuple:
    """Sort key that puts the newest installation first."""
    match = _VERSION_IN_NAME.search(path.name.replace("GAUSS", "").replace("gauss", ""))
    if not match:
        return (0, 0)
    return (int(match.group(1)), int(match.group(2) or 0))


def find_gauss() -> List[Path]:
    """GAUSS installation roots, newest first.

    GAUSS does not install into Program Files by default on Windows — the
    installation this was developed against is ``C:\\gauss26`` — so looking only
    where other vendors put things would find nothing.
    """
    roots: List[Path] = []

    configured = _config.get_option("gauss", "home", None)
    if configured:
        roots.append(Path(configured))
    for variable in ("GAUSSHOME", "MTENGHOME", "GAUSS_HOME"):
        if value := os.environ.get(variable):
            roots.append(Path(value))

    if platform.system() == "Windows":
        patterns = [
            r"C:\gauss*",
            r"C:\GAUSS*",
            os.path.join(os.environ.get("PROGRAMFILES", r"C:\Program Files"), "GAUSS*"),
            os.path.join(os.environ.get("PROGRAMFILES", r"C:\Program Files"), "Aptech", "*"),
        ]
    elif platform.system() == "Darwin":
        patterns = ["/Applications/GAUSS*", "/Applications/Aptech/*"]
    else:
        patterns = ["/usr/local/gauss*", "/opt/gauss*", "/usr/local/GAUSS*"]

    for pattern in patterns:
        roots.extend(Path(match) for match in glob.glob(pattern))

    seen: set = set()
    found: List[Path] = []
    for root in roots:
        key = str(root).lower()
        if key in seen or not root.is_dir():
            continue
        seen.add(key)
        if find_executable(root) is not None:
            found.append(root)

    found.sort(key=_version_key, reverse=True)
    return found


#: The GAUSS Engine's shared library, by platform. This is *not* part of a
#: desktop GAUSS installation: Aptech licenses the Engine separately, and a
#: normal ``C:\gauss26`` contains no ``mteng`` and its ``gauss.dll`` exports no
#: ``GAUSS_*`` symbols. Checked for anyway, so that a machine which does have it
#: gets told rather than silently running the slower backend for ever.
_ENGINE_LIBRARY = {
    "Windows": ("mteng.dll",),
    "Darwin": ("libmteng.dylib",),
    "Linux": ("libmteng.so",),
}


def find_engine_library() -> Optional[Path]:
    """The GAUSS Engine shared library, if this machine has one.

    Looked for under ``MTENGHOME`` first — the variable Aptech's own
    documentation uses — then beside the desktop installation.
    """
    names = _ENGINE_LIBRARY.get(platform.system(), ())
    if not names:
        return None

    roots: List[Path] = []
    if value := os.environ.get("MTENGHOME"):
        roots.append(Path(value))
        roots.append(Path(value) / "bin")
    roots.extend(find_gauss())

    for root in roots:
        for name in names:
            candidate = root / name
            if candidate.is_file():
                return candidate
    return None


@register
class GaussEngine(BaseEngine):
    """GAUSS, through its terminal executable."""

    name = "gauss"
    display_name = "GAUSS"
    declared_capabilities = (
        Capability.EXECUTE,
        Capability.PUSH_FRAME,
        Capability.PULL_FRAME,
        Capability.PUSH_SCALAR,
        Capability.PULL_SCALAR,
        Capability.PULL_MATRIX,
        Capability.RESTART,
        Capability.GRAPHICS,
        Capability.OLS,
    )

    def __init__(self, **options: Any) -> None:
        super().__init__(**options)
        self._backend: Any = None
        self._installs: List[Path] = []
        self._executable_path: Optional[Path] = None
        self._version_cache_value: Optional[str] = None
        self._last_frame: Optional[str] = None

    # ------------------------------------------------------------------ #
    # detection
    # ------------------------------------------------------------------ #
    def _detect(self) -> bool:
        self._installs = find_gauss()
        if not self._installs:
            self._detect_error = (
                "No GAUSS installation was found. EconEnv looks at gauss.home, the "
                "GAUSSHOME and MTENGHOME environment variables, and the usual "
                "install locations (C:\\gauss* on Windows). Set the path if yours "
                "is elsewhere:  %econ config gauss.home C:/gauss26"
            )
            return False

        chosen = self._installs[0]
        executable = find_executable(chosen)
        if executable is None:  # pragma: no cover - find_gauss filters these out
            self._detect_error = f"{chosen} has no tgauss executable."
            return False

        self._home = str(chosen)
        self._executable = str(executable)
        self._executable_path = executable
        self._backend_kind = self._requested_backend()
        return True

    def _requested_backend(self) -> str:
        """Which backend to use, and why the answer is not always what was asked.

        ``auto`` resolves to ``cli`` because that is the only backend built. A
        request for ``native`` is reported rather than silently downgraded, and
        the report distinguishes the two very different situations: the GAUSS
        Engine is not on this machine at all, or it is present and EconEnv
        simply cannot drive it yet.
        """
        choice = str(_config.get_option("gauss", "backend", "auto") or "auto").lower()
        if choice == "native":
            return "native-present" if find_engine_library() else "native-absent"
        return "cli"

    def _static_version(self) -> Optional[str]:
        if self._version_cache_value is None and self._executable_path is not None:
            self._version_cache_value = probe_version(self._executable_path)
        return self._version_cache_value

    def _version(self) -> Optional[str]:
        """The running session's version.

        For GAUSS this is the same number the executable's banner reports: the
        CLI backend runs that exact executable, so unlike EViews there is no way
        for the version on disk and the version running to disagree.
        """
        return self._static_version()

    def _info_detail(self) -> Dict[str, Any]:
        detail: Dict[str, Any] = {
            "installations": [str(p) for p in self._installs],
            "using": self._home,
        }
        if self._executable_path is not None:
            detail.update(describe(self._executable_path))
        kind = getattr(self, "_backend_kind", "cli")
        if kind == "native-absent":
            detail["backend"] = (
                "cli — native was requested, but the GAUSS Engine (mteng) is not "
                "on this machine. It is licensed separately from desktop GAUSS; a "
                "normal installation has no mteng library and its gauss.dll "
                "exports no GAUSS_* symbols."
            )
        elif kind == "native-present":
            detail["backend"] = (
                f"cli — the GAUSS Engine was found at {find_engine_library()}, but "
                "EconEnv has no binding to it yet. Please open an issue: the "
                "backend interface exists and this is the machine that could "
                "prove one works."
            )
        detail["session"] = (
            "One process per cell. Values are carried between cells with GAUSS's "
            "own save/load; procedures and #include state are not."
        )
        return detail

    # ------------------------------------------------------------------ #
    # lifecycle
    # ------------------------------------------------------------------ #
    def _start(self) -> None:
        assert self._executable_path is not None
        self._backend = GaussCliBackend(self._executable_path, Path(self._home or "."))
        self._backend.start()

    def _stop(self) -> None:
        if self._backend is not None:
            self._backend.stop()
            self._backend = None

    # ------------------------------------------------------------------ #
    # execution
    # ------------------------------------------------------------------ #
    def _execute(self, code: str, **kwargs: Any) -> ExecutionResult:
        timeout = float(_config.get_option("gauss", "timeout", 600) or 600)
        capture = kwargs.get("capture_graphs", True)

        target, program = self._with_graphics(code) if capture else (None, code)
        # A target the cell named itself is not ours to delete afterwards.
        theirs = bool(target) and program is code

        if theirs and target is not None:
            suffix = target.suffix.lstrip(".").lower()
            if suffix in _UNSUPPORTED_PLOT:
                raise EngineExecutionError(
                    f"GAUSS's plotSave cannot write {suffix!r}. It reports only "
                    '"Program execute failed", which is why EconEnv says so '
                    "first.\n"
                    f"  Supported here: {', '.join(sorted(_GRAPHICS_MIME))}.",
                    engine=self.name,
                    code=code,
                )

        text, error = self._backend.execute(program, timeout=timeout)
        if error:
            raise EngineExecutionError(error, engine=self.name, code=code)

        figures = self._read_figure(target, keep=theirs) if target else []
        return ExecutionResult(engine=self.name, code=code, stdout=text, figures=figures)

    # ------------------------------------------------------------------ #
    # graphics
    # ------------------------------------------------------------------ #
    def _graphics_format(self) -> str:
        """``svg`` by default: vector, and what a journal asks for."""
        choice = str(_config.get_option("gauss", "graphics", "svg") or "svg").lower()
        return choice if choice in _GRAPHICS_MIME or choice == "off" else "svg"

    def _with_graphics(self, code: str) -> tuple:
        """Append a ``plotSave`` when — and only when — one is needed.

        A cell that already calls ``plotSave`` has said where it wants the
        figure. Adding a second call would draw it twice and leave EconEnv
        showing its own copy rather than the file the researcher named, so the
        explicit save wins and its file is what gets displayed.
        """
        fmt = self._graphics_format()
        if fmt == "off" or not _PLOT_CALL.search(code):
            return None, code

        saved = _PLOT_SAVE.search(code)
        if saved is not None:
            return Path(saved.group(1)), code

        target = self._backend.session / f"econenv_plot_{uuid.uuid4().hex[:8]}.{fmt}"
        if fmt in ("png", "jpg", "jpeg"):
            width = int(_config.get_option("gauss", "width", _RASTER_PIXELS[0]))
            height = int(_config.get_option("gauss", "height", _RASTER_PIXELS[1]))
            unit = "px"
        else:
            width, height = _VECTOR_INCHES
            unit = "in"
        destination = str(target).replace("\\", "/")
        return target, (
            f'{code.rstrip()}\nplotSave("{destination}", {width} | {height}, "{unit}");'
        )

    def _read_figure(self, target: Path, keep: bool = False) -> List[Any]:
        """The saved plot as a Figure, or nothing if GAUSS did not write one.

        *keep* is True for a file the cell named itself: that one belongs to the
        researcher and must not be deleted after being displayed.
        """
        from ..results import Figure

        if not target.exists() or target.stat().st_size == 0:
            return []
        data = target.read_bytes()
        if not keep:
            target.unlink(missing_ok=True)

        suffix = target.suffix.lstrip(".").lower()
        mimetype = _GRAPHICS_MIME.get(suffix)
        if mimetype is None:
            # A format EconEnv cannot show inline — an .eps, say. The file is
            # still written; there is simply nothing to render.
            return []
        return [Figure(data=data, mimetype=mimetype, engine=self.name, name=target.stem)]

    # ------------------------------------------------------------------ #
    # data
    # ------------------------------------------------------------------ #
    def _push_frame(self, name: str, df: pd.DataFrame, **kwargs: Any) -> None:
        from ..bridges.gauss_bridge import push_frame

        push_frame(self, name, df, **kwargs)
        self._last_frame = name

    def _pull_frame(self, name: Optional[str], **kwargs: Any) -> pd.DataFrame:
        from ..bridges.gauss_bridge import pull_frame

        target = name or self._last_frame
        if target is None:
            raise DataTransferError(
                "GAUSS has no current dataset, so `pull` needs a name: "
                "econenv.pull('gauss', 'mydata').",
                engine=self.name,
                hint="Push one first, or name a matrix in the GAUSS workspace.",
            )
        return pull_frame(self, target, **kwargs)

    def _push_scalar(self, name: str, value: Any, **kwargs: Any) -> None:
        from ..bridges.gauss_bridge import push_value

        push_value(self, name, value)

    def _pull_value(self, name: str, **kwargs: Any) -> Any:
        from ..bridges.gauss_bridge import pull_value

        return pull_value(self, name, **kwargs)

    def _pull_scalar(self, expression: str) -> Any:
        from ..bridges.gauss_bridge import evaluate

        return evaluate(self, expression)

    # ------------------------------------------------------------------ #
    # models
    # ------------------------------------------------------------------ #
    def _fit_ols(self, spec, data: pd.DataFrame, meta: Any = None):
        """GAUSS's own ``ols`` procedure, so the comparison uses GAUSS's numbers.

        ``ols`` returns coefficients, standard errors, sigma and R-squared and
        stops there, so the t statistics, p-values, confidence interval,
        log-likelihood and information criteria are computed here — in GAUSS,
        from GAUSS's own residuals, using its ``cdftc`` and ``cdftci``.

        The formulae follow statsmodels' conventions (``-2l + 2k`` for AIC,
        ``sigma`` from ``n - k``) so that a difference between engines is a real
        difference and not a normalisation choice. Where a convention genuinely
        differs the comparison layer reports it rather than hiding it.
        """
        from ..results import ModelResult

        columns = [spec.depvar, *spec.exog]
        frame = data.loc[:, columns].dropna()

        self.ensure_started()
        self.push("eeY", frame[[spec.depvar]].to_numpy())
        self.push("eeX", frame[list(spec.exog)].to_numpy())

        # `ols` always fits a constant; without one the design matrix is passed
        # through a no-constant fit instead, rather than silently adding it.
        constant = "1" if spec.constant else "0"
        script = f"""
__output = 0;
_olsres = 1;
_con = {constant};
{{ eeVnam, eeM, eeB, eeStb, eeVc, eeSe, eeSigma, eeCx, eeRsq, eeResid, eeDw }} =
    ols("", eeY, eeX);
eeN = rows(eeY);
eeK = rows(eeB);
eeDf = eeN - eeK;
eeT = eeB ./ eeSe;
eeP = 2 * cdftc(abs(eeT), eeDf);
eeCrit = cdftci(0.025, eeDf);
eeLo = eeB - eeCrit .* eeSe;
eeHi = eeB + eeCrit .* eeSe;
eeSsr = sumc(eeResid .^ 2);
eeLl = -0.5 * eeN * (ln(2*pi) + ln(eeSsr / eeN) + 1);
eeAic = -2 * eeLl + 2 * eeK;
eeBic = -2 * eeLl + eeK * ln(eeN);
eeR2a = 1 - (1 - eeRsq) * (eeN - 1) / eeDf;
eeF = (eeRsq / (eeK - 1)) / ((1 - eeRsq) / eeDf);
eeTable = eeB ~ eeSe ~ eeT ~ eeP ~ eeLo ~ eeHi;
eeStats = eeN | eeK | eeDf | eeRsq | eeR2a | eeLl | eeAic | eeBic | eeSigma | eeF | eeDw;
"""
        exec_result = self.execute(script)

        from ..bridges.gauss_bridge import pull_matrix

        table = np.atleast_2d(pull_matrix(self, "eeTable"))
        stats = np.asarray(pull_matrix(self, "eeStats"), dtype=float).ravel()

        terms = (["_cons"] if spec.constant else []) + list(spec.exog)
        if len(terms) != table.shape[0]:  # pragma: no cover - shape guard
            terms = [f"b{i}" for i in range(table.shape[0])]

        nobs, _, df_resid, r2, r2_adj, loglik, aic, bic, sigma, fstat, dwstat = stats[:11]

        return ModelResult.from_arrays(
            engine=self.name,
            model="OLS",
            terms=terms,
            coef=table[:, 0],
            std_err=table[:, 1],
            stat=table[:, 2],
            pvalue=table[:, 3],
            ci_lower=table[:, 4],
            ci_upper=table[:, 5],
            depvar=spec.depvar,
            nobs=int(nobs),
            df_model=len(terms) - (1 if spec.constant else 0),
            df_resid=int(df_resid),
            r2=float(r2),
            r2_adj=float(r2_adj),
            loglik=float(loglik),
            aic=float(aic),
            bic=float(bic),
            rmse=float(sigma),
            fstat=float(fstat),
            vcov_type=spec.vcov or "nonrobust",
            engine_version=self.version(),
            command='ols("", y, X)',
            raw=exec_result.stdout,
            notes=[
                "GAUSS's ols reports coefficients, standard errors, sigma and "
                "R-squared; the t statistics, p-values, interval and information "
                "criteria are computed from its own residuals on statsmodels' "
                "conventions.",
                f"Durbin-Watson from GAUSS: {dwstat:.6f}",
            ],
        )

    def _pull_matrix(self, name: str) -> np.ndarray:
        from ..bridges.gauss_bridge import pull_matrix

        return pull_matrix(self, name)
