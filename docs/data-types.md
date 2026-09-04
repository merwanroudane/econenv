# Data types and what survives a trip

EconEnv's rule (brief §11): **no silent lossy conversion**. Anything that
changes meaning produces a `UserWarning` naming the column, and anything that
would change a *value* raises instead.

## The mapping

| EconEnv logical type | pandas | R | Stata | EViews |
|---|---|---|---|---|
| `boolean` | `bool` / `boolean` | `logical` | numeric 0/1 ⚠ | numeric 0/1 ⚠ |
| `integer` | `int64` / `Int64` | `integer` | `long` / `int` | `series` (double) ⚠ |
| `float` | `float64` | `numeric` | `double` / `float` | `series` |
| `string` | `object` / `string` | `character` | `str#` / `strL` | `alpha` ⚠ |
| `categorical` | `Categorical` | `factor` (levels + order kept) | string labels ⚠ | integer codes ⚠ |
| `date` | `datetime64` | `Date` | `%td` | numeric ⚠ |
| `datetime` | `datetime64[tz]` | `POSIXct` (UTC) | `%tc` ⚠ | numeric ⚠ |
| missing | `NaN` / `NA` / `NaT` | `NA` | `.` (and `.a`–`.z`) ⚠ | `NA` |

⚠ = a warning is emitted; the detail is below.

## Round-trip fidelity, measured

Python → R → Python preserves **everything** in the table:

```python
df = pd.DataFrame({
    "num":   [1.5, 2.5, np.nan, 4.0],
    "whole": pd.array([1, 2, 3, 4], dtype="int64"),
    "txt":   ["a", "b", "", None],
    "grp":   pd.Categorical(["lo","hi","lo","hi"], categories=["lo","hi"], ordered=True),
    "when":  pd.to_datetime(["2020-01-01","2020-04-01","2020-07-01","2020-10-01"]),
    "flag":  [True, False, True, False],
})
econenv.push("r", "d", df)
back = econenv.pull("r", "d")
```

`back` comes home with `Int64`, an **ordered** `Categorical` with levels in the
original order, `datetime64`, `boolean`, and — the one people usually lose —
the empty string in `txt[2]` still distinct from the missing value in `txt[3]`.

That last one is why the CSV transport uses an explicit `__ECONENV_NA__`
sentinel rather than an empty field.

## Where information is genuinely lost

### Stata

**Extended missing values.** Stata has 27 (`.` and `.a`–`.z`); pandas has one
`NaN`. Pulling from Stata collapses them. Reported on every pull.

**Value labels.** PyStata cannot accept a pandas `Categorical` directly, so
categories are sent as strings and no Stata value label is created. The
categories are listed in the warning detail.

**Datetimes** become `%tc` (milliseconds since 1960-01-01) — a numeric variable.
Apply `format var %tc` in Stata to display it as a date. A timezone, if
present, is converted to UTC and then dropped; the warning says so.

**Names.** Maximum 32 characters, `[A-Za-z_][A-Za-z0-9_]*`, no reserved words.
Renames are reported individually, not applied quietly.

### EViews

**No factor type.** A categorical becomes integer codes 0…k−1; the warning
lists the mapping.

**Dates** become days since 1970-01-01 as a plain numeric series.

**Strings** become an `alpha` series written one observation at a time — slow,
so it is capped at 5000 rows and raises `LossyConversionError` beyond that
rather than hanging.

**Names.** Maximum 24 characters, no reserved word (`c`, `resid`, `na`,
`trend`, …).

**Undated pages.** If the frame has no recognised date index, the workfile page
is created undated and you get a warning, because EViews time-series operators
(`d()`, lags, dated `@trend`) then treat observations as unordered — a silent
source of wrong results.

**And the one that would be invisible:** writing a series through COM with a
plain Python list stores `NA` for every observation and *reports success*. Every
numeric push is therefore read back and verified; a mismatch raises. See
[engines/eviews.md](engines/eviews.md).

### R

Nothing in the supported set is lost. The two things worth knowing:

* A non-`RangeIndex` becomes ordinary column(s), reported as info.
* Meaningful row names (`coef(summary(fit))` uses the term names) are carried
  across and become the pandas index. Default `1:n` row names are not.

## Inspecting what a transfer cost

```python
econenv.push("eviews", "wf", df)          # warnings appear immediately
report = econenv.transfer.conversion_report(back)
print(report)
```

```
eviews pull:
  [info] EViews NA read as NaN
  [info] alpha (string) series are not returned by GetSeries
```

```python
econenv.transfer.dataset_report(back)
```

```
['source engine: eviews', 'time variable: index', 'frequency: QS']
```

## Metadata that travels with the frame

`DatasetMetadata` (brief §12) rides along in `df.attrs["econenv_metadata"]`:

`name`, `columns` (per-column `ColumnSchema`), `time_var`, `panel_var`,
`frequency`, `index_names`, `source_engine`, `history`, `notes`.

It is inferred automatically — a `DatetimeIndex` sets `time_var` and
`frequency`; a two-level `MultiIndex` is read as (panel unit, time) — and can be
set explicitly:

```python
econenv.transfer.annotate(df, time_var="year", panel_var="country", frequency="YS")
```
