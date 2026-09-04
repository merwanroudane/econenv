# EViews commands for people who use the GUI

In EViews you click. In a notebook there is nothing to click, and that is the
only real obstacle to using EconEnv: you already know *what* you want to do,
just not how to type it.

This page is the translation. Every entry gives the menu path you already know,
the command it becomes, what it does in plain language, and a line you can copy.

**You do not have to read it.** Look things up from inside the notebook
instead, while you are writing the cell:

```python
%econ eviews                      # the list of tasks
%econ eviews graph                # everything about plotting
%econ eviews find cointegration   # search all of it
```

Same content, no browser, no context switch.

## The one idea that makes EViews commands guessable

EViews objects work like this:

```
object_name.what_you_want
```

`eq1.output` shows an equation's results. `x.line` plots a series. `v1.impulse`
draws impulse responses. So:

- Anything in an object's **View** menu is `object.thatview`.
- Anything in its **Proc** menu is `object.thatproc`, usually followed by a
  name for whatever it creates.

That single rule covers most of this page. Once you see it, you can often guess
a command you have never used.

Three more conventions:

- `c` in a regressor list means **the constant** — not a variable called c.
- Options go in parentheses right after the command: `ls(cov=white) y c x`.
- `x`, `y`, `z` are series; `eq1` an equation; `g1` a group; `v1` a VAR.

## A first cell, annotated

```python
%%eviews
wfcreate q 1990Q1 2020Q4      ' a quarterly workfile, 1990Q1 to 2020Q4
series x = nrnd               ' a random series, to have something to look at
series y = 5 + 2*x + nrnd     ' y depends on x
equation eq1.ls y c x         ' regress y on a constant and x
eq1.output                    ' show the results table
line y                        ' plot y
```

Six lines, and you have a workfile, data, a regression, its output and a chart.
In the GUI that is about twenty clicks across five dialogs.

A `'` starts a comment in EViews, exactly like `#` in Python.

## Three ways to draw the same plot

This trips people up, because the GUI hides the distinction. All three work:

```python
%%eviews
line x            ' command form  - quickest
x.line            ' view form     - matches the View menu
graph gr1.line x  ' object form   - keeps the graph so you can edit it
```

Use the object form when you want to add a title or change colours afterwards.
Otherwise use whichever you find easier to remember.

## What a check mark means

An entry marked **✓** was run against EViews 13 through EconEnv while this page
was generated, and it worked. Unmarked entries are EViews' documented syntax
that this machine could not exercise — nearly all of them panel commands, which
need a panel-structured workfile.

---

## Contents

- [Creating, opening and structuring workfiles and pages](#creating-opening-and-structuring-workfiles-and-pages) — `%econ eviews workfile`
- [Getting data in and out of EViews](#getting-data-in-and-out-of-eviews) — `%econ eviews data`
- [Creating and transforming series](#creating-and-transforming-series) — `%econ eviews series`
- [Choosing which observations to use](#choosing-which-observations-to-use) — `%econ eviews sample`
- [Working with several series at once](#working-with-several-series-at-once) — `%econ eviews group`
- [Every kind of plot, before and after estimation](#every-kind-of-plot-before-and-after-estimation) — `%econ eviews graph`
- [Descriptive statistics and simple tests](#descriptive-statistics-and-simple-tests) — `%econ eviews stats`
- [Unit root and stationarity testing](#unit-root-and-stationarity-testing) — `%econ eviews unitroot`
- [Cointegration testing](#cointegration-testing) — `%econ eviews coint`
- [Estimating equations, systems and VARs](#estimating-equations-systems-and-vars) — `%econ eviews estimate`
- [Reading what an estimation produced](#reading-what-an-estimation-produced) — `%econ eviews results`
- [Diagnostic and specification tests after estimation](#diagnostic-and-specification-tests-after-estimation) — `%econ eviews test`
- [Forecasting and fitted values](#forecasting-and-fitted-values) — `%econ eviews forecast`
- [VAR and VEC output](#var-and-vec-output) — `%econ eviews var`
- [Panel data](#panel-data) — `%econ eviews panel`
- [Scalars, matrices, loops and control](#scalars-matrices-loops-and-control) — `%econ eviews program`


## Creating, opening and structuring workfiles and pages

Look these up from a cell with `%econ eviews workfile`.

| You would click | Command | What it does | |
|---|---|---|---|
| File > New > Workfile | `wfcreate q 1990Q1 2020Q4` | Create a new workfile. The frequency letter comes first, then the start and end of the range: a annual, q quarterly, m monthly, d daily, u undated. | ✓ |
| File > New > Workfile, with a name | `wfcreate(wf=mydata) q 1990Q1 2020Q4` | Same, but names the workfile so you can refer to it later. | ✓ |
| File > Open > EViews Workfile | `wfopen "C:\work\mydata.wf1"` | Open a workfile that already exists on disk. |  |
| File > Save As | `wfsave "C:\work\mydata.wf1"` | Save the current workfile to disk. |  |
| Workfile window > New Page | `pagecreate(page=annual) a 1990 2020` | Add another page, which can hold a different frequency from the first. |  |
| Click a page tab | `pageselect annual` | Switch to another page. Everything after this line acts on that page. | ✓ |
| Proc > Structure/Resize Current Page | `pagestruct(freq=q, start=1990Q1)` | Change how the page is structured — give it a date, or turn it into a panel. |  |
| Proc > Copy/Extract from Current Page | `pagecopy(page=annual, freq=a, smpl=@all)` | Copy the page, optionally converting it to another frequency. |  |
| Right-click a page tab | `pagerename old new` | Rename or delete a page. |  |


## Getting data in and out of EViews

Look these up from a cell with `%econ eviews data`.

| You would click | Command | What it does | |
|---|---|---|---|
| File > Import > Import from file | `import "C:\data\file.xlsx" range="Sheet1!A1"` | Read a spreadsheet or text file into the current page. |  |
| Proc > Export > Write to file | `g1.write(t=csv) "out.csv"` | Write a group out to CSV or Excel. |  |
| no GUI equivalent | `%%eviews -i df` | Push a pandas DataFrame straight from Python into a new workfile. This is what EconEnv exists for — you do not need to save a CSV first. | ✓ |
| no GUI equivalent | `econenv.pull("eviews", "y")` | Bring the page, or one series, back into Python as a DataFrame. | ✓ |


## Creating and transforming series

Look these up from a cell with `%econ eviews series`.

| You would click | Command | What it does | |
|---|---|---|---|
| Object > New Object > Series, or Quick > Generate Series | `series lny = log(y)` | Create a new series from an expression. This is the workhorse: almost every variable you build starts with this word. | ✓ |
| type it in Generate Series | `series dy = d(y)` | First difference, x - x(-1). d(x,2) is the second difference. | ✓ |
| type it in Generate Series | `series g = dlog(y)` | Log difference — the usual growth-rate transform for a level series. | ✓ |
| type it in Generate Series | `series ylag = y(-1)` | Lag. x(-1) is one period back, x(+1) one period forward. | ✓ |
| type it in Generate Series | `series pc = @pch(y)` | Percent change from the previous period. |  |
| type it in Generate Series | `series big = @recode(x>2, 1, 0)` | Conditional value — the equivalent of an if/else. Use it to build dummies. | ✓ |
| type it in Generate Series | `series t = @trend` | A linear time trend, 0, 1, 2, ... | ✓ |
| type it in Generate Series | `series q2 = @seas(2)` | Seasonal dummy: 1 in season n, 0 otherwise. |  |
| type it in Generate Series | `series ma4 = @movav(y,4)` | n-period moving average. |  |
| type it in Generate Series | `series e = nrnd` | Random draws: nrnd is standard normal, rnd is uniform on (0,1). Useful for testing a workflow before your real data arrives. | ✓ |
| Right-click an object | `delete x` | Rename or delete any object — a series, an equation, a graph. | ✓ |


## Choosing which observations to use

Look these up from a cell with `%econ eviews sample`.

| You would click | Command | What it does | |
|---|---|---|---|
| Sample button, or Quick > Sample | `smpl 1995Q1 2015Q4` | Set which observations everything after this line will use. The single most common cause of results that do not match: forgetting to reset it. | ✓ |
| Sample button > @all | `smpl @all` | Use every observation again. | ✓ |
| Sample dialog, condition box | `smpl @all if x>0` | Restrict to observations satisfying a condition. |  |
| Object > New Object > Sample | `sample s1 1995Q1 2015Q4` | Save a named sample you can switch back to later. |  |


## Working with several series at once

Look these up from a cell with `%econ eviews group`.

| You would click | Command | What it does | |
|---|---|---|---|
| Select several series > Open as Group | `group g1 x y z` | Bundle series together so you can plot or test them jointly. Many multi-series views only exist on a group. | ✓ |
| Group window > Add/Drop | `g1.add w` | Change which series a group contains. |  |


## Every kind of plot, before and after estimation

Look these up from a cell with `%econ eviews graph`.

| You would click | Command | What it does | |
|---|---|---|---|
| Series > View > Graph > Line | `line x` | Line plot. Three forms all work: 'line x' as a command, 'x.line' as a view, or 'graph g1.line x' to keep the graph as an object you can edit. | ✓ |
| Series > View > Graph > Bar | `bar x` | Bar chart. | ✓ |
| Series > View > Graph > Area | `area x` | Filled area plot. | ✓ |
| Series > View > Graph > Spike | `spike x` | Spike plot — good for sparse or event data. | ✓ |
| Series > View > Graph > Dot Plot | `x.dot` | Dot plot. | ✓ |
| Series > View > Graph > Seasonal Plot | `x.seasplot` | Plots each season's path separately, so seasonality is visible by eye. | ✓ |
| Series > View > Descriptive Statistics > Histogram | `x.hist` | Histogram of one series. | ✓ |
| Series > View > Graph > Distribution | `x.distplot` | Kernel density — a smoothed histogram. | ✓ |
| Series > View > Graph > Boxplot | `x.boxplot` | Boxplot: median, quartiles and outliers. | ✓ |
| Series > View > Graph > Quantile-Quantile | `x.qqplot` | Q-Q plot against the normal — a quick normality check by eye. | ✓ |
| Group > View > Graph > Scatter | `scat x y` | Scatter plot of two series. Add (r) for a fitted regression line. | ✓ |
| Group > View > Graph > XY Line | `xyline x y` | Plots one series against another, joined in order. | ✓ |
| Group > View > Graph > Scatterplot Matrix | `g1.scatmat` | All pairwise scatters in one grid — a fast look at a whole dataset. | ✓ |
| Group > View > Graph > Line | `g1.line` | Several series on one set of axes. | ✓ |
| Freeze a graph view | `graph gr1.line y` | Create a graph as a named object, so you can retitle, recolour and keep it. | ✓ |
| Right-click a graph > Add text | `gr1.addtext(t) "Real GDP growth"` | Put a title or annotation on a graph object. |  |
| Graph Options > Line/Symbol | `gr1.setelem(1) lcolor(blue) lwidth(2)` | Change the colour, width or symbol of one plotted line. |  |
| Select graphs > Merge into one | `graph gr3.merge gr1 gr2` | Combine several graph objects into a single figure. |  |


## Descriptive statistics and simple tests

Look these up from a cell with `%econ eviews stats`.

| You would click | Command | What it does | |
|---|---|---|---|
| Series > View > Descriptive Statistics > Stats Table | `x.stats` | Mean, median, min, max, standard deviation, skewness, kurtosis and the Jarque-Bera normality test. | ✓ |
| Group > View > Descriptive Statistics | `g1.stats` | The same table for every series in a group, side by side. | ✓ |
| Group > View > Covariance Analysis | `g1.cor` | Correlation or covariance matrix. | ✓ |
| Series > View > Correlogram | `x.correl` | Autocorrelation and partial autocorrelation functions with Q-statistics — how you choose ARMA lags. | ✓ |
| Series > View > One-Way Tabulation | `x.freq` | Frequency table — counts of each value. |  |
| Series > View > Simple Hypothesis Tests | `x.teststat(mean=0)` | Test a hypothesis about the mean, median or variance of one series. |  |
| Series > View > BDS Independence Test | `x.bdstest` | BDS test for independence — used to detect nonlinear structure. | ✓ |
| Group > View > Granger Causality | `g1.cause(4)` | Granger causality tests between the group's members, at the lag you give. | ✓ |


## Unit root and stationarity testing

Look these up from a cell with `%econ eviews unitroot`.

| You would click | Command | What it does | |
|---|---|---|---|
| Series > View > Unit Root Test > ADF | `x.uroot(adf)` | Augmented Dickey-Fuller test. The null is a unit root, so a small p-value means stationary. | ✓ |
| Series > View > Unit Root Test > Phillips-Perron | `x.uroot(pp)` | Phillips-Perron test — ADF's non-parametric cousin, robust to serial correlation and heteroskedasticity. | ✓ |
| Series > View > Unit Root Test > KPSS | `x.uroot(kpss)` | KPSS test. The null is reversed — stationarity — so a small p-value means a unit root. | ✓ |
| Series > View > Unit Root Test > DF-GLS | `x.uroot(dfgls)` | Elliott-Rothenberg-Stock test, more powerful than ADF in small samples. |  |
| Unit Root dialog > 1st difference | `x.uroot(adf, dif=1)` | Run the test on first differences, to establish the order of integration. |  |
| Series > View > Unit Root Test with Break | `x.uroot(breakls)` | Unit root test allowing one structural break. |  |


## Cointegration testing

Look these up from a cell with `%econ eviews coint`.

| You would click | Command | What it does | |
|---|---|---|---|
| Group > View > Cointegration Test > Johansen | `g1.coint(e)` | Johansen system cointegration test — trace and maximum-eigenvalue statistics for how many cointegrating relations exist. | ✓ |
| Group > View > Cointegration Test > Engle-Granger | `g1.coint(eg)` | Engle-Granger single-equation cointegration test. |  |
| Group > View > Cointegration Test > Phillips-Ouliaris | `g1.coint(po)` | Phillips-Ouliaris residual-based cointegration test. |  |


## Estimating equations, systems and VARs

Look these up from a cell with `%econ eviews estimate`.

| You would click | Command | What it does | |
|---|---|---|---|
| Quick > Estimate Equation > LS | `equation eq1.ls y c x z` | Ordinary least squares. 'c' in the list is the constant. This is the command you will type most often. | ✓ |
| Estimate dialog > Options > White | `equation eq1.ls(cov=white) y c x` | OLS with heteroskedasticity-robust (White) standard errors. |  |
| Estimate dialog > Options > HAC | `equation eq1.ls(cov=hac) y c x` | OLS with Newey-West standard errors, robust to serial correlation too. |  |
| Quick > Estimate Equation > TSLS | `equation eq2.tsls y c x @ z c` | Two-stage least squares for endogenous regressors. The @ separates the equation from the instruments, which must include c if the equation has one. | ✓ |
| Quick > Estimate Equation > GMM | `equation eq3.gmm y c x @ z c` | Generalised method of moments. | ✓ |
| Quick > Estimate Equation, type a formula | `equation eq4.ls y = c(1) + c(2)*x^c(3)` | Nonlinear least squares — write the equation with c(1), c(2) as the parameters to estimate. | ✓ |
| Estimate dialog, add AR/MA terms | `equation eq5.ls y c ar(1) ma(1)` | ARMA errors: add ar(p) and ma(q) terms to an LS specification. | ✓ |
| Quick > Estimate Equation > ARDL | `equation eq6.ardl y x` | Autoregressive distributed lag, with automatic lag selection — the usual route to a bounds test for level relationships. | ✓ |
| Quick > Estimate Equation > ARCH | `equation eq7.arch(1,1) y c x` | GARCH family. arch(1,1) is the standard GARCH(1,1). | ✓ |
| ARCH dialog > Threshold order 1 | `equation eq7.arch(1,1,thrsh=1) y c x` | Threshold GARCH (GJR) — lets bad news move volatility more than good news. | ✓ |
| ARCH dialog > Model: EGARCH | `equation eq7.arch(1,1,egarch) y c x` | Exponential GARCH — log variance, so no non-negativity constraints. | ✓ |
| Quick > Estimate Equation > BINARY, Logit | `equation eq8.binary(d=l) ybin c x` | Logit for a 0/1 dependent variable. | ✓ |
| Quick > Estimate Equation > BINARY, Probit | `equation eq8.binary(d=n) ybin c x` | Probit for a 0/1 dependent variable. | ✓ |
| Quick > Estimate Equation > QREG | `equation eq9.qreg(quant=0.5) y c x` | Quantile regression. quant=0.5 is the median; vary it to see how the relationship changes across the distribution. | ✓ |
| Quick > Estimate Equation > COUNT | `equation eq11.count(d=p) ycount c x` | Poisson and negative binomial models for count data. |  |
| Quick > Estimate Equation > STEPLS | `equation eq10.stepls(method=stepwise) y c @ x z` | Stepwise selection of regressors from a candidate list after the @. | ✓ |
| Quick > Estimate VAR | `var v1.ls 1 2 x y` | Unrestricted VAR. The two numbers are the first and last lag. | ✓ |
| Quick > Estimate VAR > Vector Error Correction | `var v2.ec(c,1) 1 2 x y` | VEC model for cointegrated series. ec(c,1) means a constant and one cointegrating relation. | ✓ |
| Object > New Object > System | `system s1.append y = c(1) + c(2)*x` | Build a system of equations, then estimate it jointly. | ✓ |


## Reading what an estimation produced

Look these up from a cell with `%econ eviews results`.

| You would click | Command | What it does | |
|---|---|---|---|
| Equation > View > Estimation Output | `eq1.output` | The estimation table — coefficients, standard errors, t-statistics, R-squared, information criteria. | ✓ |
| Equation > View > Representations | `eq1.representations` | The equation written out three ways, including the substituted-coefficient form you can paste into a paper. | ✓ |
| Equation > View > Coefficient Covariance Matrix | `eq1.coefcov` | The estimated variance-covariance matrix of the coefficients. | ✓ |
| Equation > View > Actual, Fitted, Residual > Graph | `eq1.resids` | The three-line plot of actual, fitted and residual — the first thing to look at after estimating. | ✓ |
| Equation > View > Residual Diagnostics > Histogram | `eq1.hist` | Residual histogram with the Jarque-Bera normality test. | ✓ |
| Equation > View > Residual Diagnostics > Correlogram | `eq1.correl` | Correlogram of the residuals — checks for leftover serial correlation. | ✓ |
| Residual Diagnostics > Correlogram Squared Residuals | `eq1.correlsq` | Correlogram of squared residuals — checks for ARCH effects. | ✓ |
| read it off the output table | `scalar r2 = eq1.@r2` | Pull a single number into a scalar you can then send to Python: @r2, @rbar2, @aic, @schwarz, @dw, @f, @logl, @coefs(i), @stderrs(i), @tstats(i). | ✓ |
| Equation > Proc > Make Residual Series | `eq1.makeresid res1` | Save the residuals as a series you can plot or test. | ✓ |


## Diagnostic and specification tests after estimation

Look these up from a cell with `%econ eviews test`.

| You would click | Command | What it does | |
|---|---|---|---|
| Equation > View > Coefficient Diagnostics > Wald Test | `eq1.wald c(2)=0` | Test a linear restriction on the coefficients. | ✓ |
| Coefficient Diagnostics > Omitted Variables | `eq1.testadd w` | Would adding these variables improve the equation? | ✓ |
| Coefficient Diagnostics > Redundant Variables | `eq1.testdrop z` | Can these variables be dropped without loss? | ✓ |
| Coefficient Diagnostics > Variance Inflation Factors | `eq1.varinf` | VIFs — how much multicollinearity is inflating each standard error. | ✓ |
| Residual Diagnostics > Serial Correlation LM Test | `eq1.auto(2)` | Breusch-Godfrey test for serial correlation up to the lag you give. | ✓ |
| Residual Diagnostics > Heteroskedasticity > White | `eq1.white` | White's test for heteroskedasticity. | ✓ |
| Residual Diagnostics > Heteroskedasticity > Breusch-Pagan | `eq1.hettest w` | Breusch-Pagan-Godfrey test. You must name the regressors to test against — on its own it is refused. | ✓ |
| Residual Diagnostics > Heteroskedasticity > ARCH | `eq1.archtest(1)` | ARCH LM test for volatility clustering in the residuals. | ✓ |
| Stability Diagnostics > Ramsey RESET Test | `eq1.reset(1)` | Ramsey RESET — is the functional form wrong? | ✓ |
| Stability Diagnostics > Chow Breakpoint Test | `eq1.chow 2000Q1` | Chow test for a structural break at a date you name. | ✓ |
| Stability Diagnostics > Recursive Estimates > Coefficients | `eq1.rls(c)` | Recursive coefficient estimates — watch each coefficient as the sample grows. | ✓ |
| Stability Diagnostics > Recursive Estimates > Residuals | `eq1.rls(r)` | Recursive residuals with two-standard-error bands. | ✓ |
| Recursive Estimates > One-Step Forecast Test | `eq1.rls(o)` | One-step-ahead forecast test for parameter stability. | ✓ |
| Recursive Estimates > N-Step Forecast Test | `eq1.rls(n)` | N-step-ahead forecast test. | ✓ |
| Recursive Estimates > CUSUM tests | `eq1.rls(q)` | The CUSUM family, for parameter stability. EViews 13 accepts the recursive options c, n, o, q, r and v — rls(s) is not one of them. | ✓ |


## Forecasting and fitted values

Look these up from a cell with `%econ eviews forecast`.

| You would click | Command | What it does | |
|---|---|---|---|
| Equation window > Forecast button | `eq1.forecast yf` | Produce forecasts into a new series, over the current sample. Set the sample wider than the estimation sample first. | ✓ |
| Forecast dialog > Forecast graph | `eq1.forecast(g) yf` | Forecast and show the plot. EViews' own forecast window cannot be exported, so EconEnv rebuilds it as forecast +/- 2 standard errors. | ✓ |
| Forecast dialog > S.E. series | `eq1.forecast(e) yf yf_se` | Also write the forecast standard errors to a second series. | ✓ |
| Forecast dialog > Static | `eq1.forecast(s) yf` | Static (one-step-ahead) forecasts using actual lagged values, rather than dynamic forecasts that feed on their own predictions. |  |
| Equation > Proc > Forecast (in sample) | `eq1.fit yfit` | Fitted values over the estimation sample. | ✓ |


## VAR and VEC output

Look these up from a cell with `%econ eviews var`.

| You would click | Command | What it does | |
|---|---|---|---|
| VAR > View > Estimation Output | `v1.output` | The full VAR coefficient table. | ✓ |
| VAR > View > Impulse Response | `v1.impulse` | Impulse response functions — how each variable reacts to a shock. | ✓ |
| Impulse dialog > Cholesky decomposition | `v1.impulse(imp=chol)` | Impulse responses with Cholesky orthogonalisation. Ordering matters. | ✓ |
| VAR > View > Variance Decomposition | `v1.decomp` | How much of each variable's forecast error variance each shock explains. | ✓ |
| VAR > View > Lag Structure > AR Roots Table | `v1.arroots` | Roots of the characteristic polynomial — all inside the unit circle means a stable VAR. | ✓ |
| VAR > View > Residual Diagnostics > Correlograms | `v1.correl` | Residual correlograms for the system. | ✓ |
| VAR > View > Lag Structure > Lag Length Criteria | `v1.laglen(8)` | AIC, SC and HQ across lag lengths, to choose the VAR order. |  |
| Lag Structure > Granger Causality/Block Exogeneity | `v1.testexog` | Block exogeneity Wald tests within the VAR. |  |


## Panel data

Look these up from a cell with `%econ eviews panel`.

| You would click | Command | What it does | |
|---|---|---|---|
| Proc > Structure/Resize > Panel | `pagestruct id date` | Turn the page into a panel by naming the cross-section and date variables. Nothing panel-specific works until you do this. |  |
| Estimate dialog > Panel Options > Fixed | `equation p2.ls(cx=f) y c x` | Cross-section fixed effects. |  |
| Estimate dialog > Panel Options > Random | `equation p3.ls(cx=r) y c x` | Cross-section random effects. |  |
| Panel Options > both Fixed | `equation p4.ls(cx=f, per=f) y c x` | Two-way fixed effects, entity and period. |  |
| Equation > View > Fixed/Random Effects Testing | `p3.fixedtest` | Hausman test for fixed versus random effects. |  |
| Series > View > Unit Root Test (panel) | `x.uroot(sum)` | Panel unit root tests — Levin-Lin-Chu, Im-Pesaran-Shin and others. |  |
| Quick > Estimate Equation > GMM, panel | `equation p6.gmm(cx=fd, gmm=perwhite) y c y(-1) x @ y(-2)` | Arellano-Bond style dynamic panel GMM in first differences. |  |


## Scalars, matrices, loops and control

Look these up from a cell with `%econ eviews program`.

| You would click | Command | What it does | |
|---|---|---|---|
| Object > New Object > Scalar | `scalar s1 = 3.14` | A single number. The bridge for getting one value out to Python. | ✓ |
| Object > New Object > Matrix | `matrix(3,3) m1` | Matrix and vector objects. |  |
| Proc > Make Vector/Matrix | `stom(x, vx)` | Convert a series to a vector, or a vector back to a series. |  |
| no GUI equivalent | `for !i = 1 to 4   series lag{!i} = y(-!i) next` | Loop. !i is a numeric control variable, %v a string one, and {...} substitutes the value into the command. |  |
| no GUI equivalent | `if @obs(y) > 100 then   equation eq1.ls y c x endif` | Conditional execution inside a cell. |  |
| Help menu | `help ls` | Open EViews' own help page for a command — the fastest way to find options this catalogue does not list. |  |

---

## When this page does not have it

Ask EViews itself. It has help for every command:

```python
%%eviews
help ls
help arch
```

And in the EViews window, the status line along the bottom echoes the command
for many things you click. Click once in the GUI, read the line, and you have
the syntax — which is often the fastest way to learn the command for something
unusual.

## If a command runs but you see nothing

Tell EconEnv, because that is a bug in EconEnv rather than in what you typed.
Every display command should produce either output, a plot, or a warning saying
it could not be read. Silence is never correct:
<https://github.com/merwanroudane/econenv/issues>

---

Related: [EViews engine](eviews.md) · [magic commands](../magics.md) ·
[troubleshooting](../troubleshooting.md)
