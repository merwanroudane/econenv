# Getting started

## 1. Install

```bash
pip install econenv
```

On Windows, if you have EViews:

```bash
pip install "econenv[eviews]"
```

Nothing else is required. R, Stata and EViews are **found**, not installed, by
EconEnv.

## 2. Check what EconEnv can see

```bash
econenv doctor
```

Every line is PASS, WARNING or ERROR, and every warning tells you what to do
about it. If R, Stata or EViews is missing, that is a warning — not an error.
EconEnv works with whatever subset you have.

## 3. Load the extension

```python
%load_ext econenv
```

```
EconEnv 0.1.0 loaded — one notebook, multiple econometric engines.
  %econ                  econenv
  %Rec / %%Rec           econenv
  %R / %%R               rpy2 (official)
  %eviews / %%eviews     econenv
  %stata / %%stata       pystata (official)
  %econ status · %econ doctor · %econ help
```

That list is the answer to "which implementation owns which magic". EconEnv
loads the official `%stata` and (where rpy2 is installed) the official `%R`
rather than shadowing them, and says so.

No engine has started yet. Loading the extension is fast and consumes no
licence seat.

## 4. Your first four-engine notebook

```python
import pandas as pd, numpy as np

rng = np.random.default_rng(7)
df = pd.DataFrame({"x1": rng.normal(size=100), "x2": rng.normal(size=100)})
df["y"] = 2 + 0.5 * df.x1 - 0.3 * df.x2 + rng.normal(scale=0.4, size=100)
```

```python
%%R -i df
fit <- lm(y ~ x1 + x2, data = df)
summary(fit)
```

```python
%stata_push df
```

```python
%%stata
regress y x1 x2
```

```python
%%eviews -i df
equation eq1.ls y c x1 x2
```

```python
%eviews_get eq1.@r2
```

All of that ran in **one Python kernel**. `df` is still the same object.

## 5. The thing you cannot easily do any other way

```python
econenv.compare_ols(df, "y ~ x1 + x2")
```

```
OLS: y ~ x1 + x2
Engines agree within tolerance (rtol=1e-08, atol=1e-10)

Coefficients
              python         eviews              r          stata
term
_cons      1.9821094      1.9821094      1.9821094      1.9821094
x1         0.4900282      0.4900282      0.4900282      0.4900282
x2        -0.3112102     -0.3112102     -0.3112102     -0.3112102

Notes:
  - aic: AIC normalisation differs: statsmodels -2ll+2k; R counts sigma^2 as a
    parameter (k+1); EViews divides by n; Stata needs `estat ic`.
```

Coefficients identical to machine precision. Information criteria different —
and named, with the reason. That is the design principle: EconEnv shows you
where the programs disagree, it does not sand it off.

## 6. Moving data around

```python
econenv.push("stata", "default", df)     # Python → Stata
econenv.move("stata", "r", "default")    # Stata → R, no file touched
back = econenv.pull("r", "default")      # R → Python
```

Anything a transfer had to compromise on arrives as a warning:

```
UserWarning: EconEnv push -> stata: [warning] region: categorical sent as a
string column; Stata value labels are not created
```

## Next

* [magics.md](magics.md) — every magic and flag
* [data-types.md](data-types.md) — what survives which trip
* [comparison.md](comparison.md) — why the engines' AIC differ
* [`examples/`](../examples/) — nine progressive notebooks
