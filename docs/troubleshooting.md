# Troubleshooting

Start with `econenv doctor`. Every warning and error there names the fix.

---

## Installation

**`No module named 'econenv'` after `pip install -e .`**
Hatchling's editable build needs `editables`: `pip install editables`.

**`econenv doctor` crashes with `UnicodeEncodeError`**
Fixed in 0.1.0 — the CLI reconfigures stdout to UTF-8 with `errors="replace"`,
and falls back to ASCII markers when the console cannot render tick marks. If
you still see it, you are on an older build.

---

## R

**"No R installation found"**
Set it explicitly:
```python
%econ config r.home "C:/Program Files/R/R-4.5.2"
```
or export `R_HOME`. R does not need to be on `PATH` — EconEnv calls the
executable by full path.

**"R started but never reported ready"**
Usually a startup file erroring. Try running `Rterm --vanilla` yourself. EconEnv
starts R with `--vanilla`, so `.Rprofile` and `.RData` are ignored; if plain
`Rterm --vanilla` also hangs, the R installation is the problem.

**"The R session died while running this cell"**
R crashed — commonly a segfault in a compiled package. `%econ restart r`.
Everything defined before the crash is gone.

**"R did not finish within 300s"**
```python
%econ config core.timeout 1800
```

**Multiple R versions warning**
EconEnv picks the newest. Pin one with `r.home` if you need a specific version.

**A blank plot appears after every R cell**
Fixed in 0.1.0 — device stub files below 512 bytes are skipped.

**Types come back wrong from R**
Install R's `arrow` package for the exact binary path:
```r
install.packages("arrow")
```
The CSV fallback needs `jsonlite` for the schema sidecar; without it EconEnv
raises a clear message rather than silently losing types.

**rpy2 will not install on Windows**
It does not have Windows wheels. You do not need it — the subprocess backend is
the default and supported route on Windows.

---

## Stata

**"none contains utilities/pystata"**
PyStata ships with Stata **17 and later**. Older Stata cannot be driven from
Python at all.

**"`pystata.config.init('mp')` failed"**
The edition must match your licence:
```python
%econ config stata.edition se        # or be, or mp
```

**"frame ... already defined r(110)"**
Fixed in 0.1.0 — EconEnv now leaves the frame before recreating it.

**Stata's numbers differ from Python's at the ninth decimal**
Fixed in 0.1.0. `display` rounds; EconEnv now reads through Stata's Function
Interface, which returns the stored doubles. If you read values yourself with
`display`, use `%21x` or `sfi`.

**`%econ stop stata` then `%econ start stata` behaves oddly**
PyStata can only be initialised once per process. Stopping drops EconEnv's
handles but the Stata engine stays initialised — which is deliberate, because
calling `pystata.config.shutdown()` would make it unrecoverable without a new
kernel. To change edition, restart the kernel.

---

## EViews

**"EViews is currently busy"**
Something else holds the automation server — another session, or a modal dialog
open in the EViews window. EconEnv retries with backoff, then reports it. Close
any dialog; raise `eviews.busy_retries` on a slow machine. EconEnv defaults to
its **own** instance (`eviews.instance = new`); if you set it to `either` you
will attach to whatever is running, dialogs included.

**"Could not connect to EViews through COM"**
Open EViews once as the current user, so it registers itself and validates the
licence. Then retry.

**It connected to EViews 13 but I have 14 installed**
The generic `EViews.Manager` ProgID binds to whichever install registered last.
```python
%econ config eviews.progid EViews.Manager.14
```
`%econ status` always shows the version actually connected, never the newest on
disk.

**`import pyeviews` fails with `No module named 'pkg_resources'`**
It is broken on modern Python — and EconEnv does not use it. Ignore it, or
uninstall it. Nothing in EconEnv depends on it.

**All my values arrived in EViews as NA**
This should be impossible in 0.1.0: every numeric push is read back and
verified, and a mismatch raises `DataTransferError`. If you see it anyway,
please file a bug — it means the COM VARIANT marshalling regressed.

**Lags and `d()` behave as if the data were unordered**
Your frame had no recognised date index, so the workfile page was created
undated — you will have seen a warning. Give the frame a `DatetimeIndex` or
`PeriodIndex` before pushing.

**EViews is unavailable on Linux/macOS**
Correct, and not fixable: automation is COM. The rest of EconEnv works.

---

## Magics

**`%%R` is rpy2's, not EconEnv's**
By design. `%%Rec` is always EconEnv's. `%econ engines` shows who owns what.

**`%%R` says "already taken by another extension"**
Another extension registered it first and EconEnv will not shadow it. Use
`%%Rec`.

**A magic argument error kills my cell**
It should not — EconEnv's parser raises `MagicArgumentError` with the usage
line instead of exiting. If you see a raw `SystemExit`, it came from another
extension's magic.

---

## Still stuck

```bash
econenv doctor --deep --json > doctor.json
econenv snapshot snapshot.json
```

Attach both to an issue at
<https://github.com/merwanroudane/econenv/issues>. Neither file contains
licence keys or serial numbers — EconEnv's logging redacts anything that looks
like one.
