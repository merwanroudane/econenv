# Result objects

EconEnv is not a terminal inside a notebook. Every execution returns a
structured object (brief §15).

## `ExecutionResult`

```python
result = econenv.engine("r").execute("summary(fit)")
```

| Field | |
|---|---|
| `engine`, `engine_version` | which engine, and the **connected** version |
| `code` | what was run, verbatim |
| `success`, `error` | |
| `stdout`, `stderr`, `text` | as the engine wrote them |
| `warnings` | list, kept separate from output |
| `tables` | `list[DataFrame]` |
| `figures` | `list[Figure]` — PNG or SVG bytes |
| `scalars`, `matrices` | |
| `value` | the engine's own return value, where it has one |
| `metadata` | engine-specific (Stata's `rc`, EViews' workfile/page) |
| `conversions` | `ConversionReport`s from any transfer in the call |
| `elapsed`, `timestamp` | |

`to_dict()` is JSON-serialisable. In a notebook it renders as HTML with the
engine, timing, output, warnings and any tables; in a terminal it prints plain
text.

Get one from a magic with `-r`:

```python
result = %eviews -r equation eq1.ls y c x
```

## `ModelResult`

The harmonised econometric subset (brief §16). Fields present in all four
engines are filled; fields an engine does not report stay `None` — **an absent
value is information, so it is never faked**.

```python
m = econenv.engine("stata")._fit_ols(spec, df)
m.coefficients      # DataFrame: coef, std_err, stat, pvalue, ci_lower, ci_upper
m.r2, m.r2_adj, m.loglik, m.aic, m.bic, m.rmse, m.fstat, m.durbin_watson
m.nobs, m.df_model, m.df_resid
m.vcov_type         # what the engine actually used
m.command           # the command that was run
m.raw               # the untouched engine object or output
m.notes             # engine caveats that travel with the result
```

`raw` matters: the harmonised table is for comparison, and the original is what
you cite. For statsmodels it is the fitted results object; for Stata and R the
formatted output; for EViews the equation object's name.

### Term names

Normalised so engines line up: `const`, `Intercept`, `(Intercept)` and `C` all
become `_cons`, and EViews' constant-first ordering is rotated to
constant-last. The original naming survives in `raw`.

## `Figure`

```python
figure.data        # bytes
figure.mimetype    # image/png | image/svg+xml
figure.engine, figure.name
```

Renders inline through `_repr_mimebundle_`. R and EViews plots both arrive this
way; the temp file each engine had to write is deleted before you see it.

## Rich display

All three objects implement `_repr_mimebundle_`, so Jupyter gets HTML and a
terminal gets text, from the same object — no `display()` call needed.

```python
econenv.doctor()              # renders as a colour-coded table
econenv.compare_ols(df, ...)  # renders as coefficient + summary tables
```
