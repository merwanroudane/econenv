"""A searchable catalogue of EViews commands, for people who click.

EViews is normally driven from menus. In a notebook there are no menus, and a
researcher who has spent years in the GUI knows exactly *what* they want and
not at all *how to type it*. That gap — not any missing feature — is the thing
most likely to stop someone using EconEnv.

So the catalogue lives in the package rather than only in the documentation:
it is searchable from a cell with ``%econ eviews find cointegration`` while the
question is being asked, and ``docs/engines/eviews-commands.md`` is generated
from it, so the page and the tool can never drift apart.

Each entry records the menu path the user already knows, the command it maps
to, what it does in plain language, and a runnable example. ``verified`` marks
the entries that were actually run against EViews 13 through EconEnv; the rest
are documented syntax that this machine could not exercise, usually because it
needs a panel-structured workfile.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


def _tick(verified: bool) -> str:
    """A check mark where the console can render one, ASCII where it cannot.

    The default Windows console is cp1252 and raises UnicodeEncodeError on
    U+2713 — which would turn "help me find a command" into a traceback, the
    least forgivable place for one.
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
    """One EViews command, described the way a GUI user would look for it."""

    command: str
    category: str
    gui: str
    does: str
    example: str
    verified: bool = False

    def __str__(self) -> str:
        tick = _tick(self.verified)
        return (
            f"{tick} {self.command}\n    {self.does}\n    GUI: {self.gui}\n    e.g. {self.example}"
        )


CATEGORIES: Dict[str, str] = {
    "workfile": "Creating, opening and structuring workfiles and pages",
    "data": "Getting data in and out of EViews",
    "series": "Creating and transforming series",
    "sample": "Choosing which observations to use",
    "group": "Working with several series at once",
    "graph": "Every kind of plot, before and after estimation",
    "stats": "Descriptive statistics and simple tests",
    "unitroot": "Unit root and stationarity testing",
    "coint": "Cointegration testing",
    "estimate": "Estimating equations, systems and VARs",
    "results": "Reading what an estimation produced",
    "test": "Diagnostic and specification tests after estimation",
    "forecast": "Forecasting and fitted values",
    "var": "VAR and VEC output",
    "panel": "Panel data",
    "program": "Scalars, matrices, loops and control",
}


def _c(
    command: str, category: str, gui: str, does: str, example: str, verified: bool = False
) -> Command:
    return Command(command, category, gui, does, example, verified)


COMMANDS: Tuple[Command, ...] = (
    # ---------------------------------------------------------------- workfile
    _c(
        "wfcreate",
        "workfile",
        "File > New > Workfile",
        "Create a new workfile. The frequency letter comes first, then the start "
        "and end of the range: a annual, q quarterly, m monthly, d daily, u undated.",
        "wfcreate q 1990Q1 2020Q4",
        True,
    ),
    _c(
        "wfcreate(wf=name)",
        "workfile",
        "File > New > Workfile, with a name",
        "Same, but names the workfile so you can refer to it later.",
        "wfcreate(wf=mydata) q 1990Q1 2020Q4",
        True,
    ),
    _c(
        "wfopen",
        "workfile",
        "File > Open > EViews Workfile",
        "Open a workfile that already exists on disk.",
        'wfopen "C:\\work\\mydata.wf1"',
    ),
    _c(
        "wfsave",
        "workfile",
        "File > Save As",
        "Save the current workfile to disk.",
        'wfsave "C:\\work\\mydata.wf1"',
    ),
    _c(
        "pagecreate",
        "workfile",
        "Workfile window > New Page",
        "Add another page, which can hold a different frequency from the first.",
        "pagecreate(page=annual) a 1990 2020",
    ),
    _c(
        "pageselect",
        "workfile",
        "Click a page tab",
        "Switch to another page. Everything after this line acts on that page.",
        "pageselect annual",
        True,
    ),
    _c(
        "pagestruct",
        "workfile",
        "Proc > Structure/Resize Current Page",
        "Change how the page is structured — give it a date, or turn it into a panel.",
        "pagestruct(freq=q, start=1990Q1)",
    ),
    _c(
        "pagecopy",
        "workfile",
        "Proc > Copy/Extract from Current Page",
        "Copy the page, optionally converting it to another frequency.",
        "pagecopy(page=annual, freq=a, smpl=@all)",
    ),
    _c(
        "pagerename / pagedelete",
        "workfile",
        "Right-click a page tab",
        "Rename or delete a page.",
        "pagerename old new",
    ),
    # -------------------------------------------------------------------- data
    _c(
        "import",
        "data",
        "File > Import > Import from file",
        "Read a spreadsheet or text file into the current page.",
        'import "C:\\data\\file.xlsx" range="Sheet1!A1"',
    ),
    _c(
        "write",
        "data",
        "Proc > Export > Write to file",
        "Write a group out to CSV or Excel.",
        'g1.write(t=csv) "out.csv"',
    ),
    _c(
        "%%eviews -i df",
        "data",
        "no GUI equivalent",
        "Push a pandas DataFrame straight from Python into a new workfile. This "
        "is what EconEnv exists for — you do not need to save a CSV first.",
        "%%eviews -i df",
        True,
    ),
    _c(
        "econenv.pull",
        "data",
        "no GUI equivalent",
        "Bring the page, or one series, back into Python as a DataFrame.",
        'econenv.pull("eviews", "y")',
        True,
    ),
    # ------------------------------------------------------------------ series
    _c(
        "series",
        "series",
        "Object > New Object > Series, or Quick > Generate Series",
        "Create a new series from an expression. This is the workhorse: almost "
        "every variable you build starts with this word.",
        "series lny = log(y)",
        True,
    ),
    _c(
        "d(x)",
        "series",
        "type it in Generate Series",
        "First difference, x - x(-1). d(x,2) is the second difference.",
        "series dy = d(y)",
        True,
    ),
    _c(
        "dlog(x)",
        "series",
        "type it in Generate Series",
        "Log difference — the usual growth-rate transform for a level series.",
        "series g = dlog(y)",
        True,
    ),
    _c(
        "x(-1)",
        "series",
        "type it in Generate Series",
        "Lag. x(-1) is one period back, x(+1) one period forward.",
        "series ylag = y(-1)",
        True,
    ),
    _c(
        "@pch(x)",
        "series",
        "type it in Generate Series",
        "Percent change from the previous period.",
        "series pc = @pch(y)",
    ),
    _c(
        "@recode",
        "series",
        "type it in Generate Series",
        "Conditional value — the equivalent of an if/else. Use it to build dummies.",
        "series big = @recode(x>2, 1, 0)",
        True,
    ),
    _c(
        "@trend",
        "series",
        "type it in Generate Series",
        "A linear time trend, 0, 1, 2, ...",
        "series t = @trend",
        True,
    ),
    _c(
        "@seas(n)",
        "series",
        "type it in Generate Series",
        "Seasonal dummy: 1 in season n, 0 otherwise.",
        "series q2 = @seas(2)",
    ),
    _c(
        "@movav(x,n)",
        "series",
        "type it in Generate Series",
        "n-period moving average.",
        "series ma4 = @movav(y,4)",
    ),
    _c(
        "nrnd / rnd",
        "series",
        "type it in Generate Series",
        "Random draws: nrnd is standard normal, rnd is uniform on (0,1). Useful "
        "for testing a workflow before your real data arrives.",
        "series e = nrnd",
        True,
    ),
    _c(
        "rename / delete",
        "series",
        "Right-click an object",
        "Rename or delete any object — a series, an equation, a graph.",
        "delete x",
        True,
    ),
    # ------------------------------------------------------------------ sample
    _c(
        "smpl",
        "sample",
        "Sample button, or Quick > Sample",
        "Set which observations everything after this line will use. The single "
        "most common cause of results that do not match: forgetting to reset it.",
        "smpl 1995Q1 2015Q4",
        True,
    ),
    _c(
        "smpl @all",
        "sample",
        "Sample button > @all",
        "Use every observation again.",
        "smpl @all",
        True,
    ),
    _c(
        "smpl if",
        "sample",
        "Sample dialog, condition box",
        "Restrict to observations satisfying a condition.",
        "smpl @all if x>0",
    ),
    _c(
        "sample",
        "sample",
        "Object > New Object > Sample",
        "Save a named sample you can switch back to later.",
        "sample s1 1995Q1 2015Q4",
    ),
    # ------------------------------------------------------------------- group
    _c(
        "group",
        "group",
        "Select several series > Open as Group",
        "Bundle series together so you can plot or test them jointly. Many "
        "multi-series views only exist on a group.",
        "group g1 x y z",
        True,
    ),
    _c(
        "g.add / g.drop",
        "group",
        "Group window > Add/Drop",
        "Change which series a group contains.",
        "g1.add w",
    ),
    # ------------------------------------------------------------------- graph
    _c(
        "line",
        "graph",
        "Series > View > Graph > Line",
        "Line plot. Three forms all work: 'line x' as a command, 'x.line' as a "
        "view, or 'graph g1.line x' to keep the graph as an object you can edit.",
        "line x",
        True,
    ),
    _c("bar", "graph", "Series > View > Graph > Bar", "Bar chart.", "bar x", True),
    _c("area", "graph", "Series > View > Graph > Area", "Filled area plot.", "area x", True),
    _c(
        "spike",
        "graph",
        "Series > View > Graph > Spike",
        "Spike plot — good for sparse or event data.",
        "spike x",
        True,
    ),
    _c("x.dot", "graph", "Series > View > Graph > Dot Plot", "Dot plot.", "x.dot", True),
    _c(
        "x.seasplot",
        "graph",
        "Series > View > Graph > Seasonal Plot",
        "Plots each season's path separately, so seasonality is visible by eye.",
        "x.seasplot",
        True,
    ),
    _c(
        "x.hist",
        "graph",
        "Series > View > Descriptive Statistics > Histogram",
        "Histogram of one series.",
        "x.hist",
        True,
    ),
    _c(
        "x.distplot",
        "graph",
        "Series > View > Graph > Distribution",
        "Kernel density — a smoothed histogram.",
        "x.distplot",
        True,
    ),
    _c(
        "x.boxplot",
        "graph",
        "Series > View > Graph > Boxplot",
        "Boxplot: median, quartiles and outliers.",
        "x.boxplot",
        True,
    ),
    _c(
        "x.qqplot",
        "graph",
        "Series > View > Graph > Quantile-Quantile",
        "Q-Q plot against the normal — a quick normality check by eye.",
        "x.qqplot",
        True,
    ),
    _c(
        "scat",
        "graph",
        "Group > View > Graph > Scatter",
        "Scatter plot of two series. Add (r) for a fitted regression line.",
        "scat x y",
        True,
    ),
    _c(
        "xyline",
        "graph",
        "Group > View > Graph > XY Line",
        "Plots one series against another, joined in order.",
        "xyline x y",
        True,
    ),
    _c(
        "g.scatmat",
        "graph",
        "Group > View > Graph > Scatterplot Matrix",
        "All pairwise scatters in one grid — a fast look at a whole dataset.",
        "g1.scatmat",
        True,
    ),
    _c(
        "g.line",
        "graph",
        "Group > View > Graph > Line",
        "Several series on one set of axes.",
        "g1.line",
        True,
    ),
    _c(
        "graph name.type",
        "graph",
        "Freeze a graph view",
        "Create a graph as a named object, so you can retitle, recolour and keep it.",
        "graph gr1.line y",
        True,
    ),
    _c(
        "gr.addtext",
        "graph",
        "Right-click a graph > Add text",
        "Put a title or annotation on a graph object.",
        'gr1.addtext(t) "Real GDP growth"',
    ),
    _c(
        "gr.setelem",
        "graph",
        "Graph Options > Line/Symbol",
        "Change the colour, width or symbol of one plotted line.",
        "gr1.setelem(1) lcolor(blue) lwidth(2)",
    ),
    _c(
        "gr.merge",
        "graph",
        "Select graphs > Merge into one",
        "Combine several graph objects into a single figure.",
        "graph gr3.merge gr1 gr2",
    ),
    # ------------------------------------------------------------------- stats
    _c(
        "x.stats",
        "stats",
        "Series > View > Descriptive Statistics > Stats Table",
        "Mean, median, min, max, standard deviation, skewness, kurtosis and the "
        "Jarque-Bera normality test.",
        "x.stats",
        True,
    ),
    _c(
        "g.stats",
        "stats",
        "Group > View > Descriptive Statistics",
        "The same table for every series in a group, side by side.",
        "g1.stats",
        True,
    ),
    _c(
        "g.cor / g.cov",
        "stats",
        "Group > View > Covariance Analysis",
        "Correlation or covariance matrix.",
        "g1.cor",
        True,
    ),
    _c(
        "x.correl",
        "stats",
        "Series > View > Correlogram",
        "Autocorrelation and partial autocorrelation functions with Q-statistics "
        "— how you choose ARMA lags.",
        "x.correl",
        True,
    ),
    _c(
        "x.freq",
        "stats",
        "Series > View > One-Way Tabulation",
        "Frequency table — counts of each value.",
        "x.freq",
    ),
    _c(
        "x.teststat",
        "stats",
        "Series > View > Simple Hypothesis Tests",
        "Test a hypothesis about the mean, median or variance of one series.",
        "x.teststat(mean=0)",
    ),
    _c(
        "x.bdstest",
        "stats",
        "Series > View > BDS Independence Test",
        "BDS test for independence — used to detect nonlinear structure.",
        "x.bdstest",
        True,
    ),
    _c(
        "g.cause",
        "stats",
        "Group > View > Granger Causality",
        "Granger causality tests between the group's members, at the lag you give.",
        "g1.cause(4)",
        True,
    ),
    # ---------------------------------------------------------------- unitroot
    _c(
        "x.uroot(adf)",
        "unitroot",
        "Series > View > Unit Root Test > ADF",
        "Augmented Dickey-Fuller test. The null is a unit root, so a small "
        "p-value means stationary.",
        "x.uroot(adf)",
        True,
    ),
    _c(
        "x.uroot(pp)",
        "unitroot",
        "Series > View > Unit Root Test > Phillips-Perron",
        "Phillips-Perron test — ADF's non-parametric cousin, robust to serial "
        "correlation and heteroskedasticity.",
        "x.uroot(pp)",
        True,
    ),
    _c(
        "x.uroot(kpss)",
        "unitroot",
        "Series > View > Unit Root Test > KPSS",
        "KPSS test. The null is reversed — stationarity — so a small p-value means a unit root.",
        "x.uroot(kpss)",
        True,
    ),
    _c(
        "x.uroot(dfgls)",
        "unitroot",
        "Series > View > Unit Root Test > DF-GLS",
        "Elliott-Rothenberg-Stock test, more powerful than ADF in small samples.",
        "x.uroot(dfgls)",
    ),
    _c(
        "x.uroot(adf, dif=1)",
        "unitroot",
        "Unit Root dialog > 1st difference",
        "Run the test on first differences, to establish the order of integration.",
        "x.uroot(adf, dif=1)",
    ),
    _c(
        "x.uroot(breakls)",
        "unitroot",
        "Series > View > Unit Root Test with Break",
        "Unit root test allowing one structural break.",
        "x.uroot(breakls)",
    ),
    # ------------------------------------------------------------------- coint
    _c(
        "g.coint(e)",
        "coint",
        "Group > View > Cointegration Test > Johansen",
        "Johansen system cointegration test — trace and maximum-eigenvalue "
        "statistics for how many cointegrating relations exist.",
        "g1.coint(e)",
        True,
    ),
    _c(
        "g.coint(eg)",
        "coint",
        "Group > View > Cointegration Test > Engle-Granger",
        "Engle-Granger single-equation cointegration test.",
        "g1.coint(eg)",
    ),
    _c(
        "g.coint(po)",
        "coint",
        "Group > View > Cointegration Test > Phillips-Ouliaris",
        "Phillips-Ouliaris residual-based cointegration test.",
        "g1.coint(po)",
    ),
    # ---------------------------------------------------------------- estimate
    _c(
        "equation eq.ls",
        "estimate",
        "Quick > Estimate Equation > LS",
        "Ordinary least squares. 'c' in the list is the constant. This is the "
        "command you will type most often.",
        "equation eq1.ls y c x z",
        True,
    ),
    _c(
        "equation eq.ls(cov=white)",
        "estimate",
        "Estimate dialog > Options > White",
        "OLS with heteroskedasticity-robust (White) standard errors.",
        "equation eq1.ls(cov=white) y c x",
    ),
    _c(
        "equation eq.ls(cov=hac)",
        "estimate",
        "Estimate dialog > Options > HAC",
        "OLS with Newey-West standard errors, robust to serial correlation too.",
        "equation eq1.ls(cov=hac) y c x",
    ),
    _c(
        "equation eq.tsls",
        "estimate",
        "Quick > Estimate Equation > TSLS",
        "Two-stage least squares for endogenous regressors. The @ separates the "
        "equation from the instruments, which must include c if the equation has one.",
        "equation eq2.tsls y c x @ z c",
        True,
    ),
    _c(
        "equation eq.gmm",
        "estimate",
        "Quick > Estimate Equation > GMM",
        "Generalised method of moments.",
        "equation eq3.gmm y c x @ z c",
        True,
    ),
    _c(
        "equation eq.ls (nonlinear)",
        "estimate",
        "Quick > Estimate Equation, type a formula",
        "Nonlinear least squares — write the equation with c(1), c(2) as the "
        "parameters to estimate.",
        "equation eq4.ls y = c(1) + c(2)*x^c(3)",
        True,
    ),
    _c(
        "ar(1) ma(1)",
        "estimate",
        "Estimate dialog, add AR/MA terms",
        "ARMA errors: add ar(p) and ma(q) terms to an LS specification.",
        "equation eq5.ls y c ar(1) ma(1)",
        True,
    ),
    _c(
        "equation eq.ardl",
        "estimate",
        "Quick > Estimate Equation > ARDL",
        "Autoregressive distributed lag, with automatic lag selection — the usual "
        "route to a bounds test for level relationships.",
        "equation eq6.ardl y x",
        True,
    ),
    _c(
        "equation eq.arch",
        "estimate",
        "Quick > Estimate Equation > ARCH",
        "GARCH family. arch(1,1) is the standard GARCH(1,1).",
        "equation eq7.arch(1,1) y c x",
        True,
    ),
    _c(
        "arch(1,1,thrsh=1)",
        "estimate",
        "ARCH dialog > Threshold order 1",
        "Threshold GARCH (GJR) — lets bad news move volatility more than good news.",
        "equation eq7.arch(1,1,thrsh=1) y c x",
        True,
    ),
    _c(
        "arch(1,1,egarch)",
        "estimate",
        "ARCH dialog > Model: EGARCH",
        "Exponential GARCH — log variance, so no non-negativity constraints.",
        "equation eq7.arch(1,1,egarch) y c x",
        True,
    ),
    _c(
        "equation eq.binary(d=l)",
        "estimate",
        "Quick > Estimate Equation > BINARY, Logit",
        "Logit for a 0/1 dependent variable.",
        "equation eq8.binary(d=l) ybin c x",
        True,
    ),
    _c(
        "equation eq.binary(d=n)",
        "estimate",
        "Quick > Estimate Equation > BINARY, Probit",
        "Probit for a 0/1 dependent variable.",
        "equation eq8.binary(d=n) ybin c x",
        True,
    ),
    _c(
        "equation eq.qreg",
        "estimate",
        "Quick > Estimate Equation > QREG",
        "Quantile regression. quant=0.5 is the median; vary it to see how the "
        "relationship changes across the distribution.",
        "equation eq9.qreg(quant=0.5) y c x",
        True,
    ),
    _c(
        "equation eq.count",
        "estimate",
        "Quick > Estimate Equation > COUNT",
        "Poisson and negative binomial models for count data.",
        "equation eq11.count(d=p) ycount c x",
    ),
    _c(
        "equation eq.stepls",
        "estimate",
        "Quick > Estimate Equation > STEPLS",
        "Stepwise selection of regressors from a candidate list after the @.",
        "equation eq10.stepls(method=stepwise) y c @ x z",
        True,
    ),
    _c(
        "var v.ls",
        "estimate",
        "Quick > Estimate VAR",
        "Unrestricted VAR. The two numbers are the first and last lag.",
        "var v1.ls 1 2 x y",
        True,
    ),
    _c(
        "var v.ec",
        "estimate",
        "Quick > Estimate VAR > Vector Error Correction",
        "VEC model for cointegrated series. ec(c,1) means a constant and one "
        "cointegrating relation.",
        "var v2.ec(c,1) 1 2 x y",
        True,
    ),
    _c(
        "system s.append",
        "estimate",
        "Object > New Object > System",
        "Build a system of equations, then estimate it jointly.",
        "system s1.append y = c(1) + c(2)*x",
        True,
    ),
    # ----------------------------------------------------------------- results
    _c(
        "eq.output",
        "results",
        "Equation > View > Estimation Output",
        "The estimation table — coefficients, standard errors, t-statistics, "
        "R-squared, information criteria.",
        "eq1.output",
        True,
    ),
    _c(
        "eq.representations",
        "results",
        "Equation > View > Representations",
        "The equation written out three ways, including the substituted-coefficient "
        "form you can paste into a paper.",
        "eq1.representations",
        True,
    ),
    _c(
        "eq.coefcov",
        "results",
        "Equation > View > Coefficient Covariance Matrix",
        "The estimated variance-covariance matrix of the coefficients.",
        "eq1.coefcov",
        True,
    ),
    _c(
        "eq.resids",
        "results",
        "Equation > View > Actual, Fitted, Residual > Graph",
        "The three-line plot of actual, fitted and residual — the first thing to "
        "look at after estimating.",
        "eq1.resids",
        True,
    ),
    _c(
        "eq.hist",
        "results",
        "Equation > View > Residual Diagnostics > Histogram",
        "Residual histogram with the Jarque-Bera normality test.",
        "eq1.hist",
        True,
    ),
    _c(
        "eq.correl",
        "results",
        "Equation > View > Residual Diagnostics > Correlogram",
        "Correlogram of the residuals — checks for leftover serial correlation.",
        "eq1.correl",
        True,
    ),
    _c(
        "eq.correlsq",
        "results",
        "Residual Diagnostics > Correlogram Squared Residuals",
        "Correlogram of squared residuals — checks for ARCH effects.",
        "eq1.correlsq",
        True,
    ),
    _c(
        "eq.@r2 and friends",
        "results",
        "read it off the output table",
        "Pull a single number into a scalar you can then send to Python: @r2, "
        "@rbar2, @aic, @schwarz, @dw, @f, @logl, @coefs(i), @stderrs(i), @tstats(i).",
        "scalar r2 = eq1.@r2",
        True,
    ),
    _c(
        "eq.makeresid",
        "results",
        "Equation > Proc > Make Residual Series",
        "Save the residuals as a series you can plot or test.",
        "eq1.makeresid res1",
        True,
    ),
    # -------------------------------------------------------------------- test
    _c(
        "eq.wald",
        "test",
        "Equation > View > Coefficient Diagnostics > Wald Test",
        "Test a linear restriction on the coefficients.",
        "eq1.wald c(2)=0",
        True,
    ),
    _c(
        "eq.testadd",
        "test",
        "Coefficient Diagnostics > Omitted Variables",
        "Would adding these variables improve the equation?",
        "eq1.testadd w",
        True,
    ),
    _c(
        "eq.testdrop",
        "test",
        "Coefficient Diagnostics > Redundant Variables",
        "Can these variables be dropped without loss?",
        "eq1.testdrop z",
        True,
    ),
    _c(
        "eq.varinf",
        "test",
        "Coefficient Diagnostics > Variance Inflation Factors",
        "VIFs — how much multicollinearity is inflating each standard error.",
        "eq1.varinf",
        True,
    ),
    _c(
        "eq.auto",
        "test",
        "Residual Diagnostics > Serial Correlation LM Test",
        "Breusch-Godfrey test for serial correlation up to the lag you give.",
        "eq1.auto(2)",
        True,
    ),
    _c(
        "eq.white",
        "test",
        "Residual Diagnostics > Heteroskedasticity > White",
        "White's test for heteroskedasticity.",
        "eq1.white",
        True,
    ),
    _c(
        "eq.hettest",
        "test",
        "Residual Diagnostics > Heteroskedasticity > Breusch-Pagan",
        "Breusch-Pagan-Godfrey test. You must name the regressors to test "
        "against — on its own it is refused.",
        "eq1.hettest w",
        True,
    ),
    _c(
        "eq.archtest",
        "test",
        "Residual Diagnostics > Heteroskedasticity > ARCH",
        "ARCH LM test for volatility clustering in the residuals.",
        "eq1.archtest(1)",
        True,
    ),
    _c(
        "eq.reset",
        "test",
        "Stability Diagnostics > Ramsey RESET Test",
        "Ramsey RESET — is the functional form wrong?",
        "eq1.reset(1)",
        True,
    ),
    _c(
        "eq.chow",
        "test",
        "Stability Diagnostics > Chow Breakpoint Test",
        "Chow test for a structural break at a date you name.",
        "eq1.chow 2000Q1",
        True,
    ),
    _c(
        "eq.rls(c)",
        "test",
        "Stability Diagnostics > Recursive Estimates > Coefficients",
        "Recursive coefficient estimates — watch each coefficient as the sample grows.",
        "eq1.rls(c)",
        True,
    ),
    _c(
        "eq.rls(r)",
        "test",
        "Stability Diagnostics > Recursive Estimates > Residuals",
        "Recursive residuals with two-standard-error bands.",
        "eq1.rls(r)",
        True,
    ),
    _c(
        "eq.rls(o)",
        "test",
        "Recursive Estimates > One-Step Forecast Test",
        "One-step-ahead forecast test for parameter stability.",
        "eq1.rls(o)",
        True,
    ),
    _c(
        "eq.rls(n)",
        "test",
        "Recursive Estimates > N-Step Forecast Test",
        "N-step-ahead forecast test.",
        "eq1.rls(n)",
        True,
    ),
    _c(
        "eq.rls(q)",
        "test",
        "Stability Diagnostics > Recursive Estimates > CUSUM Test",
        "CUSUM test — the standardised cumulative sum of recursive residuals, "
        "with 5% critical lines. If the line leaves the band, the coefficients "
        "are not stable over the sample.",
        "eq1.rls(q)",
        True,
    ),
    _c(
        "eq.rls(v)",
        "test",
        "Stability Diagnostics > Recursive Estimates > CUSUM of Squares Test",
        "CUSUM of squares test, with 5% critical lines. More sensitive than "
        "CUSUM to a sudden change in variance rather than in the coefficients.",
        "eq1.rls(v)",
        True,
    ),
    _c(
        "eq.rls(r,s)",
        "test",
        "Recursive Estimates dialog, tick the save box",
        "Add s to any recursive option to also save the results as series. "
        "Name the series after the command: here the recursive residuals and "
        "their standard errors. s is a modifier, never an option on its own.",
        "eq1.rls(r,s) r_res r_resse",
        True,
    ),
    # ---------------------------------------------------------------- forecast
    _c(
        "eq.forecast",
        "forecast",
        "Equation window > Forecast button",
        "Produce forecasts into a new series, over the current sample. Set the "
        "sample wider than the estimation sample first.",
        "eq1.forecast yf",
        True,
    ),
    _c(
        "eq.forecast(g)",
        "forecast",
        "Forecast dialog > Forecast graph",
        "Forecast and show the plot. EViews' own forecast window cannot be "
        "exported, so EconEnv rebuilds it as forecast +/- 2 standard errors.",
        "eq1.forecast(g) yf",
        True,
    ),
    _c(
        "eq.forecast(e)",
        "forecast",
        "Forecast dialog > S.E. series",
        "Also write the forecast standard errors to a second series.",
        "eq1.forecast(e) yf yf_se",
        True,
    ),
    _c(
        "eq.forecast(s)",
        "forecast",
        "Forecast dialog > Static",
        "Static (one-step-ahead) forecasts using actual lagged values, rather "
        "than dynamic forecasts that feed on their own predictions.",
        "eq1.forecast(s) yf",
    ),
    _c(
        "eq.fit",
        "forecast",
        "Equation > Proc > Forecast (in sample)",
        "Fitted values over the estimation sample.",
        "eq1.fit yfit",
        True,
    ),
    # ----------------------------------------------------------------- var
    _c(
        "v.output",
        "var",
        "VAR > View > Estimation Output",
        "The full VAR coefficient table.",
        "v1.output",
        True,
    ),
    _c(
        "v.impulse",
        "var",
        "VAR > View > Impulse Response",
        "Impulse response functions — how each variable reacts to a shock.",
        "v1.impulse",
        True,
    ),
    _c(
        "v.impulse(imp=chol)",
        "var",
        "Impulse dialog > Cholesky decomposition",
        "Impulse responses with Cholesky orthogonalisation. Ordering matters.",
        "v1.impulse(imp=chol)",
        True,
    ),
    _c(
        "v.decomp",
        "var",
        "VAR > View > Variance Decomposition",
        "How much of each variable's forecast error variance each shock explains.",
        "v1.decomp",
        True,
    ),
    _c(
        "v.arroots",
        "var",
        "VAR > View > Lag Structure > AR Roots Table",
        "Roots of the characteristic polynomial — all inside the unit circle means a stable VAR.",
        "v1.arroots",
        True,
    ),
    _c(
        "v.correl",
        "var",
        "VAR > View > Residual Diagnostics > Correlograms",
        "Residual correlograms for the system.",
        "v1.correl",
        True,
    ),
    _c(
        "v.laglen",
        "var",
        "VAR > View > Lag Structure > Lag Length Criteria",
        "AIC, SC and HQ across lag lengths, to choose the VAR order.",
        "v1.laglen(8)",
    ),
    _c(
        "v.testexog",
        "var",
        "Lag Structure > Granger Causality/Block Exogeneity",
        "Block exogeneity Wald tests within the VAR.",
        "v1.testexog",
    ),
    # ------------------------------------------------------------------- panel
    _c(
        "pagestruct id date",
        "panel",
        "Proc > Structure/Resize > Panel",
        "Turn the page into a panel by naming the cross-section and date variables. "
        "Nothing panel-specific works until you do this.",
        "pagestruct id date",
    ),
    _c(
        "equation p.ls(cx=f)",
        "panel",
        "Estimate dialog > Panel Options > Fixed",
        "Cross-section fixed effects.",
        "equation p2.ls(cx=f) y c x",
    ),
    _c(
        "equation p.ls(cx=r)",
        "panel",
        "Estimate dialog > Panel Options > Random",
        "Cross-section random effects.",
        "equation p3.ls(cx=r) y c x",
    ),
    _c(
        "equation p.ls(cx=f, per=f)",
        "panel",
        "Panel Options > both Fixed",
        "Two-way fixed effects, entity and period.",
        "equation p4.ls(cx=f, per=f) y c x",
    ),
    _c(
        "p.fixedtest",
        "panel",
        "Equation > View > Fixed/Random Effects Testing",
        "Hausman test for fixed versus random effects.",
        "p3.fixedtest",
    ),
    _c(
        "x.uroot(sum)",
        "panel",
        "Series > View > Unit Root Test (panel)",
        "Panel unit root tests — Levin-Lin-Chu, Im-Pesaran-Shin and others.",
        "x.uroot(sum)",
    ),
    _c(
        "equation p.gmm(cx=fd)",
        "panel",
        "Quick > Estimate Equation > GMM, panel",
        "Arellano-Bond style dynamic panel GMM in first differences.",
        "equation p6.gmm(cx=fd, gmm=perwhite) y c y(-1) x @ y(-2)",
    ),
    # ----------------------------------------------------------------- program
    _c(
        "scalar",
        "program",
        "Object > New Object > Scalar",
        "A single number. The bridge for getting one value out to Python.",
        "scalar s1 = 3.14",
        True,
    ),
    _c(
        "matrix / vector",
        "program",
        "Object > New Object > Matrix",
        "Matrix and vector objects.",
        "matrix(3,3) m1",
    ),
    _c(
        "stom / mtos",
        "program",
        "Proc > Make Vector/Matrix",
        "Convert a series to a vector, or a vector back to a series.",
        "stom(x, vx)",
    ),
    _c(
        "for ... next",
        "program",
        "no GUI equivalent",
        "Loop. !i is a numeric control variable, %v a string one, and {...} "
        "substitutes the value into the command.",
        "for !i = 1 to 4\n  series lag{!i} = y(-!i)\nnext",
    ),
    _c(
        "if ... then ... endif",
        "program",
        "no GUI equivalent",
        "Conditional execution inside a cell.",
        "if @obs(y) > 100 then\n  equation eq1.ls y c x\nendif",
    ),
    _c(
        "help",
        "program",
        "Help menu",
        "Open EViews' own help page for a command — the fastest way to find "
        "options this catalogue does not list.",
        "help ls",
    ),
)


def categories() -> Dict[str, str]:
    """Category name to one-line description."""
    return dict(CATEGORIES)


def by_category(category: str) -> List[Command]:
    """Every command in one category."""
    key = category.strip().lower()
    return [c for c in COMMANDS if c.category == key]


def search(term: str) -> List[Command]:
    """Commands matching *term* anywhere — name, description, GUI path or example.

    Ranked so that a hit in the command name beats a hit in the prose, because
    someone typing ``find garch`` wants the GARCH command first, not every
    entry that mentions volatility.
    """
    needle = term.strip().lower()
    if not needle:
        return []
    scored: List[tuple] = []
    for command in COMMANDS:
        haystacks = (
            (command.command.lower(), 0),
            (command.gui.lower(), 1),
            (command.does.lower(), 2),
            (command.example.lower(), 3),
        )
        for text, rank in haystacks:
            if needle in text:
                scored.append((rank, command))
                break
    scored.sort(key=lambda pair: pair[0])
    return [command for _, command in scored]


def find(term: Optional[str] = None) -> List[Command]:
    """Search, or list a category, or return everything — whichever fits *term*."""
    if not term:
        return list(COMMANDS)
    key = term.strip().lower()
    if key in CATEGORIES:
        return by_category(key)
    return search(key)
