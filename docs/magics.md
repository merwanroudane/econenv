# Magic commands

## Who owns which name

`%load_ext econenv` prints this, and `%econ engines` repeats it:

| Magic | Implementation | Why |
|---|---|---|
| `%stata` `%%stata` `%mata` `%%mata` | **PyStata (official)** | StataCorp ships and maintains them |
| `%R` `%%R` | **rpy2 (official)** when rpy2 is importable | same reason |
| `%R` `%%R` | EconEnv, **only if the name is free** | never shadows an existing magic |
| `%Rec` `%%Rec` | EconEnv, always | the unambiguous name |
| `%eviews` `%%eviews` | EconEnv | no official EViews IPython magic exists |
| `%econ` | EconEnv | namespaced, cannot collide |

If another extension already owns `%R`, EconEnv leaves it alone and reports
`already taken by another extension — use %Rec`.

---

## `%econ` — management

```
%econ status                          engine table
%econ engines                         detail, plus magic ownership
%econ versions                        version of each engine
%econ capabilities                    capability matrix
%econ models                          estimator × engine matrix
%econ doctor [engine] [--deep] [--json]
%econ start|restart <engine>
%econ stop [engine]
%econ reset [engine]
%econ config [key [value]] [--sources]
%econ snapshot [path] [--deep]
%econ push <engine> <name> [--as target]
%econ pull <engine> [name] [--as target]
%econ move <source> <target> <name>
%econ ols <formula> --data <df> [--engines a,b] [--vcov hc1] [--no-constant]
%econ eviews [task|find <term>]       EViews command lookup
%econ matlab [category|find <term>]   MATLAB command lookup
%econ matlab colab                    Colab local-runtime setup
%econ matlab export                   saving MATLAB output for publication
%econ export [help|formats]           what can be exported, and to what
```

Examples:

```python
%econ doctor eviews --deep
%econ config stata.edition mp
%econ config r.home "C:/Program Files/R/R-4.5.2"
%econ move stata r auto
%econ ols y ~ x1 + x2 --data df --engines python,r,stata
%econ snapshot ./environment.json
```

`--deep` on `doctor` starts each engine and runs a trivial command. It is
slower and it will launch Stata and EViews, so it is opt-in.

---

## `%%R` / `%%Rec` — R

```
%%Rec [-i NAME]... [-o NAME]... [-q] [--no-graphics] [-r]
```

| Flag | Effect |
|---|---|
| `-i NAME` | Push a Python object into R first. Repeatable. |
| `-o NAME` | Pull an R object back into Python afterwards. Repeatable. |
| `-q` | Suppress output. |
| `--no-graphics` | Do not open a plot device for this cell. |
| `-r` | Return the `ExecutionResult` instead of printing. |

```python
%%Rec -i df -o coef_table
fit <- lm(y ~ x1 + x2, data = df)
coef_table <- as.data.frame(summary(fit)$coefficients)
plot(fit, which = 1)
```

The plot is rendered inline. `coef_table` arrives in Python as a DataFrame with
the R term names as its index.

Line helpers:

```
%Rec <code>                 run one line
%Rec_pull <r object>        return it as a DataFrame
%Rec_push <py name> [as <r name>]
```

When rpy2 is installed, `%%R` is rpy2's own magic with its own flag set —
consult rpy2's documentation for it. `%%Rec` is always EconEnv's.

---

## `%%stata` — Stata

`%%stata` is PyStata's. Its full documentation is `%stata?` and StataCorp's
manual. EconEnv adds four helpers that cannot collide with it:

```
%stata_run / %%stata_run [-q] [-r]     run and get an EconEnv ExecutionResult
%stata_pull [frame]                    Stata's dataset as a DataFrame
%stata_push <df> [as <frame>]          load a DataFrame into Stata
%stata_matrix <name>                   r(table), e(b), e(V) ... as an ndarray
```

`%stata_matrix` and `%stata_pull` read through Stata's Function Interface, so
values keep full double precision. `display` would round to about nine
significant figures — enough to make two engines look like they disagree when
they do not.

---

## `%%eviews` — EViews

```
%%eviews [-i NAME]... [-o NAME]... [--page P] [--append] [--no-graphs] [-q] [-r]
```

| Flag | Effect |
|---|---|
| `-i NAME` | Push a DataFrame into a **new** workfile page first. |
| `--append` | With `-i`, write into the active page instead. |
| `-o NAME` | Pull the page back into Python afterwards. |
| `--page P` | `pageselect P` before running. |
| `--no-graphs` | Do not export graph objects. |
| `-q` / `-r` | Suppress output / return the `ExecutionResult`. |

```python
%%eviews -i quarterly -o fitted
equation eq1.ls y c x1 x2
eq1.fit fitted
graph g1.line y fitted
```

`g1` is exported to a temp file, displayed inline, and the file deleted.

Line helpers:

```
%eviews <command>
%eviews_get <expression>      evaluate a scalar or string
%eviews_pull [series names]   the active page as a DataFrame
%eviews_push <df> [--append]
%eviews_show [on|off]
```

`%eviews_get` adds the `=` prefix EViews requires for anything that is not a
series expression, so `%eviews_get @vernum` and `%eviews_get eq1.@r2` both
work. Without it EViews raises *"... is not a Genr or series expression
function"*.

---

## Errors

Bad arguments raise a readable `MagicArgumentError` with the usage line, not a
`SystemExit` that kills the cell:

```
%econ config
econ config: unrecognized arguments: --nope

usage: %econ config [key] [value] [--sources]
```

## `%%matlab` — MATLAB

```python
%%matlab -i df -o beta
fit = fitlm(df, 'y ~ x1 + x2');
beta = fit.Coefficients.Estimate;
```

| Flag | Meaning |
|---|---|
| `-i NAME` | push a Python object in (DataFrame, array, list, number, text) |
| `-o NAME` | bring a MATLAB variable back, as its natural Python type |
| `-q` | suppress output |
| `--no-graphs` | do not capture figures this cell draws |
| `--result` | return the `ExecutionResult` instead of displaying it |

`-i` and `-o` are typed both ways: a MATLAB scalar comes back as a number, a
matrix as a NumPy array, a table as a DataFrame; a Python list or array goes in
as a `double` column. The full tables are in
[engines/matlab.md](engines/matlab.md).

To find a MATLAB command without leaving the notebook:

```python
%econ matlab                     # 11 categories, 102 commands
%econ matlab timeseries          # unit roots, ARIMA, VAR
%econ matlab find cointegration  # search everything
```

Every entry names the toolbox it needs, because a function you have not licensed
fails with `Unrecognized function or variable` — which reads like a typo and is
not one.

**MATLAB is slow to start** — roughly a minute cold. The first cell that uses it
pays for the whole session; every later one is fast. That is also why
`%econ status` never starts it.

If MATLAB is already open, share it and EconEnv will attach instead of starting
a second copy:

```matlab
matlab.engine.shareEngine
```

```python
%econ config matlab.shared MATLAB_shared
```

## `%econ export` — results to publication formats

```python
%econ export cmp paper/table1 --formats tex,docx,xlsx --caption "Table 1"
```

| Flag | Meaning |
|---|---|
| `--formats` | comma-separated: `tex,docx,xlsx,csv,html,md,rtf` |
| `--style` | `journal` (default) or `full` |
| `--caption`, `--label` | passed through to LaTeX and Word |

See [export.md](export.md) for the full API.
