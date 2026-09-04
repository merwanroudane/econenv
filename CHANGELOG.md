# Changelog

All notable changes to EconEnv are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is
[semantic](https://semver.org/spec/v2.0.0.html).

## [0.1.5] — 2026-09-04

A full audit of EViews graph and output forms, pre- and post-estimation,
instead of fixing them one report at a time. 44 forms were run against
EViews 13 through `%%eviews`; 40 already worked, 4 did not.

### Added

- **Text and spool views are captured.** A view freezes into one of four object
  types, and only two were handled. `eq1.representations` freezes into a
  **text** object and `g2.coint(e)` — the Johansen cointegration test — into a
  **spool**; neither has cells to read, so both produced nothing at all. They
  are now exported and read back: the Johansen output returns 5,501 characters
  where it previously returned an empty cell.
- **A verified capability matrix** in `docs/engines/eviews.md`, listing every
  pre- and post-estimation form that was actually run, marked plot or text.

### Fixed

- **No display command can fail silently any more.** If a line freezes as a
  view but none of the four readers can make sense of it, the result carries a
  warning naming the line and pointing at the issue tracker. Silence was the
  failure mode behind every EViews report in 0.1.0 through 0.1.4.

### Verified

Plots, before estimation: `line`, `bar`, `area`, `spike`, `dot`, `seasplot`,
`hist`, `distplot`, `boxplot`, `qqplot`, `scat`, `xyline`, `scatmat` — as
series views, as group views and as standalone commands.

Plots, after estimation: `resids`, `hist`, recursive least squares
`rls(c|r|q|o|n)`, `arma(type=root|acf|imp)`, GARCH conditional variance, VAR
impulse responses and residual correlograms.

Tables and text: `output`, `coefcov`, `correl`, `correlsq`, `stats`, `uroot`,
`bdstest`, `archtest`, `white`, `reset`, `representations`, `coint`, VAR
`decomp` and `arroots`.

Two gaps remain, both EViews behaviour rather than EconEnv, and both
documented: the graph shown by `eq.fit(g)` / `eq.forecast(g)` belongs to no
object and cannot be exported (plot the resulting series instead), and
`eq.rls(s)` — CUSUM — is refused by EViews in batch mode, though `rls(q)`,
CUSUM of squares, works.

### Notes

- 150 tests, up from 147.

Published to PyPI: <https://pypi.org/project/econenv/0.1.5/>

## [0.1.4] — 2026-09-04

`line x` — the most direct way to plot in EViews — still produced no graph.

### Fixed

- **Standalone graph commands showed nothing.** `line x`, `scat x y`,
  `bar(l) x` and the rest are neither views nor objects: EViews rejects
  `freeze(t) line x` with "LINE is not a view", and a bare `line x` leaves
  nothing in the workfile — the graph listing is identical before and after.
  So there was no view to freeze and no object to sweep for. Such a command is
  now run in its object form, `graph <temp>.line x`, exported, and the
  temporary object deleted. Options are preserved: `bar(l) x` works.

  0.1.3 fixed the *view* form (`x.line`); this covers the *command* form. Both
  now render.

### Notes

- 147 tests, up from 135.
- Verified through the `%%eviews` magic against EViews 13, using the reported
  cell verbatim: `wfcreate u 100` / `series x = nrnd` / `line x` returns a
  30 KB PNG. `scat x y` and `bar(l) x` render, a table and a plot in one cell
  return both, a cell with a series named `line_test` produces no spurious
  figure, and `--no-graphs` still suppresses images.

Published to PyPI: <https://pypi.org/project/econenv/0.1.4/>

## [0.1.3] — 2026-09-04

EViews plots made the ordinary EViews way produced nothing. Reported from a
notebook where the estimation table rendered correctly but no graph ever
appeared.

### Fixed

- **`x.line`, `x.hist` and every other plotting view showed nothing.** In
  EViews a plot is usually a *view*, not an object: `x.line` draws a graph but
  leaves no named graph behind. EconEnv captured figures by sweeping the
  workfile for named graph objects, so there was nothing to find. Worse, 0.1.1
  froze such a line, discovered it was not a table, and dropped it. A frozen
  view is now read as a table when it has rows and exported as an image when it
  does not — so `x.line` returns a PNG.
- **`show g1` displayed the same graph twice.** The view path keeps the name as
  typed, the workfile sweep reports EViews' own casing (`G1`), so the
  deduplication missed. It is now case-insensitive.
- **One plot reappeared below every later cell.** The sweep exported every
  graph in the workfile on every execution, with no memory of what had already
  been shown. It now emits each graph once; an explicit `show` still always
  exports.

### Notes

- 135 tests, up from 130.
- Verified end to end through the `%%eviews` magic in a live IPython session
  against EViews 13: an estimation-plus-plot cell returns both the table and a
  PNG, a later cell adds no stale figures, and `--no-graphs` still suppresses
  images while keeping the text.

Published to PyPI: <https://pypi.org/project/econenv/0.1.3/>

## [0.1.2] — 2026-09-04

Two EViews reporting bugs, both visible in `%econ status` before any engine is
started.

### Fixed

- **The documented way to pin an EViews version did not work.** EViews
  registers its versioned ProgID as `EViews.Manager.14`; EconEnv looked for
  `EViews14.Manager`, which is registered on no machine. So the versioned
  ProgIDs were never discovered, and the remedy printed by `econenv doctor`,
  raised in the start error, and written in the README and three doc pages told
  users to pin a ProgID that does not exist. Corrected everywhere; on the
  development machine EconEnv now finds eight versioned ProgIDs where it
  previously found none.
- **`%econ status` guessed the EViews version before connecting.** With EViews
  12, 13 and 14 installed it reported 14 — the newest on disk — while
  `EViews.Manager` actually binds to 13. The registry answers this without
  starting anything: the generic ProgID's CLSID carries both the server DLL
  path and the versioned ProgID it resolves to. Version and location now come
  from that, and are still confirmed against the live connection once started.

### Notes

- 130 tests, up from 127.
- The 0.1.0 audit note claiming versioned ProgIDs are "NOT registered" was
  wrong — it probed the wrong name. `docs/engines/eviews.md` now shows the
  actual registry resolution.

Published to PyPI: <https://pypi.org/project/econenv/0.1.2/>

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

Published to PyPI: <https://pypi.org/project/econenv/0.1.1/>

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

[0.1.5]: https://github.com/merwanroudane/econenv/releases/tag/v0.1.5
[0.1.4]: https://github.com/merwanroudane/econenv/releases/tag/v0.1.4
[0.1.3]: https://github.com/merwanroudane/econenv/releases/tag/v0.1.3
[0.1.2]: https://github.com/merwanroudane/econenv/releases/tag/v0.1.2
[0.1.1]: https://github.com/merwanroudane/econenv/releases/tag/v0.1.1
[0.1.0]: https://github.com/merwanroudane/econenv/releases/tag/v0.1.0
