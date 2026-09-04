# Contributing

Thanks for looking. EconEnv is early, and the parts that are least tested are
the ones nobody has had the hardware for — Linux, macOS, rpy2, older Stata
editions. Reports from those are especially useful.

## Getting set up

```bash
git clone https://github.com/merwanroudane/econenv
cd econenv
pip install editables
pip install -e ".[dev]"
pre-commit install
```

```bash
pytest -m "not stata and not eviews"    # no commercial licence needed
ruff format src tests && ruff check src tests && mypy
```

See [docs/development.md](docs/development.md) for the layout, the test markers
and how to add an engine or an estimator.

## Reporting a bug

Include:

```bash
econenv doctor --deep --json > doctor.json
econenv snapshot snapshot.json
```

Neither contains licence keys or serial numbers — EconEnv's logging redacts
anything matching a credential pattern, and a pre-commit hook refuses to let
licence material into the repository at all.

Also include what you ran, what you expected and what happened, and — if a
transfer is involved — the frame's dtypes.

## Pull requests

* One change per PR; small commits with clear messages.
* Tests for anything that could regress. If it needs a commercial engine, put
  the pure logic behind a fake in `tests/test_mocked_engines.py` so it still
  runs in CI — the EViews `PutSeries` guard is the model for this.
* Docstrings and type hints on anything public.
* Comments explain **decisions**, not syntax. If a line looks strange because a
  vendor API is strange, say which behaviour forced it, and cite the evidence.
* Run the quality gate before pushing.

## The two rules that are not negotiable

**1. Never redistribute commercial software.** No Stata or EViews binaries,
libraries, licence files, serial numbers or activation keys — in the
repository, in a test fixture, in a CI workflow, or in a docker image. The
pre-commit hook enforces the obvious cases; use judgement for the rest.

**2. Never hide a difference.** If a conversion loses information, warn. If a
value would change, raise. If two engines disagree, report it with the reason.
A PR that makes four programs *look* like they agree by rounding, defaulting or
omitting is the one kind of change that will not be merged — the project exists
to surface those differences, not to smooth them over.

## Adding support for another program

MATLAB, Julia, SAS, Gretl, Dynare, GAUSS, Ox and RATS are all plausible. The
architecture is designed so this means writing one adapter, not editing the
core. Start with [docs/development.md](docs/development.md#adding-an-engine),
and consider shipping it as a separate package registered through the
`econenv.engines` entry point rather than as a PR here — that keeps its
dependencies out of everyone else's install.

## Licence

Contributions are accepted under the MIT licence of the project.
