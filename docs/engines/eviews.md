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
%econ config eviews.progid EViews14.Manager
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

```
EViews.Manager          -> registered
EViews14.Manager        -> NOT registered
```

but the object identifies as `EViews.Application.13` on a machine with EViews
12, 13 **and** 14 installed. The generic ProgID resolves to whichever install
registered last.

`%econ status` therefore always shows the version EconEnv **connected to**, not
the newest found on disk. Pin one with `eviews.progid` if it matters.

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

## EViews' own Jupyter kernel

EViews 14 ships `XeusEViews.exe`. It is a real Jupyter kernel and it works —
but it is a *separate* kernel, so using it means a second notebook, which is the
problem EconEnv exists to solve. Documented here as an alternative, not used.
