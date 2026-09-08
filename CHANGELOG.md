# Changelog

All notable changes to EconEnv are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is
[semantic](https://semver.org/spec/v2.0.0.html).

## [1.4.1] — 2026-09-08

### Fixed

- **A GAUSS plot came out as a broken thumbnail.** `plotSave` takes a size *and
  a unit*, and without the unit it writes onto a canvas of raw units — measured
  against GAUSS 26.1.1:

  ```
  plotSave(f, 12 | 9)           ->  4.2mm x 3.2mm
  plotSave(f, 12 | 9, "in")     ->  508mm x 381mm
  plotSave(f, 800 | 600, "px")  ->  282mm x 212mm
  ```

  EconEnv omitted it, so every captured figure was a valid file full of path
  data on a four-millimetre canvas — large enough to look right by file size and
  microscopic on screen, which is why it took two reports to find. The unit is
  now always stated: inches for `svg` and `pdf`, pixels for `png`, `jpg` and
  `jpeg`.

## [1.4.0] — 2026-09-08

**EconLang** — the first vertical slice of a language in which a researcher
states the model once and changes only which engine runs it.

### Added — EconLang

```econ
data "macro.csv"

set time:
    variable = year

model ols baseline:
    y = gdp
    x = inflation, unemployment
    vcov = HC3
```

- A real language, not a Python wrapper: an indentation-sensitive lexer, a
  recursive-descent parser, an AST, and lowering into an **Econometric IR**
  before any backend sees anything. The IR is `ModelSpec` — the same object
  `compare_ols` already hands all six engines — so adding a backend is a
  lowering rather than a rewrite, and no backend ever sees EconLang syntax.
- `%%econlang` in a notebook. Estimated models land in Python under the names
  they were given, as ordinary `ModelResult`s, so export and comparison work
  on them unchanged.
- **The generated native code is visible and is the code that runs.**
  `show code m` prints it; `translate m` shows all six backends at once, from
  the same compilers that execute — so the table cannot drift from reality.
- **No silent substitution.** Where a backend cannot do what was asked, the
  generated code says so: EViews' `cov=white` is the HC1 form, so a request
  for HC3 emits the closest form *and* a comment naming the difference,
  rather than quietly returning a different estimator.
- `dryrun` interprets and generates without loading data or starting an
  engine — it works even when the data file does not exist yet.
- `explain m` describes the model in words rather than syntax.
- Errors are part of the language: a code from a fixed taxonomy, the line, a
  caret under the offending option, near-miss suggestions and, where it can be
  worked out, the corrected line. An estimator that is not implemented yet is
  a *capability* error naming what is available, not a syntax error.
- Time declarations are checked: a repeated index is refused and suggests a
  panel; gaps and unsorted rows are reported rather than estimated over.
- `docs/econlang.md`, `examples/inflation.econ`, and 52 tests.

This is deliberately **OLS only**. The architecture is meant to be proved
before it spreads to more estimators.

### Fixed — GAUSS graphics

- **A cell that called `plotSave` itself showed a broken image.** EconEnv
  appended its own `plotSave` on top of the user's, so the figure was written
  twice and the notebook displayed EconEnv's temporary copy rather than the file
  the researcher had named. An explicit save now wins: the cell is sent
  unchanged, the named file is what gets displayed, and it is left on disk.
- `jpg` and `jpeg` plots are displayed rather than written and ignored.
- A format `plotSave` refuses — `eps`, `tif`, `gif`, `bmp` — is named before
  GAUSS is asked, because GAUSS answers only "Program execute failed".

## [1.3.1] — 2026-09-08

What landed after the 1.3.0 wheel was uploaded, so is not in the published
1.3.0.

### Added — GAUSS

- **A GAUSS procedure written in one cell is callable in the next.** Each cell
  runs a fresh `tgauss`, so EconEnv already carried *values* across with GAUSS's
  own `save`/`load`; it now re-declares `proc ... endp;` definitions too.

  ```gauss
  %%gauss
  proc (1) = sq(a);
      retp(a .* a);
  endp;
  ```
  ```gauss
  %%gauss
  print sq(9);      /* 81, in a brand new process */
  ```

  Carrying a *definition* is safe where replaying a *statement* is not: a `proc`
  block computes nothing and touches nothing, so re-declaring it is idempotent,
  while re-running `x = x + 1;` would change the answer. A cell that redefines a
  procedure wins, and the stored definition is left out rather than emitted
  twice — GAUSS rejects two definitions of one name in a program.

  `#include` and `library` statements still do not carry; those need the
  licensed GAUSS Engine.
- EconEnv now looks for the GAUSS Engine library under `MTENGHOME` and beside
  the installation, so `%econ doctor gauss` distinguishes "not on this machine"
  from "found, but no binding yet".

### Fixed

- **Every EViews hypothesis test produced no output at all.** `_VIEW_RE` anchors
  at the end of the parenthesised options, so a view whose arguments follow a
  space — `eq1.wald c(2)=0`, `eq1.testadd x3`, `eq1.testdrop x2`,
  `eq1.chow 60`, `eq1.facbreak 80` — did not look like a view. Each ran as a
  bare command, which displays in EViews' own window and returns nothing here.
  Recognised now through an allow-list of five names, every one verified against
  EViews 13 as freezing to a real table; a looser pattern would have swept in
  *procs*, and freezing `eq1.ls y c x1` would give a display command the side
  effect of re-estimating the equation.

### Changed

- The GAUSS Engine verdict is now evidence, not assumption. Reading the real PE
  export tables across all 476 DLLs in a GAUSS 26 installation finds zero
  `GAUSS_*` symbols, and there is no `mteng` or `gsoop` anywhere in the tree —
  the Engine is a separate Aptech product, and owning desktop GAUSS does not
  include it. Two licence-free routes to a persistent workspace were tried and
  rejected on evidence: piping `tgauss` returns no output through the pipe, and
  a driver that `run`s a command file shares the workspace but never regains
  control.

## [1.3.0] — 2026-09-07

GAUSS becomes the sixth engine. Python, R, Stata, EViews and MATLAB are
unchanged except where a shared bug affected them.

### Added

- **GAUSS**, driven through its terminal executable. Discovery, configuration,
  `%gauss` / `%%gauss`, typed data transfer, diagnostics, OLS, and a searchable
  command catalogue. Everything was verified against a live GAUSS 26.1.1 rather
  than taken from documentation, which corrected four assumptions:
  the executable is `tgauss`, not `engauss`; `loadall` is unavailable to the
  batch compiler; `csvWriteM` writes about fifteen significant digits; and
  GAUSS installs to `C:\gauss26`, not Program Files.
- **GAUSS in `compare_ols`**, using GAUSS's own `ols` procedure. Six engines
  now agree to 1.8e-15, with R², adjusted R², log-likelihood, AIC, BIC and RMSE
  matching statsmodels, Stata and MATLAB exactly.
- **`econenv_bridge.gss`**, which writes seventeen significant digits so a
  double round-trips **exactly**. GAUSS's own writer moves a value by roughly
  3e-15 per round trip, which would have put GAUSS out of step with the
  machine-precision agreement that is the point of the comparison.
- **`%econ gauss`** — 95 commands in 12 categories, 65 resolved against a live
  GAUSS. It leads with the three rules that catch every newcomer: every
  statement ends with `;`, a bare expression prints nothing, and `~` joins
  columns while `|` stacks rows. Two catalogue claims were wrong and GAUSS
  caught them: `autocov` and `autocor` do not exist; `acf` and `pacf` do.
- **`%econ gauss colab`**, and a Colab section that now covers all six engines
  and distinguishes the hosted runtime from the local one — where MATLAB,
  GAUSS and EViews all work with your existing licences.
- `docs/engines/gauss.md` and a generated `gauss-commands.md`, with a test that
  fails if the page and the catalogue disagree.
- **GAUSS plots**, captured and displayed inline. SVG by default — vector, and
  what most journals ask for — with `png` and `pdf` available through
  `%econ config gauss.graphics`. A cell that draws nothing produces no figure,
  because asking `plotSave` unconditionally would re-emit the last plot under
  every later cell.
- **A GAUSS section in the example notebook**, executed against the real
  engines: the matrix layout, least squares written out with `/`, GAUSS's own
  `ols`, and a captured scatter plot. All six engines now appear in the
  notebook's comparison on real US macro data.

### Fixed

- **The EViews output table was misaligned.** Three causes: every cell was
  left-aligned, so decimal points did not line up and a negative coefficient
  pushed its digits across; one set of column widths was computed for the whole
  view, though a regression output is several tables stacked with different
  column counts; and the heading row is separated from its data by a blank row,
  so sizing blocks independently left "Coefficient" standing over nothing.
  Numeric columns are right-aligned, each block is sized on its own columns,
  and a heading row is merged with the block beneath it.
- **The engine registry silently returned a short list.** `_ensure_loaded()`
  imported the built-ins only when no engine class was registered yet — a proxy
  for "not yet imported" that fails as soon as anything imports one engine
  module directly. Depending on import order, `registry.names()` could omit
  half the engines. It now tracks loading explicitly.
- **`pytest` had no `gauss` marker**, so a test needing GAUSS would have failed
  rather than skipped on a machine without it.
- **`gauss` was not a known config section**, so every `%econ config gauss.*`
  documented on the engine page would have raised. Seven options are now
  declared.
- **A `struct` cannot be saved in GAUSS**, and a plotting cell declares one
  (`struct plotControl p;`) then assigns to it — which looked like an ordinary
  top-level assignment, so EconEnv tried to carry it and *every plotting cell
  failed to compile*. Struct declarations are now recognised and excluded.
- **`Series.view` is deprecated in pandas 2.2** and warned in the notebook when
  a datetime column crossed to GAUSS.
- The example notebook's own data cell used the deprecated
  `pd.PeriodIndex(year=..., quarter=...)`.

### Changed

- **The native backend is blocked, not merely unwritten.** The GAUSS Engine
  (`mteng`) is licensed separately from desktop GAUSS and is not part of an
  installation — `gauss.dll` exports no `GAUSS_*` symbols — so there is nothing
  to bind to on a normal machine. `gauss.backend=native` says so instead of
  "not built yet", and the CLI backend is what runs.
- A GAUSS cell runs in a fresh process, so **only top-level values carry**
  between cells, via GAUSS's own `save`/`load`. Procedures and `#include` state
  do not, and that is documented rather than worked around: replaying earlier
  cells to fake a session would silently re-run their side effects.
- A name GAUSS already owns (`vec`, `rows`, `ones`, …) is refused before GAUSS
  sees it, with an alternative, instead of surfacing a raw `G0276`.

## [1.2.0] — 2026-09-07

A hardening pass over the MATLAB integration, from a bug report against 1.1.1.
Python, R, Stata and EViews are untouched.

### Fixed

- **`%%matlab -o y` failed for anything that was not a table.** Every pull went
  through `pandas.DataFrame`, so `y = 10` raised
  `ValueError: Must pass 2-d input. shape=()` from inside pandas — an error that
  says nothing about MATLAB. Scalars, logicals, text, complex numbers, integer
  classes, vectors and string arrays now come back as their natural Python
  types, and a struct or mixed cell array raises a `DataTransferError` naming
  the MATLAB class and the conversion that would work.
- **`%%matlab -i x` failed for a list or any NumPy array.** `_push_scalar`
  called `float()` on everything that was not a DataFrame, so
  `float([1.0, 2.0])` and `float(np.arange(5))` failed in the float
  constructor. Lists, tuples, 1-D and 2-D arrays, Series, bools, complex numbers
  and strings each now convert to the right MATLAB class — and `bool` becomes
  `logical` rather than `double`.
- **Variables were not found under Google Colab's local runtime.** The lookup
  consulted `local_ns` and `shell.user_ns`, missed the namespace Colab uses, and
  raised `NameError: 'x' is not defined in Python` until the user wrote
  `get_ipython().user_ns["x"] = x` by hand. All four magics now share one
  resolver that consults every namespace the shell exposes and tests
  *membership* — so a variable genuinely assigned `None` is no longer reported
  as undefined.
- **`%econ doctor matlab` answered "unknown engine".** MATLAB was never added to
  the diagnostics dispatcher. It now reports the installation, the engine
  package and its release, and with `--deep` runs a round trip.
- **`pytest` had no `matlab` marker**, so the five-engine comparison test failed
  rather than skipping on a machine without MATLAB.
- **Export refused a NumPy matrix**, which is exactly what `%%matlab -o A`
  returns.
- **An unwritable extension fell back silently.** Asking for `table.pdf` wrote
  `table.tex`, `table.docx` and `table.xlsx` without a word. It is now refused
  by name, and `.pdf` is a real format.
- **A plain DataFrame or matrix got a significance-stars footnote**, claiming a
  convention for numbers with no p-values behind them.

### Added

- **`pull_value`** — `econenv.pull_value("matlab", "y")` returns the natural
  type. `pull` keeps its frame contract, which `move` and `broadcast` depend on,
  and now explains itself instead of failing inside pandas when asked for a
  scalar.
- **A searchable MATLAB command catalogue**: `%econ matlab`,
  `%econ matlab timeseries`, `%econ matlab find cointegration`. 102 commands in
  11 categories, **every one resolved against a live MATLAB R2024a** —
  `exist` for functions, `which -all` for the eleven that are class methods.
  Each names the toolbox it needs, because an unlicensed function fails with
  `Unrecognized function or variable`, which reads like a typo. Two toolbox
  claims were wrong and `which` caught them: `quantile` and `prctile` are base
  MATLAB now, not Statistics.
- **`%econ matlab colab`** — the local-runtime setup, which is the only
  arrangement where MATLAB, EViews and a local Stata work from Colab at all.
- **`%econ export`, `%econ export formats`, `%econ matlab export`** — what can
  be exported, to what, and which optional dependency each needs.
- **PDF table export**, typeset from the same LaTeX the `.tex` writer produces.
- **A research report layer**: `econenv.report(...)` with `add_text`,
  `add_table`, `add_figures` and `add_snapshot`, written as HTML, Markdown,
  LaTeX, DOCX or PDF. The snapshot is the point — a table and a figure without
  the versions that produced them are what a referee cannot check.
- **`docs/engines/matlab-commands.md`**, generated from the catalogue, with a
  test that fails if the page and the module disagree.
- 85 tests, taking the suite to 343.

### Changed

- A MATLAB vector comes back as a **1-D** NumPy array whichever way MATLAB
  oriented it, rather than a `(1, n)` DataFrame. MATLAB has no 1-D array, and
  the orientation is a storage detail, not a result.
- A 1-D Python sequence goes in as a **column**, which is what a regressor, a
  series and a table column all use. `%econ config matlab.vectors row` changes
  it.

### Removed

- Nothing.

## [1.1.1] — 2026-09-05

MATLAB release support, worked out rather than tabulated.

### Added

- **MATLAB R2026a.** Its Engine API (`matlabengine 26.1`) is the first that
  supports **Python 3.13**; EconEnv previously stopped at R2025b and told a
  3.13 user that no engine release supported them at all, which was true only
  of the releases they happened to have installed.
- Releases newer than any table are resolved by rule — MathWorks numbers the
  series as `R20YYa` → `YY.1` and `R20YYb` → `YY.2` — so R2026b and later get a
  correct pin instead of falling off the end of a lookup.

### Fixed

- **The unsupported-Python diagnostic was a dead end.** It said which of your
  installed releases could not run on your Python, then stopped. It now names
  the MATLAB release whose engine *does* support that Python, and the Python
  version your own MATLAB can drive, so there are two ways forward instead of
  none.

### Fixed — documentation that had fallen behind the code

- **The site's comparison section showed a Stata warning instead of the
  comparison table.** The page pulls its output from the executed notebook and
  took whichever output came first, so a `stderr` warning displaced the
  five-engine result on the one section the page exists to show. Real results
  now win over warnings; errors are never used.
- **The `%load_ext` banner on the site was hand-written and stale** — it
  predated `%%matlab`. It is read from the notebook now, like every other
  output on the page, so it cannot drift again. The copies in the guide and in
  `getting-started.md` were corrected too; the latter still claimed 0.1.0.
- **MATLAB was missing from the site entirely** despite shipping in 1.0.8. It
  now has an installation card with the compatibility matrix, a `%%matlab`
  reference card, a troubleshooting entry, and a place in the diagrams.
- **"Four engines" in the live documentation**, in twelve places, from before
  MATLAB was added.
- **Colab support for MATLAB was described two ways** — "possible" in the
  README and "no" on the site. It is the same situation as Stata: a Linux
  build exists, and the licence is the question.

### Removed

- **The `econenv[matlab]` extra.** It resolved to `matlabengine>=9.13`, which
  pip satisfies with the newest wheel — wrong for anyone not on the newest
  MATLAB, and unusable on Python 3.13 before R2026a. An extra cannot express a
  constraint that depends on both the MATLAB release and the interpreter, so
  `econenv doctor` prints the correct pin instead.

## [1.0.9] — 2026-09-05

A documentation release. No code changed; its purpose is a PyPI page whose links
work.

### Fixed

- **Every link in the README returned 404 on PyPI.** The README is also the PyPI
  long description, and PyPI resolves a relative link like
  `docs/guide/econenv-guide.pdf` against `pypi.org/project/econenv/<version>/`
  rather than against the repository. All twenty were therefore correct on
  GitHub and broken for anyone arriving from PyPI — including the User Guide,
  Examples and Changelog links in the header row.

  All twenty are now absolute `https://github.com/...` URLs, and two tests keep
  them that way: no relative links may appear in the README, and every
  repository link must point at a file that exists. The check matches on the
  link target alone, because a `[text](target)` pattern cannot see
  `[![badge](img)](target)` — which is how the licence badge survived the first
  pass of the fix.

- The released version is now linked from the site hero, both example notebooks
  and the guide's title page, each deriving the number from the package rather
  than repeating it.

Published to PyPI: <https://pypi.org/project/econenv/1.0.9/>

## [1.0.8] — 2026-09-05

MATLAB as a fifth engine, and a way to get results out of a notebook and into a
paper.

### Added

**MATLAB.** Driven through the official MATLAB Engine API for Python, so a
DataFrame becomes a real MATLAB `table` rather than printed text. Verified
against R2024a with matlabengine 24.1.4: push a 60×6 table with `datetime` and
`categorical` intact, run `fitlm`, pull back with every dtype preserved,
exchange scalars and matrices, capture figures without repeats, and get errors
that name toolboxes and `addpath`.

MATLAB also implements OLS, so **all five engines now agree** on the same
regression to eight decimals. Detection reports the release the Engine API will
*start* — not the newest installed — because on a machine with R2024a and
R2025a those are different, and naming the wrong one is the mistake the EViews
adapter used to make.

**Publication export.**

```python
econenv.export(cmp, "paper/table1", formats=["tex", "docx", "xlsx"])
%econ export cmp paper/table1 --formats tex,docx --caption "Table 1"
```

Two layouts, selectable per call: `journal` prints what a paper prints —
coefficient with significance stars, standard error beneath in parentheses, N
and fit statistics at the foot — and `full` gives every statistic the engine
reported. Seven writers: LaTeX with booktabs, Word as a real editable table,
Excel one sheet per result, plus CSV, HTML, Markdown and RTF.

The content decision is made once and the writers only render it, so the LaTeX
and the Word version of a result cannot disagree about a coefficient. The output
was **compiled with pdflatex** during development, which is how the escaping
rules were settled — a raw `²` is written as `	extsuperscript{2}` rather than
trusting the document's `inputenc`.

**Transfer helpers.** `econenv.broadcast("macro", df)` puts one dataset into
every available engine in a single call — 13 seconds for four engines here — and
records rather than raises when one is missing. `econenv.transfer_matrix()`
reports what can move where *on this machine*.

### Fixed

- **`pull("eviews", name)` failed after `push("eviews", name, df)`**, while the
  same round trip worked for R, Stata and MATLAB. A push to EViews creates a
  page of series, not an object named after the frame. EViews now remembers the
  name and returns the page.
- **`export` raised on a DataFrame** — `if tables:` is ambiguous for pandas.
- **`R²` was emitted as a raw Unicode superscript** in LaTeX.

### Changed

- The documentation said "four engines" in twenty-four places. Present-tense
  claims now say five; release history is unchanged.
- New chapters in the guide: MATLAB, Exporting results, Moving data between
  programs. 31 pages, up from 25.
- New `docs/export.md`; `docs/magics.md` and `docs/data-exchange.md` extended.

### Notes

- 235 tests, up from 170. `matlabengine` and the export writers are optional
  extras — MATLAB, Word and Excel are never required.

Published to PyPI: <https://pypi.org/project/econenv/1.0.8/>

## [1.0.7] — 2026-09-04

First stable release. The same code as 0.1.7, with the version number and the
project's claims about itself brought into line.

### Changed

- **0.1.7 → 1.0.7, and the API is declared stable.** The magics,
  `push` / `pull` / `move`, the result objects and `compare_ols` now follow
  semantic versioning: no breaking change without a major bump.
- `Development Status` classifier moved from *3 - Alpha* to
  *5 - Production/Stable*, and the README status badge with it. Shipping a 1.0
  while still calling the project alpha would have been a contradiction.

### What "stable" does and does not claim

It says the public API is settled. It does not say every path has been
exercised, and the verification table in the README is unchanged:

- The **rpy2 R backend** is implemented but unverified — rpy2 is not
  installable on the development machine.
- **Linux and macOS** are supported by design and have not been run end to end.
  R discovery resolves correctly on Linux by inspection; the runtime has not
  been exercised.
- **Panel commands** — 42 of the 136 catalogue entries — are documented syntax
  rather than verified, because no panel-structured workfile was available.

Everything else in the four-engine workflow was run against R 4.5.2, StataNow
19.5 MP and EViews 13 on Windows, and the example notebook is re-executed
against them on every release.

### Note on the jump

1.0.0 through 1.0.6 never existed; the number went straight from 0.1.7 at the
author's request. PyPI orders releases numerically, so 1.0.7 supersedes every
0.x version permanently — a later 0.x would never be served as latest.

Published to PyPI: <https://pypi.org/project/econenv/1.0.7/>

## [0.1.7] — 2026-09-04

Google Colab support, and a correction to what I had claimed about it.

### Added

- **Colab detection.** `discovery.is_colab()` reads `COLAB_RELEASE_TAG`,
  `COLAB_GPU` or the `google.colab` module, and `doctor` reports the environment
  by name with what can and cannot run there.
- **`examples/11_colab_quickstart.ipynb`** with an *Open in Colab* badge: one
  `%pip install econenv`, then a Python + R workflow on the same real macro data
  as the four-engine notebook.
- **All four engines in Colab, via a local runtime.** Colab already runs in a
  browser on your own PC, so it can be pointed at a Jupyter server on that same
  PC: the interface stays Colab while the kernel — and therefore Python, R,
  Stata **and EViews** — is your Windows machine. Nothing is exposed to the
  internet, so this is not the prohibited "web server access to EViews via COM".

  It needs the classic Jupyter stack, and that was measured rather than assumed.
  `jupyter_http_over_ws` was last released in March 2020 and is a notebook 5/6
  server extension: on notebook 7.5.5 and 6.5.7 — both on `jupyter_server 2` —
  enabling it fails and `/http_over_websocket` returns 404. Pinned to
  `notebook==6.4.12` it validates and the probe returns HTTP 400, the endpoint
  waiting for Colab's websocket upgrade.
- A **Colab chapter** in the printed guide, and a Colab section on the
  documentation site and in `docs/installation.md`.

### Corrected

- **Stata on Colab was reported as impossible. It is not.** Stata for Linux
  installs from a tarball and pystata officially supports Linux, so with a Linux
  licence it can be installed on a Colab runtime from Google Drive — and EconEnv
  finds it with no configuration, since the Linux executable names and
  `/usr/local` were already in discovery. The recipe and its caveats are
  documented.
- **EViews on a Colab runtime remains impossible, now for cited reasons**
  rather than assumption: no Linux build, Wine cannot read a valid machine ID so
  licensing fails, and EViews' own documentation forbids reaching it over a
  network.

### Notes

- 170 tests, up from 166. The Colab tests pin the corrected facts, including the
  exact EViews restriction, so this cannot silently revert.

Published to PyPI: <https://pypi.org/project/econenv/0.1.7/>

## [0.1.6] — 2026-09-04

For researchers who have only ever driven EViews from its menus. In a notebook
there is nothing to click, and not knowing the command is a harder barrier than
any missing feature.

### Added

- **A searchable catalogue of 134 EViews commands**, 92 of them verified
  against EViews 13. Each entry records the menu path you already know, the
  command it becomes, what it does in plain language, and a runnable example.
- **`%econ eviews`** — look commands up from inside the notebook, while writing
  the cell:

  ```python
  %econ eviews                      # tasks
  %econ eviews graph                # everything about plotting
  %econ eviews find cointegration   # search all of it
  ```

  Also `econenv eviews <term>` from the command line; both share one catalogue.
- **`docs/engines/eviews-commands.md`**, generated from that catalogue by
  `scripts/gen_eviews_docs.py`, so the page and the lookup cannot disagree — a
  test fails if the file on disk drifts from the source.

### Fixed

- **`eq.forecast(g)` and `eq.fit(g)` now produce a plot.** EViews draws the
  forecast in a window belonging to no object, so it could not be exported.
  EconEnv rebuilds the same picture — forecast ± 2 standard errors — from
  series EViews will write, using temporary series that are deleted afterwards.
  The figure is labelled so you can tell it was reconstructed. A forecast
  *without* the `g` option still produces no figure, because none was asked for.
- **The `✓` in command listings no longer crashes the Windows console.** cp1252
  cannot encode U+2713, which turned "help me find a command" into a traceback.

### Resolved

The CUSUM gap reported in 0.1.5 does not exist, and the explanation given for
it was also wrong. EViews' own *Object Reference* (page 202) settles it:
`rls(q)` is the CUSUM test and `rls(v)` is CUSUM of squares, both working.

`s` is not an option at all but a **modifier** meaning *save*: combine it with
another option and name the series, as in `eq1.rls(r,s) r_res r_resse`, which
plots the recursive residuals and keeps them. `rls(s)` alone fails because it
asks to save without saying what to plot — not because CUSUM is unavailable in
batch mode, which is what 0.1.5 claimed.

### Added — a full worked example and a printed guide

- **`examples/10_real_data_four_engines.ipynb`** — a complete analysis on
  **real US quarterly macroeconomic data, 1959Q1–2009Q3** (203 observations,
  shipped with statsmodels, so no download and no private file). Python builds
  the data, R plots and diagnoses, Stata's `newey` supplies HAC standard errors,
  and EViews does unit roots, Johansen cointegration, CUSUM stability and an
  out-of-sample forecast — then all four estimate the same regression and are
  compared.

  Every output in it was produced by **executing it** against R 4.5.2, StataNow
  19.5 MP and EViews 13: 43 outputs and 8 embedded figures, no cell errored. It
  is generated by `scripts/build_example_notebook.py --run`, so it can be
  rebuilt rather than quietly going stale.

- **`docs/guide/econenv-guide.pdf`** — a 22-page installation and user guide,
  starting from a machine with no Python on it: Python, Jupyter, EconEnv, then
  R, Stata and EViews one at a time, with the traps each one has. Also the magic
  commands, a chapter for EViews users who have only ever clicked,
  reproducibility, and troubleshooting. Source in `econenv-guide.tex`.

### Added — Google Colab, including all four engines

- **Colab's local runtime gets you all four engines**, and it was the user's
  idea: Colab already runs in a browser on your own PC, so point it at a Jupyter
  server on that same PC. The interface stays Colab; the kernel — and therefore
  Python, R, Stata and EViews — is your Windows machine. Nothing is exposed to
  the internet, so this is not the prohibited "web server access to EViews via
  COM": your browser talks to `localhost` and EViews is driven by local COM
  exactly as in a local notebook.

  It needs the **classic** Jupyter stack, and that was measured rather than
  assumed. `jupyter_http_over_ws` was last released in March 2020 and is a
  notebook 5/6 server extension: on notebook 7.5.5 and 6.5.7 — both running on
  jupyter_server 2 — enabling it fails and `/http_over_websocket` returns 404.
  Pinned to `notebook==6.4.12` the extension validates and the same probe
  returns HTTP 400, the endpoint waiting for Colab's websocket upgrade. The
  recipe and that evidence are in `docs/installation.md`.

### Added — Google Colab cloud runtimes

- **`examples/11_colab_quickstart.ipynb`**, with an *Open in Colab* badge: one
  `%pip install econenv` and a Python + R workflow on real macro data, needing
  no local setup.
- **Colab detection.** `discovery.is_colab()`, and a `doctor` check that names
  the environment and states precisely what can and cannot run there.

  **Stata can.** Stata for Linux installs from a tarball and
  [pystata supports Linux](https://www.stata.com/python/pystata17/install.html),
  so with a Linux licence it can be installed from Google Drive at the top of a
  notebook. EconEnv already discovers it — the Linux executable names and
  `/usr/local` were in discovery from the start. `docs/installation.md` carries
  the recipe, and the caveats: it repeats every session, and whether your licence
  covers a disposable cloud VM is a question for StataCorp.

  **EViews cannot, and this is not a limitation EconEnv can route around.**
  There is no Linux build. Under Wine, EViews cannot read a valid machine ID, so
  licence activation fails. And the obvious workaround — running EViews on a
  Windows machine and reaching it from Colab over a tunnel — is ruled out by
  EViews' own documentation, which states that *"web server access to EViews via
  COM is not allowed"* and limits remote Distributed COM to a single instance.
  That workaround is easy to build and contractually prohibited, so EconEnv does
  not ship it.

### Also fixed

- **`pull("r")` without a name returned an empty frame.** Stata and EViews have
  a current dataset; R does not — every frame is just a variable. The default
  was R's `.Last.value`, the last top-level expression, which after a plot or a
  model fit is not a data frame at all, so the pull silently produced a `(0, 1)`
  result instead of the data. The default is now the frame EconEnv last
  transferred, and when there is none the error names the data frames R
  actually holds.

- **`print(result)` showed a debugging repr, not the result.** Every result
  class — `ExecutionResult`, `ModelResult`, `ComparisonResult`, `Figure` —
  defined `_repr_mimebundle_` but no `__str__`. So a notebook rendered the full
  comparison table while the same object printed as `<ComparisonResult ...>` in
  a script or from the CLI. The text was already being built; it just was not
  reachable outside a notebook. `str()` now returns exactly what the notebook
  shows, and `repr()` stays terse. `Figure` describes itself rather than
  printing raw PNG bytes to a terminal.

- **`doctor` reported PASS for an rpy2 that cannot be imported.** The check used
  `find_spec`, so a package that is present but raises on import — an rpy2 built
  for an older Python, which is what `pip install rpy2` leaves on Windows —
  passed. Installed, importable and usable are now three states rather than two:
  a broken rpy2 is a WARNING carrying the real ImportError and the conda-forge
  repair, instead of "not installed", which sent people to install what they
  already had.
- `docs/engines/r.md` explains the Windows situation, including the catch that
  conda-forge's rpy2 brings its own R alongside any already installed.

### Notes

- 166 tests, up from 150.

Published to PyPI: <https://pypi.org/project/econenv/0.1.6/>

Documentation site: <https://merwanroudane.github.io/econenv/> 136 catalogue entries, 94 verified.

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

Not released to PyPI on its own — these fixes reached users in 0.1.5.

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

[1.0.9]: https://github.com/merwanroudane/econenv/releases/tag/v1.0.9
[1.0.8]: https://github.com/merwanroudane/econenv/releases/tag/v1.0.8
[1.0.7]: https://github.com/merwanroudane/econenv/releases/tag/v1.0.7
[0.1.7]: https://github.com/merwanroudane/econenv/releases/tag/v0.1.7
[0.1.6]: https://github.com/merwanroudane/econenv/releases/tag/v0.1.6
[0.1.5]: https://github.com/merwanroudane/econenv/releases/tag/v0.1.5
[0.1.4]: https://github.com/merwanroudane/econenv/releases/tag/v0.1.4
[0.1.3]: https://github.com/merwanroudane/econenv/releases/tag/v0.1.3
[0.1.2]: https://github.com/merwanroudane/econenv/releases/tag/v0.1.2
[0.1.1]: https://github.com/merwanroudane/econenv/releases/tag/v0.1.1
[0.1.0]: https://github.com/merwanroudane/econenv/releases/tag/v0.1.0
