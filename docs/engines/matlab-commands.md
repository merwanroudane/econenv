# MATLAB commands for research

MATLAB is not short of documentation. It is short of a way to answer, without
leaving the notebook, the question a researcher actually has: *is there a
function for this, is it in a toolbox I have, and what does the call look
like?*

That is what this page and `%econ matlab` are for. They are the same content —
look it up from a cell instead of reading here:

```python
%econ matlab                     # the categories
%econ matlab timeseries          # unit roots, ARIMA, VAR
%econ matlab find cointegration  # search everything
```

## Toolboxes

Most of MATLAB's econometrics lives in toolboxes that are licensed separately,
so every entry names the one it needs. Check what you have:

```python
%%matlab
ver                              % release and every licensed toolbox
license('test', 'Econometrics_Toolbox')
which adftest                    % where a function came from
```

A function you do not have licensed fails with `Unrecognized function or
variable`, which reads like a typo and is not one — that is why the toolbox is
named here rather than left to be discovered.

## What a check mark means

An entry marked **✓** was resolved against a live MATLAB through EconEnv while
this page was generated: `exist` for functions, `which -all` for methods that
belong to a class rather than sitting on the path. Unmarked entries are
documented syntax that this machine could not confirm.

## Getting values in and out

```python
%%matlab -i df -o coefs
mdl = fitlm(df, 'y ~ x1 + x2');
coefs = mdl.Coefficients;
```

`-i` sends a Python object in; `-o` brings a MATLAB variable back as its
natural Python type — a scalar is a number, a matrix is a NumPy array, a table
is a DataFrame. The full type tables are in [matlab.md](matlab.md).

---

## Contents

102 commands, 102 resolved against a live MATLAB.

- [Finding functions and reading MATLAB's own documentation](#finding-functions-and-reading-matlab's-own-documentation) — `%econ matlab help`
- [Inspecting what exists and what type it is](#inspecting-what-exists-and-what-type-it-is) — `%econ matlab workspace`
- [Reading and writing files, tables and timetables](#reading-and-writing-files-tables-and-timetables) — `%econ matlab data`
- [Missing values, reshaping, joining and grouping](#missing-values-reshaping-joining-and-grouping) — `%econ matlab clean`
- [Descriptive statistics and correlation](#descriptive-statistics-and-correlation) — `%econ matlab stats`
- [Plotting, layout and saving figures](#plotting-layout-and-saving-figures) — `%econ matlab graphics`
- [Linear and generalised regression](#linear-and-generalised-regression) — `%econ matlab regression`
- [Autocorrelation, ARIMA/VAR, unit roots and forecasting](#autocorrelation-arimavar-unit-roots-and-forecasting) — `%econ matlab timeseries`
- [Wavelet and frequency-domain analysis](#wavelet-and-frequency-domain-analysis) — `%econ matlab wavelet`
- [Minimisation and constrained optimisation](#minimisation-and-constrained-optimisation) — `%econ matlab optimization`
- [Linear algebra and numerical computing](#linear-algebra-and-numerical-computing) — `%econ matlab matrix`

Toolboxes these commands need:

| Commands | Toolbox |
|---|---|
| 65 | ships with MATLAB |
| 16 | Econometrics Toolbox |
| 9 | Statistics and Machine Learning Toolbox |
| 5 | Optimization Toolbox |
| 5 | Wavelet Toolbox |
| 2 | Signal Processing Toolbox |


## Finding functions and reading MATLAB's own documentation

Look these up from a cell with `%econ matlab help`.

| Command | What it does | Needs | |
|---|---|---|---|
| `help` | One-screen help for a function, in the notebook. | — | ✓ |
| `doc` | Open the full documentation page for a function. <br><sub>Opens MATLAB's own browser window, not the notebook.</sub> | — | ✓ |
| `lookfor` | Search the one-line summary of every function. | — | ✓ |
| `which` | Where a function lives — and so which toolbox it needs. | — | ✓ |
| `exist` | Whether a name is a variable, function or file. | — | ✓ |
| `ver` | MATLAB release and every licensed toolbox. | — | ✓ |
| `license` | Whether a named toolbox is licensed here. | — | ✓ |
| `methods` | The methods defined on an object, such as a fitted model. | — | ✓ |
| `properties` | The properties of an object. | — | ✓ |

```python
%%matlab
help fitlm
%%matlab
doc arima
%%matlab
lookfor cointegration
%%matlab
which wcoherence
```


## Inspecting what exists and what type it is

Look these up from a cell with `%econ matlab workspace`.

| Command | What it does | Needs | |
|---|---|---|---|
| `who` | The names currently in the MATLAB workspace. | — | ✓ |
| `whos` | Names with size, bytes and class — the workspace browser. | — | ✓ |
| `class` | The MATLAB class of a value, which decides how it crosses to Python. | — | ✓ |
| `size` | Rows and columns. | — | ✓ |
| `numel` | Total number of elements. | — | ✓ |
| `head` | The first rows of a table or timetable. | — | ✓ |
| `tail` | The last rows of a table or timetable. | — | ✓ |
| `summary` | Per-variable summary of a table: type, range, missing count. <br><sub>A method on a table/timetable: summary(T).</sub> | — | ✓ |

```python
%%matlab
who
%%matlab
whos
%%matlab
class(x)
%%matlab
size(X)
```


## Reading and writing files, tables and timetables

Look these up from a cell with `%econ matlab data`.

| Command | What it does | Needs | |
|---|---|---|---|
| `readtable` | Read a delimited or Excel file into a table. | — | ✓ |
| `writetable` | Write a table to CSV or Excel. | — | ✓ |
| `readmatrix` | Read a numeric file straight into a matrix. | — | ✓ |
| `writematrix` | Write a numeric matrix to a file. | — | ✓ |
| `detectImportOptions` | Inspect and adjust how a file will be parsed before reading it. | — | ✓ |
| `table` | Build a table from columns, with variable names. | — | ✓ |
| `array2table` | Turn a numeric matrix into a named table. | — | ✓ |
| `table2array` | Drop the names and get the numeric matrix back. | — | ✓ |
| `timetable` | A table indexed by time — the right shape for time series. | — | ✓ |
| `retime` | Resample a timetable to a new frequency. <br><sub>A timetable method: retime(TT, ...).</sub> | — | ✓ |
| `synchronize` | Align several timetables onto one time base. <br><sub>A timetable method: synchronize(TT1, TT2).</sub> | — | ✓ |

```python
%%matlab
T = readtable('data.csv');
%%matlab
writetable(T, 'out.csv');
%%matlab
X = readmatrix('data.csv');
%%matlab
writematrix(X, 'out.csv');
```


## Missing values, reshaping, joining and grouping

Look these up from a cell with `%econ matlab clean`.

| Command | What it does | Needs | |
|---|---|---|---|
| `rmmissing` | Drop rows with missing values — listwise deletion. | — | ✓ |
| `fillmissing` | Fill gaps by interpolation, previous value or a constant. | — | ✓ |
| `ismissing` | A logical mask of what is missing. | — | ✓ |
| `normalize` | Standardise, rescale or centre. | — | ✓ |
| `sortrows` | Sort a table or matrix by one or more columns. | — | ✓ |
| `groupsummary` | Statistics by group — MATLAB's group-by. | — | ✓ |
| `innerjoin` | Keep rows present in both tables. <br><sub>A table method: innerjoin(T1, T2, ...).</sub> | — | ✓ |
| `outerjoin` | Keep rows from both, filling what is absent. <br><sub>A table method: outerjoin(T1, T2, ...).</sub> | — | ✓ |
| `varfun` | Apply a function to each variable of a table. <br><sub>A table method: varfun(@f, T).</sub> | — | ✓ |

```python
%%matlab
T = rmmissing(T);
%%matlab
T = fillmissing(T, 'linear');
%%matlab
sum(ismissing(T))
%%matlab
Z = normalize(X);
```


## Descriptive statistics and correlation

Look these up from a cell with `%econ matlab stats`.

| Command | What it does | Needs | |
|---|---|---|---|
| `mean` | Column means. | — | ✓ |
| `median` | Column medians. | — | ✓ |
| `std` | Standard deviation, normalised by n-1. | — | ✓ |
| `var` | Variance. | — | ✓ |
| `quantile` | Sample quantiles. <br><sub>Base MATLAB since it moved to datafun; no Statistics licence needed.</sub> | — | ✓ |
| `prctile` | Percentiles. <br><sub>Base MATLAB since it moved to datafun; no Statistics licence needed.</sub> | — | ✓ |
| `corr` | Correlation with p-values, Pearson/Spearman/Kendall. | Statistics and Machine Learning Toolbox | ✓ |
| `corrcoef` | Pearson correlation, in base MATLAB. | — | ✓ |
| `cov` | Covariance matrix. | — | ✓ |

```python
%%matlab
mean(X)
%%matlab
median(X)
%%matlab
std(X)
%%matlab
var(X)
```


## Plotting, layout and saving figures

Look these up from a cell with `%econ matlab graphics`.

| Command | What it does | Needs | |
|---|---|---|---|
| `plot` | Line plot — the default for a series against time. | — | ✓ |
| `scatter` | Scatter plot, optionally sized and coloured by a third variable. | — | ✓ |
| `histogram` | Histogram with automatic or chosen bins. | — | ✓ |
| `boxchart` | Box plot by group, without the Statistics toolbox. | — | ✓ |
| `bar` | Bar chart. | — | ✓ |
| `tiledlayout` | A grid of panels — the modern replacement for subplot. | — | ✓ |
| `nexttile` | Move to the next panel of a tiled layout. | — | ✓ |
| `yyaxis` | A second y axis on the right. | — | ✓ |
| `legend` | Label the series. | — | ✓ |
| `exportgraphics` | Save a figure at publication quality — vector for PDF/EPS, chosen DPI for PNG. <br><sub>EconEnv uses this to capture figures; see %econ matlab export.</sub> | — | ✓ |

```python
%%matlab
plot(dates, y); grid on;
%%matlab
scatter(x, y, 'filled');
%%matlab
histogram(resid, 30);
%%matlab
boxchart(g, y);
```


## Linear and generalised regression

Look these up from a cell with `%econ matlab regression`.

| Command | What it does | Needs | |
|---|---|---|---|
| `fitlm` | Linear regression with a formula, diagnostics and a coefficient table. | Statistics and Machine Learning Toolbox | ✓ |
| `regress` | Least squares returning coefficients and confidence intervals. | Statistics and Machine Learning Toolbox | ✓ |
| `fitglm` | Generalised linear model — logit, probit, Poisson. | Statistics and Machine Learning Toolbox | ✓ |
| `stepwiselm` | Stepwise selection of terms. | Statistics and Machine Learning Toolbox | ✓ |
| `robustfit` | Robust regression, down-weighting outliers. | Statistics and Machine Learning Toolbox | ✓ |
| `coefCI` | Confidence intervals for fitted coefficients. <br><sub>A method on the fitted model: coefCI(mdl).</sub> | Statistics and Machine Learning Toolbox | ✓ |
| `predict` | Fitted or forecast values, with prediction intervals. <br><sub>A method on the fitted model: predict(mdl, Tnew).</sub> | Statistics and Machine Learning Toolbox | ✓ |
| `anova` | Analysis of variance for a fitted model. | Statistics and Machine Learning Toolbox | ✓ |

```python
%%matlab
mdl = fitlm(T, 'y ~ x1 + x2');
disp(mdl)
%%matlab
[b, bint] = regress(y, [ones(n,1) X]);
%%matlab
mdl = fitglm(T, 'y ~ x', 'Distribution', 'binomial');
%%matlab
mdl = stepwiselm(T, 'y ~ 1');
```


## Autocorrelation, ARIMA/VAR, unit roots and forecasting

Look these up from a cell with `%econ matlab timeseries`.

| Command | What it does | Needs | |
|---|---|---|---|
| `autocorr` | Sample autocorrelation function with confidence bounds. | Econometrics Toolbox | ✓ |
| `parcorr` | Partial autocorrelation function. | Econometrics Toolbox | ✓ |
| `adftest` | Augmented Dickey-Fuller unit root test. | Econometrics Toolbox | ✓ |
| `kpsstest` | KPSS test, with stationarity as the null. | Econometrics Toolbox | ✓ |
| `pptest` | Phillips-Perron unit root test. | Econometrics Toolbox | ✓ |
| `arima` | Specify an ARIMA/SARIMA model before estimating it. | Econometrics Toolbox | ✓ |
| `estimate` | Fit a specified model to data by maximum likelihood. <br><sub>A method on the model object: estimate(arima(1,1,1), y).</sub> | Econometrics Toolbox | ✓ |
| `forecast` | Out-of-sample forecasts with error bands. <br><sub>A method on the fitted model: forecast(fit, 8, y).</sub> | Econometrics Toolbox | ✓ |
| `infer` | Residuals implied by a fitted model. <br><sub>A method on the fitted model: infer(fit, y).</sub> | Econometrics Toolbox | ✓ |
| `simulate` | Simulate paths from a fitted or specified model. | Econometrics Toolbox | ✓ |
| `varm` | Vector autoregression. | Econometrics Toolbox | ✓ |
| `egcitest` | Engle-Granger cointegration test. | Econometrics Toolbox | ✓ |
| `jcitest` | Johansen cointegration test. | Econometrics Toolbox | ✓ |
| `archtest` | Engle's test for ARCH effects. | Econometrics Toolbox | ✓ |
| `garch` | GARCH volatility model. | Econometrics Toolbox | ✓ |
| `lmctest` | Lagrange multiplier test for a conditional mean. | Econometrics Toolbox | ✓ |

```python
%%matlab
autocorr(y, 24);
%%matlab
parcorr(y, 24);
%%matlab
[h, p] = adftest(y, 'Model', 'ARD');
%%matlab
[h, p] = kpsstest(y);
```


## Wavelet and frequency-domain analysis

Look these up from a cell with `%econ matlab wavelet`.

| Command | What it does | Needs | |
|---|---|---|---|
| `cwt` | Continuous wavelet transform — the scalogram. | Wavelet Toolbox | ✓ |
| `icwt` | Invert a continuous wavelet transform. | Wavelet Toolbox | ✓ |
| `wcoherence` | Wavelet coherence between two series, with phase arrows. | Wavelet Toolbox | ✓ |
| `modwt` | Maximal overlap discrete wavelet transform, for decomposition by scale. | Wavelet Toolbox | ✓ |
| `modwtmra` | Multiresolution analysis from a MODWT. | Wavelet Toolbox | ✓ |
| `periodogram` | Power spectral density by periodogram. | Signal Processing Toolbox | ✓ |
| `pwelch` | Welch's averaged spectral estimate. | Signal Processing Toolbox | ✓ |

```python
%%matlab
cwt(y, years(1/12));
%%matlab
yr = icwt(wt);
%%matlab
wcoherence(x, y);
%%matlab
w = modwt(y, 'db4', 6);
```


## Minimisation and constrained optimisation

Look these up from a cell with `%econ matlab optimization`.

| Command | What it does | Needs | |
|---|---|---|---|
| `fminsearch` | Unconstrained minimisation, derivative-free. Base MATLAB. | — | ✓ |
| `fminunc` | Unconstrained minimisation using gradients. | Optimization Toolbox | ✓ |
| `fmincon` | Minimisation subject to bounds and constraints. | Optimization Toolbox | ✓ |
| `linprog` | Linear programming. | Optimization Toolbox | ✓ |
| `optimoptions` | Set solver options — tolerance, display, algorithm. | Optimization Toolbox | ✓ |
| `lsqnonlin` | Nonlinear least squares. | Optimization Toolbox | ✓ |

```python
%%matlab
b = fminsearch(@(b) sse(b), b0);
%%matlab
b = fminunc(@obj, b0);
%%matlab
b = fmincon(@obj, b0, A, c);
%%matlab
x = linprog(f, A, b);
```


## Linear algebra and numerical computing

Look these up from a cell with `%econ matlab matrix`.

| Command | What it does | Needs | |
|---|---|---|---|
| `inv` | Matrix inverse. Prefer the backslash operator for solving. <br><sub>For A*x = b use x = A\b: more accurate and faster than inv(A)*b.</sub> | — | ✓ |
| `pinv` | Moore-Penrose pseudoinverse, for rank-deficient problems. | — | ✓ |
| `eig` | Eigenvalues and eigenvectors. | — | ✓ |
| `svd` | Singular value decomposition. | — | ✓ |
| `chol` | Cholesky factorisation of a positive definite matrix. | — | ✓ |
| `qr` | QR factorisation, as used by least squares. | — | ✓ |
| `rank` | Numerical rank. | — | ✓ |
| `cond` | Condition number — how close to collinear the columns are. | — | ✓ |
| `mldivide` | The backslash operator: solve A*x = b by least squares. | — | ✓ |

```python
%%matlab
inv(A)
%%matlab
pinv(A)
%%matlab
[V, D] = eig(A);
%%matlab
[U, S, V] = svd(A);
```

---

## When this page does not have it

Ask MATLAB itself, from the notebook:

```python
%%matlab
help fitlm            % one-screen summary
lookfor cointegration % search every function's summary line
which wcoherence      % where it lives, and so which toolbox
```

`lookfor` is the one to reach for: it searches the first line of every function
on the path, which is how you find a function whose name you do not know.

## If a command runs but you see nothing

Tell EconEnv — that is a bug here rather than in what you typed. Output,
figures, or a warning saying something could not be read: silence is never
correct. <https://github.com/merwanroudane/econenv/issues>

---

Related: [MATLAB engine](matlab.md) · [magic commands](../magics.md) ·
[export](../export.md) · [troubleshooting](../troubleshooting.md)
