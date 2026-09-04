# R

## Two backends

### `subprocess` — the default, always available

One long-lived `Rterm` (Windows) or `bin/R` (POSIX) child process, fed over
stdin. Persistent session, no compiler, identical behaviour on all three
platforms.

Per cell: your code is written to a temp file; R's stdout and message streams
are sunk to a private file; `source()` runs it inside `withCallingHandlers` so
warnings and messages are captured separately from output; a status file records
`status`, `error`, `warning`, `message` and `plot`; then a one-time token is
printed so the Python side knows the cell finished. Output is captured exactly
and cannot interleave with the next cell.

### `rpy2` — used automatically when importable

In-process and faster. When rpy2 is present EconEnv also loads **rpy2's own**
`%R` / `%%R` magics instead of shadowing them.

```python
%econ config r.backend subprocess    # auto | subprocess | rpy2
```

## Why rpy2 is not a requirement

The original project brief assumed rpy2. It cannot be the foundation on
Windows:

* rpy2 3.6.x publishes **no Windows wheels** — checked 3.6.2 through 3.6.7, all
  source-only.
* A source build needs Rtools plus R headers and breaks often.
* The author's own platform is Windows.

Making the flagship R integration depend on a package that does not install on
the primary target would be a design flaw, so the subprocess backend is the
default and rpy2 is an optional accelerator. On Linux and macOS, where rpy2
installs cleanly, it is picked up automatically.

`econenv doctor` reports which backend is live and why.

## Discovery

`R_HOME` → `PATH` → the Windows registry (`HKLM\SOFTWARE\R-core\R`) → the usual
install roots. Newest version wins; `doctor` warns when several are installed.

```python
%econ config r.home "C:/Program Files/R/R-4.5.2"
```

On Windows the subprocess backend needs **`Rterm.exe`**, not `R.exe` — plain
`R.exe` is a launcher that can spawn its own console instead of talking to the
pipe. Discovery looks for `bin/x64/Rterm.exe` first.

## Data transfer

Two transports, chosen automatically:

**Arrow feather** when `pyarrow` is importable in Python *and* the `arrow`
package is installed in R. Binary, typed, fastest.

**Typed CSV + JSON schema sidecar** otherwise — and deliberately not "just
CSV". The data goes out with an explicit `__ECONENV_NA__` sentinel, so an empty
string stays an empty string rather than becoming a missing value, and a
companion schema records each column's logical type, factor levels and
ordering. R re-applies those on arrival; the reverse trip does the same coming
back.

```python
%econ config r.transfer feather      # auto | feather | csv
```

Installing R's `arrow` package is worth it for large frames:

```r
install.packages("arrow")
```

The CSV path uses `data.table::fread`/`fwrite` when available and base R
otherwise, and needs `jsonlite` for the schema sidecar unless `arrow` is
present.

## Plots

```python
%econ config r.graphics svg     # svg | png | off
%econ config r.width 8
%econ config r.height 5
```

`svglite` is used when installed, base `grDevices::svg` otherwise. Opening a
device writes the file immediately, so a cell that draws nothing leaves a
header-only stub behind — EconEnv skips files below 512 bytes rather than
putting a blank frame in your notebook after every non-plotting cell.

## Row names

Meaningful row names survive the trip. `coef(summary(fit))` uses the term names,
and they come back as the pandas index:

```python
%%Rec -i df -o ct
fit <- lm(y ~ x1 + x2, data = df)
ct <- as.data.frame(coef(summary(fit)))
```

```
             Estimate  Std. Error   t value      Pr(>|t|)
(Intercept)  1.995567    0.048424  41.21018  3.774617e-33
x1           0.456617    0.053706   8.50208  2.531838e-10
```

Default `1:n` row names are not promoted — they carry no information.

## Errors, warnings and messages

Kept separate, as R keeps them:

```python
result = engine.execute('warning("mind out"); message("fyi"); cat("body")')
result.stdout    # 'body'
result.warnings  # ['mind out']
result.stderr    # 'fyi'
```

An error raises `EngineExecutionError` carrying R's own `conditionMessage`, and
**the session survives** — variables defined before the error are still there.
`%econ restart r` gives you a clean one.

## Timeouts

```python
%econ config core.timeout 900        # seconds, per cell
```

On timeout you get `EngineTimeoutError` telling you how to raise it. If the R
process has died you get `SessionError` telling you to restart.

## IRkernel

IRkernel is R's own Jupyter kernel. It is excellent and completely legitimate —
but it is a *separate kernel*, so a notebook using it is an R notebook, not a
polyglot one. Use IRkernel when you want a pure-R notebook; use EconEnv when
you want R alongside Python, Stata and EViews in the same kernel.


## rpy2 on Windows

You do not need rpy2. EconEnv's subprocess backend gives you `%R`, `%%R`, data
transfer and plots without it, and is the supported route on Windows.

If you want rpy2 anyway — for its official magics, or slightly faster
transfers — PyPI is the wrong place to get it: there are no Windows wheels for
any 3.6.x release, so `pip install rpy2` either fails or leaves you with an old
version built for an older Python. That produces an rpy2 that is *present* but
raises on import, typically:

```
ImportError: cannot import name 'SexpVectorCCompatibleAbstract'
    from 'rpy2.rinterface_lib.sexp'
```

`econenv doctor` reports that case as **installed but cannot be imported**,
rather than as missing, and gives the repair:

```bash
pip uninstall -y rpy2
conda install -c conda-forge rpy2
```

conda-forge does build rpy2 for Windows — 3.6.4 has builds for Python 3.10
through 3.14.

**The catch, and it matters.** conda-forge's rpy2 brings its own R with it
(the `r44` in the build string means R 4.4). That is a second R, separate from
any R already installed under `C:\Program Files\R`. Packages you installed in
your existing R will not be visible to the rpy2 backend, and EconEnv's
subprocess backend will still use the R it discovered on the system — so the
two backends can see different libraries.

If that sounds like more trouble than it is worth, it usually is. Stay on the
subprocess backend:

```python
%econ config r.backend subprocess
```
