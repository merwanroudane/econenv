# GAUSS commands for research

GAUSS is the least like the other engines EconEnv drives. It has no DataFrame,
its matrix syntax is its own, and the operators a researcher needs most are not
guessable from a Python or R background. This page is the translation.

Look it up from a cell instead of reading here — same content, no context
switch:

```python
%econ gauss                   # the categories
%econ gauss regression        # ols and friends
%econ gauss find missing      # search everything
```

## The three things that catch everyone out

**1. Every statement ends with a semicolon.** A missing one is a syntax error,
not a warning.

```gauss
x = 5;
```

**2. A bare expression prints nothing.** Where Python echoes the last value,
GAUSS needs to be told:

```gauss
x           /* shows nothing at all */
print x;    /* shows it */
```

**3. `~` joins columns, `|` stacks rows.** This is how a design matrix is
built, and it has no equivalent in the other engines' syntax:

```gauss
X = ones(rows(y),1) ~ x1 ~ x2;   /* constant, then two regressors */
z = a | b;                       /* a on top of b */
```

## And one that looks like a bug

GAUSS **compiles the whole cell before running any of it**. A mistyped name on
the last line means the first line never ran either, so a cell can produce no
output at all rather than a partial result. EconEnv says so explicitly when it
happens, because the natural reading — "my print statement did nothing" — sends
people looking in the wrong place.

## Least squares, annotated

```python
%%gauss -i df -o b
y = df[.,3];                                /* third column            */
X = ones(rows(df),1) ~ df[.,1] ~ df[.,2];   /* constant + regressors   */
b = y / X;                                  /* solve X*b = y           */
print b;
```

`/` is the least-squares solve, not division — it is GAUSS's equivalent of
`numpy.linalg.lstsq`, and it is more accurate than forming `inv(X'X)X'y`
yourself. For standard errors and R-squared use `ols`, which is what
`econenv.compare_ols` calls.

## What a check mark means

An entry marked **✓** was resolved against a live GAUSS through EconEnv while
this page was generated. Operators and keywords cannot be probed that way and
are unmarked; so are the functions belonging to libraries this machine does not
have, which say so in their note.

---

## Contents

95 commands, 65 resolved against a live GAUSS.

- [Syntax, printing and the things that trip up newcomers](#syntax-printing-and-the-things-that-trip-up-newcomers) — `%econ gauss basics`
- [Building, shaping and slicing matrices](#building-shaping-and-slicing-matrices) — `%econ gauss matrix`
- [Linear algebra and solving systems](#linear-algebra-and-solving-systems) — `%econ gauss algebra`
- [Descriptive statistics and distributions](#descriptive-statistics-and-distributions) — `%econ gauss stats`
- [Reading and writing files and datasets](#reading-and-writing-files-and-datasets) — `%econ gauss data`
- [Missing values, sorting, selecting and grouping](#missing-values-sorting-selecting-and-grouping) — `%econ gauss clean`
- [Least squares and related estimators](#least-squares-and-related-estimators) — `%econ gauss regression`
- [Lags, differences and time-series work](#lags-differences-and-time-series-work) — `%econ gauss timeseries`
- [Optimisation and root finding](#optimisation-and-root-finding) — `%econ gauss optimize`
- [Loops, conditions and procedures](#loops-conditions-and-procedures) — `%econ gauss control`
- [Random numbers and simulation](#random-numbers-and-simulation) — `%econ gauss random`
- [Controlling what GAUSS prints](#controlling-what-gauss-prints) — `%econ gauss output`

| Commands | Library |
|---|---|
| 92 | the GAUSS language itself |
| 2 | TSMT (Time Series MT) |
| 1 | CML / Constrained Maximum Likelihood |


## Syntax, printing and the things that trip up newcomers

Look these up from a cell with `%econ gauss basics`.

| Command | What it does | Needs | |
|---|---|---|---|
| `print` | Show a value. GAUSS prints nothing for a bare expression. <br><sub>Unlike Python, `x;` on its own displays nothing.</sub> | — |  |
| `;` | Every statement ends with a semicolon. A missing one is a syntax error. | — |  |
| `/* */` | A comment. `@ ... @` is the older form and also works. | — |  |
| `let` | Build a matrix from literal values without expressions. | — |  |
| `type` | What a symbol is: 6 is a matrix, 13 a string. <br><sub>EconEnv uses this to decide how a value crosses to Python.</sub> | — | ✓ |
| `show` | List the symbols in the workspace with their sizes. | — |  |
| `clear` | Remove symbols from the workspace. | — |  |

```gauss
print "rows: " rows(x);
x = 5;
/* this is a comment */
let x = 1 2 3;
```


## Building, shaping and slicing matrices

Look these up from a cell with `%econ gauss matrix`.

| Command | What it does | Needs | |
|---|---|---|---|
| `~` | Horizontal concatenation — join matrices side by side. <br><sub>This is how a design matrix with a constant is built.</sub> | — |  |
| `\|` | Vertical concatenation — stack matrices on top of each other. | — |  |
| `ones` | A matrix of ones — the constant column of a regression. | — | ✓ |
| `zeros` | A matrix of zeros. | — | ✓ |
| `eye` | The identity matrix. | — | ✓ |
| `rows` | Number of rows. | — | ✓ |
| `cols` | Number of columns. | — | ✓ |
| `reshape` | Change the shape, filling row by row. | — | ✓ |
| `submat` | Pull out chosen rows and columns. | — | ✓ |
| `delif` | Delete rows where a condition holds. | — | ✓ |
| `selif` | Keep rows where a condition holds. | — | ✓ |
| `vec` | Stack the columns into one long column vector. <br><sub>A GAUSS built-in, so a Python variable cannot be pushed under this name.</sub> | — | ✓ |
| `vecr` | Stack the rows instead of the columns. | — | ✓ |
| `diag` | The diagonal of a matrix, as a column. | — | ✓ |
| `trimr` | Drop rows from the top and bottom — how a lag is aligned. | — | ✓ |

```gauss
X = ones(rows(y),1) ~ x1 ~ x2;
z = a | b;
c = ones(rows(y), 1);
z = zeros(10, 3);
```


## Linear algebra and solving systems

Look these up from a cell with `%econ gauss algebra`.

| Command | What it does | Needs | |
|---|---|---|---|
| `inv` | Matrix inverse. Prefer / for solving a system. <br><sub>For least squares use y / X, which is more accurate than inv(X'X)X'y.</sub> | — | ✓ |
| `invpd` | Inverse of a positive definite matrix — faster and stabler. | — | ✓ |
| `/` | Least squares solve: b = y / X solves X*b = y. <br><sub>The workhorse. This is GAUSS's equivalent of numpy.linalg.lstsq.</sub> | — |  |
| `det` | Determinant. | — | ✓ |
| `rank` | Numerical rank — how collinear the columns are. | — | ✓ |
| `chol` | Cholesky factor of a positive definite matrix. | — | ✓ |
| `eig` | Eigenvalues. | — | ✓ |
| `eigv` | Eigenvalues and eigenvectors together. | — | ✓ |
| `svd` | Singular values. | — | ✓ |
| `'` | Transpose, written as a trailing apostrophe. | — |  |

```gauss
A_inv = inv(A);
V = invpd(X'X);
b = y / X;
d = det(A);
```


## Descriptive statistics and distributions

Look these up from a cell with `%econ gauss stats`.

| Command | What it does | Needs | |
|---|---|---|---|
| `meanc` | Column means — returns one value per column. | — | ✓ |
| `stdc` | Column standard deviations. | — | ✓ |
| `sumc` | Column sums. | — | ✓ |
| `median` | Column medians. | — | ✓ |
| `minc` | Column minima. | — | ✓ |
| `maxc` | Column maxima. | — | ✓ |
| `moment` | Cross-product matrix X'X, handling missing values. | — | ✓ |
| `corrx` | Correlation matrix. | — | ✓ |
| `vcx` | Covariance matrix. | — | ✓ |
| `quantile` | Quantiles of each column. | — | ✓ |
| `cdfn` | Standard normal CDF. | — | ✓ |
| `cdftc` | Upper tail of the t distribution — the p-value of a t statistic. <br><sub>Two-sided p-value is 2*cdftc(abs(t), df).</sub> | — | ✓ |
| `cdftci` | Inverse t — the critical value for a confidence interval. | — | ✓ |
| `cdfchic` | Upper tail of the chi-square distribution. | — | ✓ |
| `cdffc` | Upper tail of the F distribution. | — | ✓ |

```gauss
m = meanc(X);
s = stdc(X);
total = sumc(X);
m = median(X);
```


## Reading and writing files and datasets

Look these up from a cell with `%econ gauss data`.

| Command | What it does | Needs | |
|---|---|---|---|
| `loadd` | Load a dataset or CSV into a matrix or dataframe. | — | ✓ |
| `saved` | Save a matrix as a GAUSS dataset or CSV. | — | ✓ |
| `csvReadM` | Read a CSV straight into a matrix. <br><sub>What EconEnv uses to bring a DataFrame in.</sub> | — | ✓ |
| `csvWriteM` | Write a matrix to CSV. <br><sub>Writes about 15 significant digits; EconEnv writes 17 itself so a double round-trips exactly.</sub> | — | ✓ |
| `save` | Save a symbol to a .fmt (matrix) or .fst (string) file. <br><sub>How EconEnv carries values from one %%gauss cell to the next.</sub> | — |  |
| `load` | Load a matrix saved with save. | — |  |
| `loads` | Load a *string* saved with save — load will not do it. | — |  |

```gauss
X = loadd("data.csv");
call saved(X, "out.csv", 0);
X = csvReadM("data.csv");
r = csvWriteM(X, "out.csv");
```


## Missing values, sorting, selecting and grouping

Look these up from a cell with `%econ gauss clean`.

| Command | What it does | Needs | |
|---|---|---|---|
| `miss` | Turn values into GAUSS missing values. | — | ✓ |
| `missex` | Set missing where a logical mask is true. | — | ✓ |
| `ismiss` | 1 if the matrix contains any missing value. | — | ✓ |
| `packr` | Drop every row containing a missing value — listwise deletion. <br><sub>Pack the y and X together so the same rows are dropped from both.</sub> | — | ✓ |
| `sortc` | Sort rows by a chosen column, ascending. | — | ✓ |
| `sortmc` | Sort by several columns. | — | ✓ |
| `unique` | The distinct values of a column, sorted. | — | ✓ |
| `counts` | How many elements fall in each bin — a frequency table. | — | ✓ |
| `recode` | Replace values according to conditions. | — | ✓ |

```gauss
y = miss(y, -999);
y = missex(y, y .< 0);
if ismiss(X); print "has gaps"; endif;
clean = packr(y ~ X);
```


## Least squares and related estimators

Look these up from a cell with `%econ gauss regression`.

| Command | What it does | Needs | |
|---|---|---|---|
| `ols` | Least squares with standard errors, R-squared and sigma. <br><sub>Set __output=0 to suppress the printed report and _olsres=1 for residuals. EconEnv's compare_ols uses this.</sub> | — | ✓ |
| `olsqr` | Least squares coefficients only, by QR — numerically safer. | — | ✓ |
| `__output` | Set to 0 to stop ols printing its own report. <br><sub>A global, set before calling ols.</sub> | — |  |
| `_olsres` | Set to 1 to make ols return residuals and Durbin-Watson. | — |  |
| `glm` | Generalised linear models. | — | ✓ |

```gauss
{ vnam,m,b,stb,vc,se,sig,cx,rsq,resid,dw } = ols("", y, X);
b = olsqr(y, X);
__output = 0;
_olsres = 1;
```


## Lags, differences and time-series work

Look these up from a cell with `%econ gauss timeseries`.

| Command | What it does | Needs | |
|---|---|---|---|
| `lagn` | Lag a series by n periods. | — | ✓ |
| `lag1` | Lag by one period. | — | ✓ |
| `diff` | First difference of a series. <br><sub>Written with lag1; trim the first row before using it.</sub> | — |  |
| `acf` | Sample autocorrelation function. <br><sub>acf(series, lags, order of differencing). Pass 1 as the third argument to difference first.</sub> | — | ✓ |
| `pacf` | Sample partial autocorrelation function. <br><sub>pacf(series, lags, order of differencing).</sub> | — | ✓ |
| `dfgls` | DF-GLS unit root test. <br><sub>Not resolvable on a machine without TSMT installed.</sub> | TSMT (Time Series MT) |  |
| `vmdiff` | Difference a matrix of series. <br><sub>Not resolvable on a machine without TSMT installed.</sub> | TSMT (Time Series MT) |  |

```gauss
y1 = lagn(y, 1);
y1 = lag1(y);
dy = y - lag1(y);
a = acf(y, 12, 0);
```


## Optimisation and root finding

Look these up from a cell with `%econ gauss optimize`.

| Command | What it does | Needs | |
|---|---|---|---|
| `optmt` | General unconstrained optimisation. <br><sub>Not resolvable on a machine without CML installed.</sub> | CML / Constrained Maximum Likelihood |  |
| `qnewton` | Quasi-Newton minimisation, in base GAUSS. | — | ✓ |
| `eqSolve` | Solve a system of nonlinear equations. | — | ✓ |
| `gradp` | Numerical gradient of a function. | — | ✓ |
| `hessp` | Numerical Hessian — the basis of a standard error. | — | ✓ |

```gauss
out = optmt(&fn, start);
{ x, f, g, ret } = qnewton(&fn, start);
{ x, f, ret } = eqSolve(&fn, start);
g = gradp(&fn, x0);
```


## Loops, conditions and procedures

Look these up from a cell with `%econ gauss control`.

| Command | What it does | Needs | |
|---|---|---|---|
| `proc` | Define a procedure. Ends with endp. <br><sub>The (1) is the number of values returned. A procedure must be defined in the same cell that uses it.</sub> | — |  |
| `retp` | Return values from a procedure. | — |  |
| `local` | Declare a procedure's local variables. | — |  |
| `do while` | The loop. GAUSS has no for-in. | — |  |
| `do until` | Loop until a condition becomes true. | — |  |
| `if` | Conditional. Needs endif, and elseif is one word. | — |  |
| `.*` | Element-by-element multiply — `*` is matrix multiplication. <br><sub>The dot prefix makes any operator elementwise: .* ./ .^ .> .==</sub> | — |  |

```gauss
proc (1) = sqr(x);
    retp(x .* x);
endp;
retp(b, se);
local i, n, buf;
i = 1;
do while i <= n;
    i = i + 1;
endo;
```


## Random numbers and simulation

Look these up from a cell with `%econ gauss random`.

| Command | What it does | Needs | |
|---|---|---|---|
| `rndn` | Standard normal draws. | — | ✓ |
| `rndu` | Uniform draws on [0,1, verified=True). | — |  |
| `rndseed` | Set the seed, so a simulation reproduces. | — |  |
| `rndKMn` | Normal draws from an explicitly carried state. | — | ✓ |

```gauss
e = rndn(100, 1);
u = rndu(100, 1);
rndseed 42;
{ x, state } = rndKMn(100, 1, state);
```


## Controlling what GAUSS prints

Look these up from a cell with `%econ gauss output`.

| Command | What it does | Needs | |
|---|---|---|---|
| `format` | Control how numbers print — width and decimals. | — |  |
| `output` | Send printed output to a file as well as the screen. | — |  |
| `printfm` | Print a matrix with per-column formats. | — | ✓ |
| `ftos` | Format a number as a string. <br><sub>EconEnv uses this at 17 digits to move doubles without losing precision.</sub> | — | ✓ |

```gauss
format /rd 10,4;
output file = log.txt on;
call printfm(X, 1~1, "*.*lf" ~ "*.*lf");
buf = ftos(x, "%*.*lf", 10, 4);
```

---

## When this page does not have it

Ask GAUSS itself, from the notebook:

```python
%%gauss
help ols;
```

GAUSS also ships its full documentation with the installation, and the command
reference there is the authority for arguments this page summarises.

## What does not carry between cells

Values assigned at the top level do — EconEnv saves and reloads them using
GAUSS's own `save`/`load`. **Procedures, `#include`s and library loads do
not**, because each cell runs in a fresh process. Define a `proc` in the same
cell that uses it.

That is a real limit of the command-line backend rather than a choice, and it
is stated rather than worked around: rebuilding a session by replaying earlier
cells would silently re-run their side effects.

---

Related: [GAUSS engine](gauss.md) · [magic commands](../magics.md) ·
[comparison](../comparison.md) · [troubleshooting](../troubleshooting.md)
