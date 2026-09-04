# Phase 0 — Repository & Technology Audit

**Project:** EconEnv · **Author:** Dr Merwan Roudane · **Date:** 2026-09-04
**Audit machine:** Windows 11 Pro Education 10.0.26200, AMD64, Python 3.11.0

Everything below was **measured on this machine**, not assumed. Where the
project brief made a technical assumption that turned out to be wrong or
outdated, it is flagged **[CORRECTION]** — the brief explicitly asks for that
rather than literal execution.

---

## 1. Repository state

| Item | Finding |
|---|---|
| `github.com/merwanroudane/econenv` | Exists, `default_branch = main`, `size = 0` → **empty repository** |
| Local working copy | Was untracked; `git init` performed in this phase |
| PyPI name `econenv` | **Available** (HTTP 404 on `pypi.org/pypi/econenv/json`) |
| PyPI name `EconEnv` | Available (PyPI normalises to `econenv`) |

No name change is needed. `EconEnv` (branding) / `econenv` (distribution) hold.

---

## 2. Host stack

| Component | Version |
|---|---|
| Python | 3.11.0 |
| IPython | 9.9.0 |
| JupyterLab | 4.5.6 |
| Notebook | 7.5.5 |
| pandas / numpy | 2.3.3 / 2.2.6 |
| pyarrow | 23.0.1 |
| statsmodels | 0.14.6 |
| pytest / ruff / mypy | 9.0.3 / 0.16.3 / 2.3.1 |

IPython 9.x is the target. Its extension API (`load_ipython_extension`,
`@magics_class`, `line_cell_magic`, `needs_local_scope`) is stable and is what
EconEnv builds on. **No custom Jupyter kernel** is written — brief §2/§52 agreed.

---

## 3. Engines physically present on this machine

| Engine | Installed | Notes |
|---|---|---|
| R | 4.4.3 **and** 4.5.2 | `R_HOME` **not set**; `R`/`Rscript` **not on PATH** |
| Stata | 17, 18, **StataNow 19.5 MP** | `StataMP-64.exe` only in `StataNow19`; `Stata18` contains **no `.exe`** (partial install) |
| EViews | 12, 13, **14** | `C:\Program Files\EViews 14\EViews14.exe` |

Rtools 4.4 and 4.5 are present. This machine can run the **full four-engine MVP
acceptance test (§46) for real** — no mocking required for the proof of concept.

---

## 4. Stata — verified working

`pystata` is **not** a PyPI package. It ships inside the Stata installation at
`<STATA_HOME>\utilities\pystata` and is put on `sys.path` manually or by
`stata_setup` (0.1.3, installed).

- Bundled `pystata` version on this machine: **0.1.2** (StataCorp LLC)
- `pystata.config.init('mp', splash=False)` → succeeded
- `c(stata_version)` = **19.5**, `c(edition_real)` = **MP**
- `stata.pdataframe_to_data(df, force=True)` → OK
- `stata.run("regress y x")` → full formatted output captured
- `stata.pdataframe_from_data()` → round-trip returned floats **and** the string
  column intact

**Official magics confirmed present** in `pystata/ipython/stpymagic.py`:
`%stata` / `%%stata`, `%mata` / `%%mata`, `%pystata`, `%help`, plus a Stata
tab-completer.

**[DECISION]** Brief §8/§61 says do not reimplement what PyStata gives.
EconEnv **delegates** to `pystata`'s own magics via
`pystata.ipython.stpymagic.load_ipython_extension`. EconEnv's Stata engine owns
*discovery, edition detection, configuration, lifecycle and result wrapping* —
not the magic itself.

---

## 5. EViews — verified working, several traps found

Automation is through **COM** via `comtypes` (1.4.16, installed).

### 5.1 Registered ProgID points at the wrong version — [CORRECTION]

```
EViews.Manager          -> {A1B20F57-078C-4677-9D9D-FAF6C9E79190}   registered
EViews12/13/14.Manager  -> NOT REGISTERED
```

The live object identifies itself as **`EViews.Application.13`** even though
EViews 14 is installed. The generic ProgID resolves to whichever install
registered last; `Get("=@vernum")` returned **13.0**.

→ EconEnv must **report the version it actually connected to**, never the version
found on disk, and must let the user pin a ProgID.

### 5.2 `IApplication` surface (measured)

```
Run, Get, Put, GetSeries, PutSeries, GetGroup, GetGroupEx, PutGroup,
Lookup, ArrayToList, ListToArray, Show, Hide, ShowLog, HideLog
```

There is **no `Quit`/`Close` method** — shutdown is by releasing the COM
reference (what `pyeviews.Cleanup()` does).

### 5.3 `Get` needs an `=` prefix for anything that is not a series — [CORRECTION]

`Get("@lasterrornum")` raises `... is not a Genr or series expression function`.
Bare `Get` is evaluated as a **series/genr** expression. Scalars and strings need
`Get("=expr")`:

| Expression | Result |
|---|---|
| `=@vernum` | `13.0` |
| `=@wfname` / `=@pagename` | `'UNTITLED'` / `'Untitled'` |
| `=@pagefreq` | `'Q'` |
| `=@pagesmpl` / `=@pagerange` | `'2000Q1 2001Q4'` |
| `=@obsrange` / `=@obssmpl` | `8.0` |
| `=@otod(1)` | `'2000Q1'` (observation → date label) |
| `=@wlookup("*","series")` | `'S2 X'` |
| `=eq1.@coefs(i)`, `@stderrs`, `@tstats`, `@pvals`, `@regobs`, `@rbar2`, `@ncoef` | numbers |

`@lasterrornum` / `@lasterrortext` are **not** available as genr functions here —
they are program-level. Error capture must not rely on them.

### 5.4 `Run` raises on failure — this is the error channel

```
app.Run('this_is_bad')
_ctypes.COMError: (-2147024809, ...,
  ('THIS_IS_BAD is not defined or is an illegal command in "THIS_IS_BAD".',
   'EViews.Application.13.EvaluateSeries', None, 0, None))
```

`args[2][0]` carries a **human-readable EViews message**. EconEnv's adapter reads
it and re-raises as `EngineExecutionError`, keeping the raw `COMError`.

### 5.5 `PutSeries` with a plain Python list silently writes all-NA — [CRITICAL]

```python
app.PutSeries("zz", [1.0, 2.0, 3.0, 4.0, 5.0])   # "succeeds"
app.GetSeries("zz")   ->  (None, None, None, None, None)      # data lost
```

Marshalling through a `comtypes.automation.VARIANT` works:

```python
v = VARIANT(); v.value = [1.0, 2.0, 3.0, 4.0, 9.0]
app.PutSeries("zz2", v)
app.GetSeries("zz2")  ->  (1.0, 2.0, 3.0, 4.0, 9.0)           # correct
```

This is exactly the "silent lossy conversion" the brief bans in §11. The EViews
bridge **must** marshal through `VARIANT` and **must** verify what landed.

`GetSeries` returns `None` for `NA`, mapping cleanly to `NaN`.
`GetGroup` rejects a plain Python list of names (`One of the seriesNames in the
array was empty`) — it wants a BSTR SAFEARRAY. EconEnv uses per-series
`GetSeries`/`PutSeries` instead: correct, and it avoids the marshalling trap.

### 5.6 `pyeviews` 1.0.5 is broken on this Python — [CORRECTION]

```
import pyeviews
ModuleNotFoundError: No module named 'pkg_resources'
```

`pyeviews/__init__.py` does `from pkg_resources import get_distribution` at
import time; `pkg_resources` is gone from modern setuptools, so the package is
unimportable on a clean Python 3.11+ environment.

The brief says **`py2eviews`** — that name is **obsolete**; the maintained
package is **`pyeviews`**.

→ **Decision:** EconEnv talks to EViews COM **directly** and does **not** depend
on `pyeviews`. Its API (`GetEViewsApp`, `Run`, `Get`, `PutPythonAsWF`,
`GetWFAsPython`, `Cleanup`) is documented as an optional interop path only. The
connection recipe we reuse is `EViews.Manager → GetApplication(0|1|2)`
(new / either / existing).

### 5.7 EViews 14 ships its own Jupyter pieces

`C:\Program Files\EViews 14\` contains `XeusEViews.exe`, `EViewsPy3Conn.exe`,
`EViewsRConn.exe`. `XeusEViews` is EViews' **own** Jupyter kernel — a *separate
kernel*, i.e. exactly what brief §7/§45 rules out for v0.1 (it would mean a
second notebook, not one notebook). Documented as an alternative, not used.

---

## 6. R — the brief's assumption needs correcting — [CORRECTION]

The brief assumes `rpy2` and its `%R`/`%%R` magics are the answer. On Windows
they are not reliably installable:

- `rpy2` latest = **3.6.7**, `requires_python >= 3.9`
- **No Windows wheels** for any 3.6.x release — checked 3.6.2 … 3.6.7, all
  source-only. A source build needs Rtools + R headers and breaks often.
- `rpy2` is **not** currently importable in this environment.

R itself is fully usable here (4.5.2) with `jsonlite`, `data.table`, `haven`,
`readr`, `ggplot2`, `svglite` among 529 installed packages (`arrow` is **not**).

**Decision — two-backend R engine:**

1. **`subprocess` backend (default, always available).** One long-lived
   `R --vanilla --no-echo` child driven over stdin/stdout with unique sentinel
   markers per execution. Persistent session, no compiler, identical on
   Windows/Linux/macOS. Plots to an `svglite`/`png` device in a temp dir,
   displayed, then cleaned up.
2. **`rpy2` backend (optional, auto-detected).** When `rpy2` *is* importable
   (typical on Linux/macOS), EconEnv **loads rpy2's own `%R`/`%%R` magics rather
   than shadowing them** — brief §7 and §3.

The `%%R` name collision is handled explicitly: EconEnv always registers `%%Rec`
and claims `%%R` **only if nothing else already owns it**; `%econ engines`
reports which implementation is live.

**Data bridge for R:** tiered, never bare CSV — arrow feather (if the R `arrow`
package is present) → **typed CSV + JSON schema sidecar** written/read with
`data.table::fwrite`/`fread`, restoring factors, dates, integer-vs-double and
`NA` exactly.

---

## 7. Risk register

| # | Risk | Severity | Mitigation in the design |
|---|---|---|---|
| R1 | `PutSeries` silent all-NA | **Critical** | VARIANT marshalling + post-write verification |
| R2 | Generic `EViews.Manager` binds to the wrong version | High | Report the *connected* version; ProgID pinning |
| R3 | `pyeviews` unimportable | High | Zero dependency on it; direct COM |
| R4 | `rpy2` not installable on Windows | High | Subprocess R backend as default |
| R5 | `pystata` not on PyPI, path varies | Medium | Discovery + `stata_setup` + config override |
| R6 | Multiple Stata installs, one broken | Medium | Discovery validates the executable, not the folder |
| R7 | COM is Windows-only | Medium | EViews reports `available=False` elsewhere; package still installs |
| R8 | Long-lived engines leak processes | Medium | `atexit` + explicit `stop`/`reset` |
| R9 | Arbitrary code execution is the point of the tool | High | No implicit execution; no shell-string interpolation of user data; `tempfile` dirs |

---

## 8. Dependency decision

**Core (hard):** `pandas`, `numpy`, `ipython`.
**Reused, never reimplemented:** `pystata` (Stata magics + data API), `rpy2`
(when present), `comtypes` (COM plumbing).
**Written by us:** engine abstraction, registry, discovery, diagnostics, R
subprocess backend, EViews COM adapter + magics, data bridges, result objects,
model spec/comparison, CLI.

**Extras:** `[r]`, `[stata]`, `[eviews]` (Windows only), `[arrow]`, `[all]`,
`[dev]`.

---

## 9. Roadmap adjustment proposed

The brief's v0.1 → v1.0 ladder is kept, with one change: **fold "graphs" forward
from v0.3 into v0.2**, because plot capture for R and EViews is a property of the
execution/transport layer built in v0.2 anyway, and retrofitting it later would
mean touching every adapter twice.
