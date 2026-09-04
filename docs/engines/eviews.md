# EViews

**Windows only.** Automation is COM-based, and COM does not exist on Linux or
macOS. On those platforms the EViews engine reports itself unavailable and
everything else works normally.

```bash
pip install "econenv[eviews]"    # adds comtypes
```

## How EconEnv connects

`EViews.Manager` → `GetApplication(code)` where code is `0` new, `1` either,
`2` existing. EconEnv defaults to **`new`**: it manages its own session rather
than attaching to a window you are working in, which avoids deadlocking on a
modal dialog you have open.

```python
%econ config eviews.instance either    # attach to a running EViews if there is one
%econ config eviews.progid EViews.Manager.14
%econ config eviews.show_window true
```

## `pyeviews` is not a dependency

The brief called it `py2eviews`; that name is obsolete. The maintained package
is `pyeviews`, and on a modern Python it **fails at import**:

```
>>> import pyeviews
ModuleNotFoundError: No module named 'pkg_resources'
```

`pyeviews/__init__.py` does `from pkg_resources import get_distribution` at
import time, and `pkg_resources` was removed from modern setuptools.

EconEnv therefore talks to COM directly. Its connection recipe
(`EViews.Manager` → `GetApplication`) is reused; nothing else is. If you have
`pyeviews` installed and working you can still use it alongside EconEnv —
`econenv doctor` reports its state either way, and nothing needs fixing.

## Four things measured on a live EViews

These are not from a doc page; they were run.

### 1. The ProgID may bind to the wrong version

On a machine with EViews 12, 13 **and** 14 installed, the generic ProgID
resolves to whichever install registered last — here, 13:

```
EViews.Manager     -> {A1B20F57-...}
                      InprocServer32  C:\Program Files\EViews 13\EViewsMgr.dll
                      ProgID          EViews.Manager.13
```

Two consequences.

**The version is knowable without starting EViews.** The CLSID carries the
server path and the versioned ProgID it resolves to, so `%econ status` reports
the real target — 13, not the newest install on disk — before anything is
launched, and confirms it against the connection once started.

**Versioned ProgIDs are `EViews.Manager.14`,** not `EViews14.Manager`. The
latter is registered on no machine; EconEnv looked for that form until 0.1.2
and so recommended pinning a ProgID that does not exist. To pin a version:

```python
%econ config eviews.progid EViews.Manager.14
```

### 2. `Get` needs an `=` prefix for non-series expressions

```python
app.Get("@vernum")     # raises: not a Genr or series expression function
app.Get("=@vernum")    # 13.0
```

Bare `Get` is evaluated as a series/genr expression. `%eviews_get` and
`engine.pull_scalar()` add the prefix for you.

Useful expressions:

| | |
|---|---|
| `@vernum` | version |
| `@wfname`, `@pagename` | workfile, page |
| `@pagefreq` | frequency letter |
| `@pagesmpl`, `@pagerange`, `@obsrange` | sample |
| `@otod(i)` | date label of observation *i* |
| `@wlookup("*","series")` | series names |
| `eq1.@coefs(i)`, `@stderrs`, `@tstats`, `@pvals`, `@r2`, `@rbar2`, `@regobs`, `@aic`, `@schwarz`, `@dw` | equation results |

`@lasterrornum` / `@lasterrortext` are **not** available as genr functions.
Error capture does not rely on them.

### 3. `Run` raises on failure, and the message is usable

```
COMError(-2147024809, ..., ('THIS_IS_BAD is not defined or is an illegal
                            command in "THIS_IS_BAD".', ...))
```

EconEnv reads `args[2][0]` and re-raises as `EngineExecutionError` with the
EViews text, the failing line, and how many commands ran first:

```
[eviews] THIS_IS_BAD is not defined or is an illegal command in "THIS_IS_BAD".
  in: this_is_bad
Hint: 3 of 5 command(s) ran before this one.
```

Cells are run line by line for exactly this reason.

### 4. `PutSeries` with a plain list silently destroys the data

```python
app.PutSeries("zz", [1.0, 2.0, 3.0])   # returns without error
app.GetSeries("zz")   ->  (None, None, None)
```

Every value gone, no exception, no warning. Marshalling through a
`comtypes.automation.VARIANT` works:

```python
v = VARIANT(); v.value = [1.0, 2.0, 3.0]
app.PutSeries("zz", v)
app.GetSeries("zz")   ->  (1.0, 2.0, 3.0)
```

EconEnv always marshals through a VARIANT **and reads every numeric series back
to verify it**. A frame that arrives all-NA raises `DataTransferError` instead
of becoming a regression on empty data. There is a unit test that reproduces the
trap against a fake COM object, so a regression here fails CI on Linux.

## Other behaviours

* `GetSeries` returns `None` for `NA` → mapped to `NaN`.
* `GetGroup` needs a BSTR SAFEARRAY and rejects a Python list, so transfers go
  series by series. Simpler and it sidesteps the marshalling trap.
* There is **no `Quit`** on the interface. `stop()` releases the COM reference
  and collects.
* *"EViews is currently busy"* is a timing condition — another session holds it,
  or a modal dialog is open. EconEnv retries with backoff
  (`eviews.busy_retries`, default 5) before reporting it. A genuine syntax error
  raises on the first attempt and is not retried.

## Workfiles

A dated pandas index becomes a dated page:

```python
df.index = pd.period_range("2000Q1", periods=40, freq="Q").to_timestamp()
econenv.push("eviews", "wf", df)      # create Q 2000Q1 2009Q4
```

and the dates come back through `@otod` on pull. Without a recognised date
index the page is created undated and you get a warning, because EViews
time-series operators then treat observations as unordered.

```python
%econ config eviews.graphics svg     # png | svg | off
%econ config eviews.width 8
```

Graphs are exported to a private temp directory, read into memory, displayed,
and the file deleted immediately.

## How output gets back to the notebook

The COM `Run` method executes a command but returns no text: EViews writes
output to its own window, and EconEnv keeps that window hidden. So text has to
be pulled back deliberately.

A line that names a **display view** — `object.view` with no trailing
arguments, or `show something` — is frozen into a table object and read back
cell by cell:

```python
%%eviews
equation eq1.ls y c x     # an action: arguments follow, so it just runs
eq1.output                # a view: frozen, read back, printed
```

```
Dependent Variable: Y
Method: Least Squares
Sample: 1 100
Included observations: 100

Variable    Coefficient  Std. Error  t-Statistic  Prob.

C           5.044621     0.105875    47.64697     0.0000
X           2.056953     0.112013    18.36358     0.0000

R-squared   0.774827     Mean dependent var       4.894231
...
```

The distinction matters: freezing an action would silently skip it. So
`equation eq1.ls y c x` and `eq1.makeresids r1` carry arguments and are run
normally, while `eq1.output`, `x.stats` and `show eq1` are captured. If a freeze
fails the line is simply run instead, so an unrecognised view never breaks a
cell.

The frozen table is deleted immediately afterwards, and the raw grid stays on
`result.metadata["views"]` if you want the cells rather than the text.

A view does not always freeze into a table. A plotting view freezes into a
**graph**, which has no rows and is exported as an image instead:

```python
%%eviews
x.line          # a view: no named graph object is created
```

This matters because `x.line` leaves nothing behind in the workfile. Capturing
figures by sweeping for named graph objects finds it only when you name one
yourself (`graph g1.line x`), which is why plots written the ordinary EViews way
showed nothing before 0.1.3.

Each named graph is shown once, not again under every later cell. `show g1`
always re-exports, and `--no-graphs` suppresses images while keeping the text.

The third way to plot is a standalone **graph command**:

```python
%%eviews
line x          # also: scat x y, bar(l) x, xyline a b, boxplot x
```

This is neither a view nor an object — EViews rejects `freeze(t) line x` with
*"LINE is not a view"*, and it leaves nothing in the workfile. EconEnv runs it
as `graph <temp>.line x`, exports the result and deletes the temporary object,
so all three forms render:

| You write | What it is | How it is captured |
|---|---|---|
| `line x` | command | run as a temporary graph object |
| `x.line` | view | frozen, exported as an image |
| `graph g1.line x` | object | exported by the end-of-cell sweep |

## What a view freezes into

A view becomes one of four object types, and each is read differently:

| Object | Example | Read as |
|---|---|---|
| table | `eq1.output` | cells, over COM — no temporary file |
| graph | `x.line` | PNG or SVG |
| text | `eq1.representations` | exported text |
| spool | `g2.coint(e)` | exported text |

If a view freezes but none of the four can read it, you get a warning naming
the line. EconEnv never runs a display command and shows nothing.

## Verified graph and output forms

Every entry below was run against EViews 13 through `%%eviews`. **P** = plot,
**T** = text or table.

**Before estimation**

| Series views | Group views | Commands |
|---|---|---|
| `x.line` P `x.bar` P `x.area` P | `g.line` P `g.scat` P | `line x` P `scat x y` P |
| `x.spike` P `x.dot` P `x.seasplot` P | `g.xyline` P `g.scatmat` P | `bar x` P `xyline x y` P |
| `x.hist` P `x.distplot` P | `g.boxplot` P `g.distplot` P | `boxplot x` P `area x` P |
| `x.boxplot` P `x.qqplot` P | `g.stats` T `g.cor` T | `spike x` P `qqplot x` P |
| `x.correl` T `x.stats` T | `g.coint(e)` T | `distplot x` P `scatmat x y` P |
| `x.uroot` T `x.bdstest` T | | |

**After estimation**

| Equation | Stability | ARMA / GARCH / VAR |
|---|---|---|
| `eq.resids` P `eq.hist` P | `eq.rls(c)` P `eq.rls(r)` P | `eq.arma(type=root)` P |
| `eq.output` T `eq.coefcov` T | `eq.rls(q)` P `eq.rls(o)` P | `eq.arma(type=acf)` P |
| `eq.correl` T `eq.correlsq` T | `eq.rls(n)` P | `eq.arma(type=imp)` P |
| `eq.archtest(1)` T `eq.white` T | | `eqg.garch` P `eqg.resids` P |
| `eq.reset(1)` T | | `v.impulse` P `v.correl` P |
| `eq.representations` T | | `v.output` T `v.decomp` T `v.arroots` T |

Two known gaps, both EViews behaviour rather than EconEnv:

- `eq.fit(g) yf` and `eq.forecast(g) yf2` create their series correctly, but the
  graph the `g` option displays belongs to no object and cannot be exported.
  Plot the result instead: `line yf`.
- `eq.rls(s)` (CUSUM) is refused by EViews in batch mode — *"Incomplete command
  in batch mode"*. `eq.rls(q)`, the CUSUM of squares, works.

Very large views are capped:

```python
%econ config eviews.max_view_cells 50000   # default 20000
```

Reading happens one cell per COM call, so an unbounded table would be slow; when
the cap trims a view you get a warning saying so rather than silent truncation.

## EViews' own Jupyter kernel

EViews 14 ships `XeusEViews.exe`. It is a real Jupyter kernel and it works —
but it is a *separate* kernel, so using it means a second notebook, which is the
problem EconEnv exists to solve. Documented here as an alternative, not used.
