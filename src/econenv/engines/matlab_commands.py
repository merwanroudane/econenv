"""A searchable catalogue of MATLAB commands, for researchers.

The problem this solves is the same one ``eviews_commands`` solves, from the
other direction. An EViews user knows what they want and not how to type it. A
MATLAB user can usually type, but MATLAB is enormous and split across toolboxes
that may or may not be licensed — so the question is less "what is the command"
than "is there one, is it in a toolbox I have, and what does the call look
like".

So every entry records the toolbox it needs, and ``verified`` marks the entries
that were actually resolved against a live MATLAB through EconEnv:
``exist(name)`` for existence and ``which(name)`` for the toolbox. An entry that
could not be checked on this machine is documented syntax, and says so rather
than implying it was tested.

``docs/engines/matlab-commands.md`` is generated from this module, so the page
and ``%econ matlab`` cannot drift apart.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Dict, List, Optional

#: Toolbox label meaning "ships with every MATLAB".
BASE = "MATLAB"


def _tick(verified: bool) -> str:
    """A check mark where the console can render one, ASCII where it cannot.

    The default Windows console is cp1252 and raises UnicodeEncodeError on
    U+2713, which would turn "help me find a command" into a traceback.
    """
    if not verified:
        return " "
    encoding = getattr(sys.stdout, "encoding", None) or "ascii"
    try:
        "✓".encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return "*"
    return "✓"


@dataclass(frozen=True)
class Command:
    """One MATLAB function, described for someone doing applied research."""

    name: str
    category: str
    does: str
    example: str
    toolbox: str = BASE
    keywords: str = ""
    notes: str = ""
    verified: bool = False

    def __str__(self) -> str:
        lines = [f"{_tick(self.verified)} {self.name}", f"    {self.does}"]
        if self.toolbox != BASE:
            lines.append(f"    needs: {self.toolbox}")
        # Examples are multi-line (a %%matlab header and the code), so the
        # continuation has to be indented or the block loses its shape.
        example = self.example.replace("\n", "\n         ")
        lines.append(f"    e.g. {example}")
        if self.notes:
            lines.append(f"    note: {self.notes}")
        return "\n".join(lines)


CATEGORIES: Dict[str, str] = {
    "help": "Finding functions and reading MATLAB's own documentation",
    "workspace": "Inspecting what exists and what type it is",
    "data": "Reading and writing files, tables and timetables",
    "clean": "Missing values, reshaping, joining and grouping",
    "stats": "Descriptive statistics and correlation",
    "graphics": "Plotting, layout and saving figures",
    "regression": "Linear and generalised regression",
    "timeseries": "Autocorrelation, ARIMA/VAR, unit roots and forecasting",
    "wavelet": "Wavelet and frequency-domain analysis",
    "optimization": "Minimisation and constrained optimisation",
    "matrix": "Linear algebra and numerical computing",
}

#: Toolbox names as ``ver`` reports them, for the availability check.
STATS = "Statistics and Machine Learning Toolbox"
ECON = "Econometrics Toolbox"
WAVELET = "Wavelet Toolbox"
SIGNAL = "Signal Processing Toolbox"
OPTIM = "Optimization Toolbox"


COMMANDS: List[Command] = [
    # ---------------------------------------------------------------- help
    Command(
        "help",
        "help",
        "One-screen help for a function, in the notebook.",
        "%%matlab\nhelp fitlm",
        keywords="documentation manual",
        verified=True,
    ),
    Command(
        "doc",
        "help",
        "Open the full documentation page for a function.",
        "%%matlab\ndoc arima",
        keywords="documentation browser",
        notes="Opens MATLAB's own browser window, not the notebook.",
        verified=True,
    ),
    Command(
        "lookfor",
        "help",
        "Search the one-line summary of every function.",
        "%%matlab\nlookfor cointegration",
        keywords="search find",
        verified=True,
    ),
    Command(
        "which",
        "help",
        "Where a function lives — and so which toolbox it needs.",
        "%%matlab\nwhich wcoherence",
        keywords="path toolbox locate",
        verified=True,
    ),
    Command(
        "exist",
        "help",
        "Whether a name is a variable, function or file.",
        "%%matlab\nexist('fitlm')",
        keywords="defined available",
        verified=True,
    ),
    Command(
        "ver",
        "help",
        "MATLAB release and every licensed toolbox.",
        "%%matlab\nver",
        keywords="version toolbox licence",
        verified=True,
    ),
    Command(
        "license",
        "help",
        "Whether a named toolbox is licensed here.",
        "%%matlab\nlicense('test', 'Statistics_Toolbox')",
        keywords="licence toolbox",
        verified=True,
    ),
    Command(
        "methods",
        "help",
        "The methods defined on an object, such as a fitted model.",
        "%%matlab\nmethods(mdl)",
        keywords="object class",
        verified=True,
    ),
    Command(
        "properties",
        "help",
        "The properties of an object.",
        "%%matlab\nproperties(mdl)",
        keywords="object fields",
        verified=True,
    ),
    # ----------------------------------------------------------- workspace
    Command(
        "who",
        "workspace",
        "The names currently in the MATLAB workspace.",
        "%%matlab\nwho",
        keywords="variables list",
        verified=True,
    ),
    Command(
        "whos",
        "workspace",
        "Names with size, bytes and class — the workspace browser.",
        "%%matlab\nwhos",
        keywords="variables size class",
        verified=True,
    ),
    Command(
        "class",
        "workspace",
        "The MATLAB class of a value, which decides how it crosses to Python.",
        "%%matlab\nclass(x)",
        keywords="type",
        verified=True,
    ),
    Command(
        "size",
        "workspace",
        "Rows and columns.",
        "%%matlab\nsize(X)",
        keywords="shape dimensions",
        verified=True,
    ),
    Command(
        "numel",
        "workspace",
        "Total number of elements.",
        "%%matlab\nnumel(x)",
        keywords="length count",
        verified=True,
    ),
    Command(
        "head",
        "workspace",
        "The first rows of a table or timetable.",
        "%%matlab\nhead(T, 8)",
        keywords="preview first",
        verified=True,
    ),
    Command(
        "tail",
        "workspace",
        "The last rows of a table or timetable.",
        "%%matlab\ntail(T, 8)",
        keywords="preview last",
        verified=True,
    ),
    Command(
        "summary",
        "workspace",
        "Per-variable summary of a table: type, range, missing count.",
        "%%matlab\nsummary(T)",
        keywords="describe overview",
        notes="A method on a table/timetable: summary(T).",
        verified=True,
    ),
    # ---------------------------------------------------------------- data
    Command(
        "readtable",
        "data",
        "Read a delimited or Excel file into a table.",
        "%%matlab\nT = readtable('data.csv');",
        keywords="import csv excel load",
        verified=True,
    ),
    Command(
        "writetable",
        "data",
        "Write a table to CSV or Excel.",
        "%%matlab\nwritetable(T, 'out.csv');",
        keywords="export save csv excel",
        verified=True,
    ),
    Command(
        "readmatrix",
        "data",
        "Read a numeric file straight into a matrix.",
        "%%matlab\nX = readmatrix('data.csv');",
        keywords="import numeric",
        verified=True,
    ),
    Command(
        "writematrix",
        "data",
        "Write a numeric matrix to a file.",
        "%%matlab\nwritematrix(X, 'out.csv');",
        keywords="export numeric",
        verified=True,
    ),
    Command(
        "detectImportOptions",
        "data",
        "Inspect and adjust how a file will be parsed before reading it.",
        "%%matlab\nopts = detectImportOptions('data.csv');",
        keywords="import options types",
        verified=True,
    ),
    Command(
        "table",
        "data",
        "Build a table from columns, with variable names.",
        "%%matlab\nT = table(y, x, 'VariableNames', {'y','x'});",
        keywords="dataframe construct",
        verified=True,
    ),
    Command(
        "array2table",
        "data",
        "Turn a numeric matrix into a named table.",
        "%%matlab\nT = array2table(X, 'VariableNames', {'a','b'});",
        keywords="convert matrix",
        verified=True,
    ),
    Command(
        "table2array",
        "data",
        "Drop the names and get the numeric matrix back.",
        "%%matlab\nX = table2array(T);",
        keywords="convert matrix",
        verified=True,
    ),
    Command(
        "timetable",
        "data",
        "A table indexed by time — the right shape for time series.",
        "%%matlab\nTT = timetable(dates, y);",
        keywords="time series dates index",
        verified=True,
    ),
    Command(
        "retime",
        "data",
        "Resample a timetable to a new frequency.",
        "%%matlab\nQ = retime(TT, 'quarterly', 'mean');",
        keywords="resample frequency aggregate",
        notes="A timetable method: retime(TT, ...).",
        verified=True,
    ),
    Command(
        "synchronize",
        "data",
        "Align several timetables onto one time base.",
        "%%matlab\nboth = synchronize(TT1, TT2);",
        keywords="merge align join time",
        notes="A timetable method: synchronize(TT1, TT2).",
        verified=True,
    ),
    # --------------------------------------------------------------- clean
    Command(
        "rmmissing",
        "clean",
        "Drop rows with missing values — listwise deletion.",
        "%%matlab\nT = rmmissing(T);",
        keywords="dropna missing na listwise",
        verified=True,
    ),
    Command(
        "fillmissing",
        "clean",
        "Fill gaps by interpolation, previous value or a constant.",
        "%%matlab\nT = fillmissing(T, 'linear');",
        keywords="impute interpolate na",
        verified=True,
    ),
    Command(
        "ismissing",
        "clean",
        "A logical mask of what is missing.",
        "%%matlab\nsum(ismissing(T))",
        keywords="na null count",
        verified=True,
    ),
    Command(
        "normalize",
        "clean",
        "Standardise, rescale or centre.",
        "%%matlab\nZ = normalize(X);",
        keywords="standardize zscore scale",
        verified=True,
    ),
    Command(
        "sortrows",
        "clean",
        "Sort a table or matrix by one or more columns.",
        "%%matlab\nT = sortrows(T, 'date');",
        keywords="order sort arrange",
        verified=True,
    ),
    Command(
        "groupsummary",
        "clean",
        "Statistics by group — MATLAB's group-by.",
        "%%matlab\nG = groupsummary(T, 'country', 'mean', 'gdp');",
        keywords="groupby aggregate collapse by",
        verified=True,
    ),
    Command(
        "innerjoin",
        "clean",
        "Keep rows present in both tables.",
        "%%matlab\nJ = innerjoin(T1, T2, 'Keys', 'id');",
        keywords="merge join",
        notes="A table method: innerjoin(T1, T2, ...).",
        verified=True,
    ),
    Command(
        "outerjoin",
        "clean",
        "Keep rows from both, filling what is absent.",
        "%%matlab\nJ = outerjoin(T1, T2, 'Keys', 'id');",
        keywords="merge join",
        notes="A table method: outerjoin(T1, T2, ...).",
        verified=True,
    ),
    Command(
        "varfun",
        "clean",
        "Apply a function to each variable of a table.",
        "%%matlab\nvarfun(@mean, T);",
        keywords="apply map columns",
        notes="A table method: varfun(@f, T).",
        verified=True,
    ),
    # --------------------------------------------------------------- stats
    Command(
        "mean", "stats", "Column means.", "%%matlab\nmean(X)", keywords="average", verified=True
    ),
    Command(
        "median",
        "stats",
        "Column medians.",
        "%%matlab\nmedian(X)",
        keywords="middle",
        verified=True,
    ),
    Command(
        "std",
        "stats",
        "Standard deviation, normalised by n-1.",
        "%%matlab\nstd(X)",
        keywords="dispersion sd",
        verified=True,
    ),
    Command("var", "stats", "Variance.", "%%matlab\nvar(X)", keywords="dispersion", verified=True),
    Command(
        "quantile",
        "stats",
        "Sample quantiles.",
        "%%matlab\nquantile(x, [.25 .5 .75])",
        keywords="percentile median",
        verified=True,
        notes="Base MATLAB since it moved to datafun; no Statistics licence needed.",
    ),
    Command(
        "prctile",
        "stats",
        "Percentiles.",
        "%%matlab\nprctile(x, 95)",
        keywords="quantile percentile",
        verified=True,
        notes="Base MATLAB since it moved to datafun; no Statistics licence needed.",
    ),
    Command(
        "corr",
        "stats",
        "Correlation with p-values, Pearson/Spearman/Kendall.",
        "%%matlab\n[R, P] = corr(X);",
        toolbox=STATS,
        keywords="correlation spearman kendall pearson",
        verified=True,
    ),
    Command(
        "corrcoef",
        "stats",
        "Pearson correlation, in base MATLAB.",
        "%%matlab\ncorrcoef(x, y)",
        keywords="correlation",
        verified=True,
    ),
    Command(
        "cov",
        "stats",
        "Covariance matrix.",
        "%%matlab\ncov(X)",
        keywords="covariance",
        verified=True,
    ),
    # ------------------------------------------------------------ graphics
    Command(
        "plot",
        "graphics",
        "Line plot — the default for a series against time.",
        "%%matlab\nplot(dates, y); grid on;",
        keywords="line chart series",
        verified=True,
    ),
    Command(
        "scatter",
        "graphics",
        "Scatter plot, optionally sized and coloured by a third variable.",
        "%%matlab\nscatter(x, y, 'filled');",
        keywords="points xy cloud",
        verified=True,
    ),
    Command(
        "histogram",
        "graphics",
        "Histogram with automatic or chosen bins.",
        "%%matlab\nhistogram(resid, 30);",
        keywords="distribution bins density",
        verified=True,
    ),
    Command(
        "boxchart",
        "graphics",
        "Box plot by group, without the Statistics toolbox.",
        "%%matlab\nboxchart(g, y);",
        keywords="boxplot distribution group",
        verified=True,
    ),
    Command(
        "bar",
        "graphics",
        "Bar chart.",
        "%%matlab\nbar(categories, values);",
        keywords="column chart",
        verified=True,
    ),
    Command(
        "tiledlayout",
        "graphics",
        "A grid of panels — the modern replacement for subplot.",
        "%%matlab\ntiledlayout(2,2); nexttile; plot(x,y);",
        keywords="subplot panel grid facet multiple",
        verified=True,
    ),
    Command(
        "nexttile",
        "graphics",
        "Move to the next panel of a tiled layout.",
        "%%matlab\nnexttile; histogram(r);",
        keywords="subplot panel",
        verified=True,
    ),
    Command(
        "yyaxis",
        "graphics",
        "A second y axis on the right.",
        "%%matlab\nyyaxis right; plot(x, z);",
        keywords="twin axis dual scale",
        verified=True,
    ),
    Command(
        "legend",
        "graphics",
        "Label the series.",
        "%%matlab\nlegend({'actual','fitted'}, 'Location', 'best');",
        keywords="key labels",
        verified=True,
    ),
    Command(
        "exportgraphics",
        "graphics",
        "Save a figure at publication quality — vector for PDF/EPS, chosen DPI for PNG.",
        "%%matlab\nexportgraphics(gcf, 'fig1.pdf', 'ContentType', 'vector');",
        keywords="save export pdf png dpi vector publication",
        notes="EconEnv uses this to capture figures; see %econ matlab export.",
        verified=True,
    ),
    # ---------------------------------------------------------- regression
    Command(
        "fitlm",
        "regression",
        "Linear regression with a formula, diagnostics and a coefficient table.",
        "%%matlab\nmdl = fitlm(T, 'y ~ x1 + x2');\ndisp(mdl)",
        toolbox=STATS,
        keywords="ols regression linear lm estimate",
        verified=True,
    ),
    Command(
        "regress",
        "regression",
        "Least squares returning coefficients and confidence intervals.",
        "%%matlab\n[b, bint] = regress(y, [ones(n,1) X]);",
        toolbox=STATS,
        keywords="ols least squares",
        verified=True,
    ),
    Command(
        "fitglm",
        "regression",
        "Generalised linear model — logit, probit, Poisson.",
        "%%matlab\nmdl = fitglm(T, 'y ~ x', 'Distribution', 'binomial');",
        toolbox=STATS,
        keywords="logit probit poisson glm binary",
        verified=True,
    ),
    Command(
        "stepwiselm",
        "regression",
        "Stepwise selection of terms.",
        "%%matlab\nmdl = stepwiselm(T, 'y ~ 1');",
        toolbox=STATS,
        keywords="selection stepwise",
        verified=True,
    ),
    Command(
        "robustfit",
        "regression",
        "Robust regression, down-weighting outliers.",
        "%%matlab\nb = robustfit(X, y);",
        toolbox=STATS,
        keywords="outliers m-estimator",
        verified=True,
    ),
    Command(
        "coefCI",
        "regression",
        "Confidence intervals for fitted coefficients.",
        "%%matlab\ncoefCI(mdl)",
        toolbox=STATS,
        keywords="confidence interval",
        notes="A method on the fitted model: coefCI(mdl).",
        verified=True,
    ),
    Command(
        "predict",
        "regression",
        "Fitted or forecast values, with prediction intervals.",
        "%%matlab\n[yhat, ci] = predict(mdl, Tnew);",
        toolbox=STATS,
        keywords="fitted forecast prediction",
        notes="A method on the fitted model: predict(mdl, Tnew).",
        verified=True,
    ),
    Command(
        "anova",
        "regression",
        "Analysis of variance for a fitted model.",
        "%%matlab\nanova(mdl, 'summary')",
        toolbox=STATS,
        keywords="f test variance",
        verified=True,
    ),
    # ---------------------------------------------------------- timeseries
    Command(
        "autocorr",
        "timeseries",
        "Sample autocorrelation function with confidence bounds.",
        "%%matlab\nautocorr(y, 24);",
        toolbox=ECON,
        keywords="acf correlogram lag",
        verified=True,
    ),
    Command(
        "parcorr",
        "timeseries",
        "Partial autocorrelation function.",
        "%%matlab\nparcorr(y, 24);",
        toolbox=ECON,
        keywords="pacf lag order",
        verified=True,
    ),
    Command(
        "adftest",
        "timeseries",
        "Augmented Dickey-Fuller unit root test.",
        "%%matlab\n[h, p] = adftest(y, 'Model', 'ARD');",
        toolbox=ECON,
        keywords="unit root stationarity dickey fuller",
        verified=True,
    ),
    Command(
        "kpsstest",
        "timeseries",
        "KPSS test, with stationarity as the null.",
        "%%matlab\n[h, p] = kpsstest(y);",
        toolbox=ECON,
        keywords="unit root stationarity",
        verified=True,
    ),
    Command(
        "pptest",
        "timeseries",
        "Phillips-Perron unit root test.",
        "%%matlab\n[h, p] = pptest(y);",
        toolbox=ECON,
        keywords="unit root stationarity",
        verified=True,
    ),
    Command(
        "arima",
        "timeseries",
        "Specify an ARIMA/SARIMA model before estimating it.",
        "%%matlab\nmdl = arima(1,1,1);",
        toolbox=ECON,
        keywords="arma sarima box jenkins",
        verified=True,
    ),
    Command(
        "estimate",
        "timeseries",
        "Fit a specified model to data by maximum likelihood.",
        "%%matlab\nfit = estimate(mdl, y);",
        toolbox=ECON,
        keywords="fit mle estimate",
        notes="A method on the model object: estimate(arima(1,1,1), y).",
        verified=True,
    ),
    Command(
        "forecast",
        "timeseries",
        "Out-of-sample forecasts with error bands.",
        "%%matlab\n[yf, ymse] = forecast(fit, 8, y);",
        toolbox=ECON,
        keywords="predict out of sample horizon",
        notes="A method on the fitted model: forecast(fit, 8, y).",
        verified=True,
    ),
    Command(
        "infer",
        "timeseries",
        "Residuals implied by a fitted model.",
        "%%matlab\n[e, v] = infer(fit, y);",
        toolbox=ECON,
        keywords="residuals errors",
        notes="A method on the fitted model: infer(fit, y).",
        verified=True,
    ),
    Command(
        "simulate",
        "timeseries",
        "Simulate paths from a fitted or specified model.",
        "%%matlab\npaths = simulate(fit, 100, 'NumPaths', 500);",
        toolbox=ECON,
        keywords="monte carlo bootstrap paths",
        verified=True,
    ),
    Command(
        "varm",
        "timeseries",
        "Vector autoregression.",
        "%%matlab\nmdl = varm(3, 2);\nfit = estimate(mdl, Y);",
        toolbox=ECON,
        keywords="var vector autoregression multivariate",
        verified=True,
    ),
    Command(
        "egcitest",
        "timeseries",
        "Engle-Granger cointegration test.",
        "%%matlab\n[h, p] = egcitest(Y);",
        toolbox=ECON,
        keywords="cointegration engle granger",
        verified=True,
    ),
    Command(
        "jcitest",
        "timeseries",
        "Johansen cointegration test.",
        "%%matlab\n[h, pV] = jcitest(Y);",
        toolbox=ECON,
        keywords="cointegration johansen trace eigenvalue rank",
        verified=True,
    ),
    Command(
        "archtest",
        "timeseries",
        "Engle's test for ARCH effects.",
        "%%matlab\n[h, p] = archtest(e);",
        toolbox=ECON,
        keywords="heteroskedasticity garch volatility",
        verified=True,
    ),
    Command(
        "garch",
        "timeseries",
        "GARCH volatility model.",
        "%%matlab\nmdl = garch(1,1);\nfit = estimate(mdl, e);",
        toolbox=ECON,
        keywords="volatility conditional variance",
        verified=True,
    ),
    Command(
        "lmctest",
        "timeseries",
        "Lagrange multiplier test for a conditional mean.",
        "%%matlab\n[h, p] = lmctest(e);",
        toolbox=ECON,
        keywords="lm test specification",
        verified=True,
    ),
    # ------------------------------------------------------------- wavelet
    Command(
        "cwt",
        "wavelet",
        "Continuous wavelet transform — the scalogram.",
        "%%matlab\ncwt(y, years(1/12));",
        toolbox=WAVELET,
        keywords="continuous wavelet scalogram time frequency",
        verified=True,
    ),
    Command(
        "icwt",
        "wavelet",
        "Invert a continuous wavelet transform.",
        "%%matlab\nyr = icwt(wt);",
        toolbox=WAVELET,
        keywords="inverse reconstruct",
        verified=True,
    ),
    Command(
        "wcoherence",
        "wavelet",
        "Wavelet coherence between two series, with phase arrows.",
        "%%matlab\nwcoherence(x, y);",
        toolbox=WAVELET,
        keywords="coherence comovement phase lead lag partial",
        verified=True,
    ),
    Command(
        "modwt",
        "wavelet",
        "Maximal overlap discrete wavelet transform, for decomposition by scale.",
        "%%matlab\nw = modwt(y, 'db4', 6);",
        toolbox=WAVELET,
        keywords="discrete decomposition multiresolution scale",
        verified=True,
    ),
    Command(
        "modwtmra",
        "wavelet",
        "Multiresolution analysis from a MODWT.",
        "%%matlab\nmra = modwtmra(w);",
        toolbox=WAVELET,
        keywords="multiresolution decomposition",
        verified=True,
    ),
    Command(
        "periodogram",
        "wavelet",
        "Power spectral density by periodogram.",
        "%%matlab\nperiodogram(y);",
        toolbox=SIGNAL,
        keywords="spectrum frequency density",
        verified=True,
    ),
    Command(
        "pwelch",
        "wavelet",
        "Welch's averaged spectral estimate.",
        "%%matlab\npwelch(y);",
        toolbox=SIGNAL,
        keywords="spectrum frequency smoothing",
        verified=True,
    ),
    # -------------------------------------------------------- optimization
    Command(
        "fminsearch",
        "optimization",
        "Unconstrained minimisation, derivative-free. Base MATLAB.",
        "%%matlab\nb = fminsearch(@(b) sse(b), b0);",
        keywords="minimise nelder mead simplex",
        verified=True,
    ),
    Command(
        "fminunc",
        "optimization",
        "Unconstrained minimisation using gradients.",
        "%%matlab\nb = fminunc(@obj, b0);",
        toolbox=OPTIM,
        keywords="minimise gradient quasi newton",
        verified=True,
    ),
    Command(
        "fmincon",
        "optimization",
        "Minimisation subject to bounds and constraints.",
        "%%matlab\nb = fmincon(@obj, b0, A, c);",
        toolbox=OPTIM,
        keywords="constrained minimise bounds",
        verified=True,
    ),
    Command(
        "linprog",
        "optimization",
        "Linear programming.",
        "%%matlab\nx = linprog(f, A, b);",
        toolbox=OPTIM,
        keywords="linear program lp",
        verified=True,
    ),
    Command(
        "optimoptions",
        "optimization",
        "Set solver options — tolerance, display, algorithm.",
        "%%matlab\nopts = optimoptions('fmincon', 'Display', 'off');",
        toolbox=OPTIM,
        keywords="options tolerance algorithm",
        verified=True,
    ),
    Command(
        "lsqnonlin",
        "optimization",
        "Nonlinear least squares.",
        "%%matlab\nb = lsqnonlin(@resid, b0);",
        toolbox=OPTIM,
        keywords="nls curve fitting",
        verified=True,
    ),
    # -------------------------------------------------------------- matrix
    Command(
        "inv",
        "matrix",
        "Matrix inverse. Prefer the backslash operator for solving.",
        "%%matlab\ninv(A)",
        keywords="inverse",
        notes="For A*x = b use x = A\\b: more accurate and faster than inv(A)*b.",
        verified=True,
    ),
    Command(
        "pinv",
        "matrix",
        "Moore-Penrose pseudoinverse, for rank-deficient problems.",
        "%%matlab\npinv(A)",
        keywords="pseudoinverse singular rank",
        verified=True,
    ),
    Command(
        "eig",
        "matrix",
        "Eigenvalues and eigenvectors.",
        "%%matlab\n[V, D] = eig(A);",
        keywords="eigenvalue eigenvector spectral",
        verified=True,
    ),
    Command(
        "svd",
        "matrix",
        "Singular value decomposition.",
        "%%matlab\n[U, S, V] = svd(A);",
        keywords="decomposition singular pca",
        verified=True,
    ),
    Command(
        "chol",
        "matrix",
        "Cholesky factorisation of a positive definite matrix.",
        "%%matlab\nR = chol(S);",
        keywords="decomposition covariance factor",
        verified=True,
    ),
    Command(
        "qr",
        "matrix",
        "QR factorisation, as used by least squares.",
        "%%matlab\n[Q, R] = qr(X, 0);",
        keywords="decomposition orthogonal",
        verified=True,
    ),
    Command(
        "rank",
        "matrix",
        "Numerical rank.",
        "%%matlab\nrank(X)",
        keywords="collinearity singular",
        verified=True,
    ),
    Command(
        "cond",
        "matrix",
        "Condition number — how close to collinear the columns are.",
        "%%matlab\ncond(X)",
        keywords="collinearity conditioning stability",
        verified=True,
    ),
    Command(
        "mldivide",
        "matrix",
        "The backslash operator: solve A*x = b by least squares.",
        "%%matlab\nb = X \\ y;",
        keywords="solve least squares backslash regression",
        verified=True,
    ),
]


def categories() -> Dict[str, str]:
    """Category name to description."""
    return dict(CATEGORIES)


def by_category(name: str) -> List[Command]:
    """Every command in one category."""
    key = name.lower().strip()
    return [c for c in COMMANDS if c.category == key]


def get(name: str) -> Optional[Command]:
    """One command by exact name."""
    for command in COMMANDS:
        if command.name.lower() == name.lower().strip():
            return command
    return None


def find(term: str) -> List[Command]:
    """Commands matching a category, a name, or a word in the description.

    Category first, so ``%econ matlab timeseries`` lists that section rather
    than every entry whose text happens to contain the word.
    """
    needle = term.lower().strip()
    if not needle:
        return list(COMMANDS)
    if needle in CATEGORIES:
        return by_category(needle)

    scored = []
    for command in COMMANDS:
        haystack = " ".join(
            (command.name, command.does, command.keywords, command.category, command.notes)
        ).lower()
        if needle == command.name.lower():
            scored.append((0, command))
        elif needle in command.name.lower():
            scored.append((1, command))
        elif needle in command.keywords.lower():
            scored.append((2, command))
        elif needle in haystack:
            scored.append((3, command))
    return [c for _, c in sorted(scored, key=lambda pair: pair[0])]


def toolboxes() -> Dict[str, int]:
    """How many catalogued commands each toolbox accounts for."""
    counts: Dict[str, int] = {}
    for command in COMMANDS:
        counts[command.toolbox] = counts.get(command.toolbox, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))
