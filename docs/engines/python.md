# Python

Python is the host kernel, so this engine deliberately does **not** build an
interpreter. It exists so Python appears everywhere the other three do:

* in `%econ status` and `%econ versions`
* in reproducibility snapshots, with every installed distribution
* in the cross-engine comparison table, where "what does statsmodels say" is one
  of the four answers being compared

## Session

`start()` and `stop()` are bookkeeping. `stop()` is a deliberate no-op —
killing the host interpreter is not this engine's business.

`restart()` clears only the **EconEnv-managed namespace**, never your kernel's:

```python
engine = econenv.engine("python")
engine.execute("value = 42")
engine.pull_scalar("value")      # 42
engine.restart()
engine.pull_scalar("value")      # KeyError — but your notebook variables are intact
```

That namespace starts with `pd` and `np` bound and is reachable as
`engine.namespace`.

## OLS

`_fit_ols` uses statsmodels, with the conventions recorded on the result rather
than assumed:

* non-robust (homoskedastic) covariance by default — the same default as Stata's
  `regress` and R's `lm`
* listwise deletion of rows with any missing value in the used columns
* `vcov="hc0"`…`"hc3"` passes `cov_type` through
* `vcov_type` on the result says what was actually used

AIC/BIC use `-2·llf + 2k` and `-2·llf + k·ln(n)`. R and EViews normalise
differently; see [../comparison.md](../comparison.md).

## Packages

```python
econenv.engine("python").packages()       # the interesting ones
econenv.engine("python").all_packages()   # every installed distribution
```

`all_packages()` is what a snapshot records — the full environment, so a
replication package can reconstruct it.
