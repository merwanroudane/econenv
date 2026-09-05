# MATLAB

Driven through the **MATLAB Engine API for Python** — the interface MathWorks
ships inside every MATLAB installation and publishes on PyPI as `matlabengine`.
EconEnv uses it rather than a console subprocess because it is the supported
route and it exchanges arrays natively, so a DataFrame becomes a real MATLAB
`table` rather than parsed text.

## Installing the bridge

The engine package is versioned to the MATLAB release **and** to your Python,
and both windows are narrow:

| MATLAB | Install | Python |
|---|---|---|
| R2024a | `pip install "matlabengine==24.1.*"` | 3.9 – **3.11** |
| R2024b | `pip install "matlabengine==24.2.*"` | 3.9 – 3.12 |
| R2025a | `pip install "matlabengine==25.1.*"` | 3.9 – 3.12 |
| R2025b | `pip install "matlabengine==25.2.*"` | 3.9 – 3.12 |
| R2026a | `pip install "matlabengine==26.1.*"` | 3.9 – **3.13** |

**Python 3.13 needs R2026a or newer** — it is the first release whose Engine API
supports it. On an earlier MATLAB, run EconEnv on a Python that release can
drive:

```bash
conda create -n econ python=3.11
conda activate econ
pip install econenv "matlabengine==24.1.*"
```

A release newer than this table still resolves: MathWorks numbers the series to
a rule — `R20YYa` is `YY.1`, `R20YYb` is `YY.2` — so EconEnv computes the pin for
R2026b and beyond rather than falling off the end of a lookup table.

`econenv doctor` works this out for you: it names a pin for every MATLAB
release you have installed, and when your Python suits none of them it says
which release *would* work on it and which Python your own MATLAB can drive —
rather than handing you a command that cannot work.

## Which release actually starts

If several MATLAB releases are installed, the one that starts is the one your
*engine package* matches — not the newest on disk. On a machine with R2024a and
R2025a and `matlabengine 24.1.4`, it is **R2024a** that runs, and that is what
`%econ status` reports.

Reporting the newest install instead would repeat the mistake the EViews adapter
used to make: naming a version you are not running.

## Using it

```python
%%matlab -i df -o beta
fit = fitlm(df, 'y ~ x1 + x2');
beta = fit.Coefficients.Estimate;
disp(fit)
```

| Flag | Meaning |
|---|---|
| `-i NAME` | push a DataFrame in as a MATLAB `table` |
| `-o NAME` | bring a MATLAB variable back to Python |
| `-q` | suppress output |
| `--no-graphs` | do not capture figures this cell draws |
| `--result` | return the `ExecutionResult` instead of displaying it |

## Starting is slow — once

A cold start takes roughly a minute. The first cell that uses MATLAB pays for
the whole session; every later one is fast. That is also why `%econ status`
never starts it: detection reads the disk and the registry only.

If MATLAB is already open, share it and EconEnv attaches instead of launching a
second copy:

```matlab
matlab.engine.shareEngine
```

```python
%econ config matlab.shared MATLAB_shared
```

## Data types

| pandas | MATLAB | Note |
|---|---|---|
| float, int | `double` | integers become double, as MATLAB tables prefer |
| bool | `logical` | a missing value cannot be represented — NaN becomes false, and you are warned |
| datetime | `datetime` | the pandas index becomes a column, since MATLAB tables have no date index |
| category | `categorical` | |
| str | `string` | missing strings become empty, and you are warned |

Anything lossy warns and names the column. The index is moved to a column
because a MATLAB table's row names are strings only, so a `DatetimeIndex` would
otherwise be flattened.

## Figures

Captured automatically, once each — MATLAB keeps figures open until closed, so
without a memory of what has been shown one plot would reappear under every
later cell.

```python
%econ config matlab.graphics pdf    # png | svg | pdf | off
%econ config matlab.dpi 300
```

For journal submission use `pdf`: vector figures stay sharp at any size. See
[export.md](../export.md).

## OLS, and the comparison

MATLAB implements `_fit_ols` through `fitlm`, so it appears in
`compare_ols` alongside the other four:

```python
econenv.compare_ols(df, "y ~ x1 + x2")
```

```
         python    eviews    matlab         r     stata
_cons  1.480534  1.480534  1.480534  1.480534  1.480534
x1     1.933102  1.933102  1.933102  1.933102  1.933102
```

MATLAB's `fitlm` reports AIC and BIC on the same $-2\ell + 2k$ basis as
statsmodels and Stata, so those three agree where R's and EViews' differ. R
counts $\sigma^2$ as a parameter; EViews divides by $n$.

## Tables in the notebook

`disp(tbl)` returns MATLAB's own console output — monospace text, exactly as
MATLAB printed it. For a real Jupyter table, name it on the way out:

```python
%%matlab -o coefs
mdl = fitlm(df, 'y ~ x');
coefs = mdl.Coefficients;
```

```python
coefs      # a DataFrame, rendered as a table
```

## Troubleshooting

**`matlab.engine` will not import.** Almost always a version mismatch — either
the engine package against the MATLAB release, or against your Python. Run
`econenv doctor`; it prints the exact pin.

**`Unrecognized function or variable`.** The function may be in a toolbox you do
not have, or on a path MATLAB has not been told about:

```python
%%matlab
addpath('C:/path/to/code')
```

**A cell seems to hang.** The first one is starting MATLAB. Subsequent cells are
fast; share an already-open session to skip the wait entirely.

---

Related: [export](../export.md) · [data exchange](../data-exchange.md) ·
[magics](../magics.md)
