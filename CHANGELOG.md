# Changelog

All notable changes to EconEnv are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is
[semantic](https://semver.org/spec/v2.0.0.html).

## [0.1.1] — 2026-09-04

Bug fixes for three defects found by running EconEnv in a real notebook against
EViews 13, StataNow 19.5 and R 4.5.2. Two of them meant EViews produced no
visible output at all.

### Fixed

- **`%%eviews` printed nothing.** The adapter ran commands through the COM
  `Run` method, which executes a command but returns no text — EViews writes
  output to its own window, which is hidden. So `eq1.output` and `show eq1`
  completed successfully and displayed nothing. Display views are now frozen
  into a table object and read back cell by cell over COM, which needs no
  temporary file and no path quoting. A line is treated as a view only when it
  is `object.view` with no trailing arguments, or `show ...`; `equation eq1.ls
  y c x` is an action and still runs normally.
- **No EViews graph was ever captured.** The export path was built with
  `Path.as_posix()`, and EViews parses `"C:/Users/..."` as the drive-relative
  path `C:Users\...`. It wrote nowhere, reported success, and the adapter then
  found no file and returned `None`. Paths now use native separators. This
  contradicts the 0.1.0 note claiming EViews graphs were captured; they were
  not.
- **`%econ status` disagreed with itself about rpy2.** The banner does a real
  import, but the status column used `find_spec`, so an rpy2 that is installed
  yet cannot load R — common in conda environments — was reported as the active
  backend in the same session whose banner said "rpy2 not installed". The check
  now attempts the import once and caches the result.
- **`%econ status` reported the wrong EViews location.** Detection sorts
  installations newest-first, so on a machine with EViews 12, 13 and 14 the
  location column said "EViews 14" while `EViews.Manager` had actually bound to
  13. After connecting, the reported location is the installation whose version
  matches the running one.

### Notes

- 127 tests, up from 114. The new EViews tests need no EViews: they pin the
  decisions the adapter makes before it reaches COM, and the COM behaviour they
  encode was measured against EViews 13.

## [0.1.0] — 2026-09-04

First release. Execution, engine management, the data bridge, results, graphs,
diagnostics, snapshots and cross-engine OLS comparison.

### Added

**Core**
- `BaseEngine` contract and engine registry, extensible through the
  `econenv.engines` entry-point group; a third-party engine that fails to load
  is reported, not raised.
- Layered configuration: defaults < `~/.econenv/config.toml` < environment <
  runtime, with unknown keys rejected rather than silently stored.
- Full exception hierarchy; every engine error keeps the untouched vendor
  exception in `.raw` and usually carries a `.hint`.
- Logging with credential and serial-number redaction.

**Engines**
- **Python** — the host interpreter, exposed through the same interface as the
  others so it appears in status, snapshots and the comparison table.
- **R** — two backends. A persistent `Rterm`/`R` subprocess (the default,
  always available) and `rpy2` when it is importable. Where rpy2 is present its
  official `%R`/`%%R` magics are loaded rather than shadowed.
- **Stata** — PyStata delegation. Discovery validates the executable, not just
  the folder; editions BE/SE/MP detected; `%stata`/`%%stata`/`%mata` are
  StataCorp's own.
- **EViews** — direct COM automation via `comtypes`, Windows only. No
  dependency on `pyeviews`. (Output and graph capture were broken in this
  release; see 0.1.1.)

**Data**
- `push` / `pull` / `move` with `pandas.DataFrame` as the canonical interchange
  object; engine-to-engine transfers touch no file the user has to manage.
- Typed transports: Arrow feather for R where available, otherwise typed CSV
  with a JSON schema sidecar that restores factors, integers, dates and the
  empty-string vs missing distinction.
- `DatasetMetadata` carrying time variable, panel variable, frequency, labels
  and conversion history; inferred from a `DatetimeIndex` or a two-level
  `MultiIndex`.
- `ConversionReport` on every transfer; anything lossy warns, anything that
  would change a value raises.

**Results and models**
- `ExecutionResult`, `ModelResult` and `Figure`, all with rich Jupyter display.
- `ModelSpec` as an engine-neutral intermediate representation; non-additive
  formula terms are refused with an explanation rather than half-translated.
- Model registry and a capability matrix that combines declared support with
  runtime availability.
- `compare_ols` — the same specification across every available engine, with
  absolute and relative tolerances and the documented reasons the engines can
  legitimately differ.

**Tooling**
- `econenv` CLI and `%econ` magic sharing one service layer.
- `econenv doctor` — every warning and error carries a fix, enforced by a test.
- Environment snapshots and provenance records (code hash, data hash, versions,
  timing).
- 114 tests; unit tests need no commercial engine.

### Corrections to the original project brief

The brief asked for wrong assumptions to be fixed rather than implemented
literally. Four were:

- **`py2eviews` → `pyeviews`, and neither is used.** The maintained package is
  `pyeviews`; it fails to import on modern Python (`pkg_resources`). EconEnv
  talks to COM directly.
- **rpy2 is not the foundation.** It publishes no Windows wheels for any 3.6.x
  release, so the R engine defaults to a subprocess backend and uses rpy2 as an
  optional accelerator.
- **The EViews version reported is the connected one.** The generic
  `EViews.Manager` ProgID binds to whichever install registered last, which on
  a machine with EViews 12/13/14 was 13, not 14.
- **Graphs moved from v0.3 to v0.1.** Plot capture is a property of the
  transport layer built here; retrofitting it later would have meant touching
  every adapter twice.

Evidence for each is in
[`docs/audit/PHASE0_TECHNOLOGY_AUDIT.md`](docs/audit/PHASE0_TECHNOLOGY_AUDIT.md).

### Pre-release fixes found by clean-install testing

Installing the built wheel into an empty virtual environment — rather than
testing only against the development environment — caught two packaging defects
that would have shipped:

- `statsmodels` was not a core dependency, so `compare_ols` (the headline
  feature, and the first example in the README) silently produced a comparison
  table with the Python column missing. It is now a core dependency.
- `econenv doctor` returned exit code 1 on a perfectly good Python + R + Stata
  installation, because a missing `comtypes` was classified as an ERROR. A
  missing optional extra is now a WARNING when EViews is present and a SKIP when
  it is not, so `doctor` stays usable as a CI gate.

### Known limitations

- The rpy2 R backend is implemented but **not verified** — rpy2 is not
  installable on the development machine.
- Linux and macOS are supported by design but **not yet run** by the author.
- Only OLS is comparable across engines; `%econ models` shows the rest as
  `planned`.
- Provenance records exist but are not captured automatically per cell (v0.5).
- Stata value labels are not created from pandas categoricals (v0.2).
- EViews string (alpha) transfer is capped at 5000 rows.

Published to PyPI: <https://pypi.org/project/econenv/0.1.0/>

[0.1.1]: https://github.com/merwanroudane/econenv/releases/tag/v0.1.1
[0.1.0]: https://github.com/merwanroudane/econenv/releases/tag/v0.1.0
