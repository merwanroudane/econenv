# Development

```bash
git clone https://github.com/merwanroudane/econenv
cd econenv
pip install editables
pip install -e ".[dev]"
pre-commit install
```

## Layout

```
src/econenv/
  __init__.py        public API + IPython extension entry point
  _version.py        single source of the version
  _logging.py        logger hierarchy + credential redaction
  exceptions.py      the full error tree
  config.py          layered configuration
  schema.py          logical types, ColumnSchema, DatasetMetadata, ConversionReport
  results.py         ExecutionResult, ModelResult, Figure
  discovery.py       finding R / Stata / EViews without hard-coded paths
  diagnostics.py     doctor
  transfer.py        push/pull/move, snapshots, provenance
  services.py        the layer %econ and the CLI both call
  cli.py             `econenv`
  engines/           base.py, registry.py, one module per engine
  bridges/           pandas <-> engine, one module per engine
  magics/            econ, r, stata, eviews + shared parsing/display
  models/            spec.py, registry.py, compare.py
tests/
  conftest.py            fixtures + automatic engine gating
  test_core.py           no engine needed
  test_mocked_engines.py adapter logic against fakes
  test_integration.py    real engines, marked and skipped without them
```

## Tests

```bash
pytest                                    # everything the machine can run
pytest -m "not stata and not eviews"      # no commercial licence needed
pytest -m "not r and not stata and not eviews"   # pure unit tests
pytest -m eviews                          # just EViews
```

`conftest.py` checks engine availability at collection time and skips what is
not installed, so the same command works on a laptop with nothing and on a
workstation with all three.

Markers: `r`, `stata`, `eviews`, `windows`, `slow`.

### What must stay testable without a licence

Brief §40. Adapter logic that does not need the binary — command splitting,
name sanitising, error translation, type mapping, the VARIANT trap guard — lives
in `test_mocked_engines.py` and runs on a Linux CI runner that will never have
EViews. The fake COM object there deliberately reproduces the silent
`PutSeries` failure, so a regression in the marshalling fails CI everywhere.

## Quality gate

```bash
ruff format src tests
ruff check src tests
mypy
pytest
```

All four are green on `main` and enforced in CI.

Two config notes worth knowing before you fight the linter:

* `UP006`/`UP007`/`UP035`/`UP045` are ignored because the package supports
  Python 3.9, where `dict[str, X]` and `X | None` are not available in runtime
  positions. Keep using `typing.Dict` / `Optional`.
* mypy targets 3.10 because current mypy refuses to target 3.9. The runtime
  floor is still 3.9; the ruff ignores above are what actually keep it honest.

## Adding an engine

1. Subclass `BaseEngine` in `src/econenv/engines/<name>_engine.py`; implement
   `_detect`, `_start`, `_stop`, `_execute`, `_version`.
2. Decorate with `@register`.
3. Add discovery to `discovery.py` if the software needs locating.
4. Add a bridge in `bridges/` if it exchanges data.
5. Add checks to `diagnostics.py` — with a **fix** on every warning.
6. Add the entry point in `pyproject.toml`.
7. Tests: pure logic in `test_mocked_engines.py`, the real thing in
   `test_integration.py` behind a marker.

Third-party packages register through the `econenv.engines` entry point group
without importing EconEnv at build time.

## Adding an estimator

1. Register a `ModelDefinition` in `models/registry.py` with the command each
   engine would use.
2. Implement `_fit_<estimator>` on each engine that supports it.
3. Return a `ModelResult` with `raw` preserved and `notes` explaining any
   convention that differs from the other engines.
4. Add the known-divergence entry to `models/compare.py` if there is one.

Step 3 is the one that matters. The project's value is in reporting differences
accurately, not in making five programs look identical.

## Conventions

* Type hints and docstrings on everything public.
* Comments explain **decisions**, not syntax. If a line looks odd because a
  vendor API is odd, say which behaviour forced it — and cite the evidence.
* Never swallow a vendor error; translate it and keep `.raw`.
* Never let a conversion lose information quietly.

## Releasing

1. Bump `src/econenv/_version.py` and `CITATION.cff`.
2. Update `CHANGELOG.md`.
3. Green quality gate.
4. `python -m build && twine check dist/*`.
5. Tag `v0.x.y`, push, publish.
