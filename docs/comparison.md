# Cross-engine comparison

```python
comparison = econenv.compare_ols(df, "y ~ x1 + x2")
comparison.coefficients()   # terms × engines
comparison.summary()        # one row per engine
comparison.differences()    # max abs/rel gap per term, and the verdict
comparison.explain()        # plain-language notes
comparison.agree            # bool
```

## What agreement means here

Two tolerances, both applied (brief §26):

```python
within_tolerance = (max_abs_diff <= atol) | (max_rel_diff <= rtol)
```

Defaults `rtol=1e-8`, `atol=1e-10`. A 1e-15 gap between two programs is
floating-point arithmetic, not a finding. Anything that clears **both**
tolerances is reported as a real difference.

## Measured result

Fifty observations, `y ~ x1 + x2`, all five engines on one machine:

| engine | max abs. difference vs statsmodels |
|---|---|
| statsmodels | 0 |
| EViews 13 | 5.6e-16 |
| Stata 19.5 MP | 4.4e-16 |
| R 4.5.2 | 4.4e-15 |

R², adjusted R², log-likelihood, F and RMSE agree to the same order. The
coefficients are the same numbers.

## Where they legitimately differ

### Information criteria

This is the one that surprises people, so `compare_ols` explains it every time.

| Engine | AIC formula | On the example |
|---|---|---|
| statsmodels | −2·ln L + 2k | 82.70 |
| Stata (`estat ic`) | −2·ln L + 2k, k = e(rank)+1 | 82.70 |
| R | −2·ln L + 2(k+1) — σ² counts as a parameter | 84.70 |
| EViews | (−2·ln L + 2k) / n — **divided by n** | 1.378 |

None is wrong. They are different conventions for the same quantity, and
comparing raw AIC across programs is meaningless unless you know which. Model
*rankings* within one engine are unaffected.

Stata does not put AIC/BIC in `e()` after `regress` — they exist only after
`estat ic`. EconEnv runs it, so the Stata column has a number rather than a
hole, and the note explaining the normalisation still travels with the result.

### Robust standard errors

| Engine | "robust" means |
|---|---|
| Stata `vce(robust)` | HC1 |
| statsmodels `cov_type="HC0"` | HC0 |
| statsmodels `cov_type="HC1"` | HC1 |
| EViews White | HC1 with a d.f. correction |
| R `sandwich::vcovHC` | HC3 by default |

`ModelSpec(vcov=...)` passes your choice through, and `ModelResult.vcov_type`
records what each engine actually used. If you ask several engines for "robust"
and compare, expect the standard errors to differ — the comparison names this.

### Missing values

All five use listwise deletion for OLS by default, so the estimation samples
match. They diverge for other estimators; when EconEnv gains those, the same
"report the difference" rule applies.

### Degrees of freedom and the intercept

EViews lists the constant **first** (`ls y c x1 x2`); Stata and statsmodels list
it last. EconEnv normalises the term order and renames the intercept to `_cons`
across all of them (`const`, `(Intercept)`, `C` all map to it), so the rows line
up. The original naming is preserved in `ModelResult.raw`.

## Reading the output

```python
comparison.differences()
```

```
       max_abs_diff  max_rel_diff  within_tolerance
term
_cons  4.662937e-15  2.512172e-15              True
x1     7.216450e-16  1.472660e-15              True
x2     7.216450e-16  3.774092e-15              True
```

```python
comparison.explain()
```

```
['aic: AIC normalisation differs: statsmodels -2ll+2k; R counts sigma^2 as a
  parameter (k+1); EViews divides by n; Stata needs `estat ic`.',
 'eviews: EViews lists the constant first; term order is normalised here.',
 ...]
```

## When an engine is missing

An engine that is not installed, or that fails, lands in `.failures` and the
rest still run:

```python
comparison.failures
# {'eviews': 'EViews automation needs Windows COM.'}
```

Pass `strict=True` to `run_spec` if you would rather it raise.

## What is comparable in v0.1

Only OLS. `%econ models` shows the full estimator × engine matrix, with
everything else marked `planned` — the matrix is honest about the roadmap
rather than omitting what does not exist yet.

`ModelSpec.from_formula` accepts additive terms only. Interactions, transforms
and factor expansions are **refused with a clear message**, because `y ~ x1*x2`
does not mean the same thing in statsmodels, R, Stata and EViews. Build the
column in Python first, or write the command directly in that engine's cell
magic.
