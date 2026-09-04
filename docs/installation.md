# Installation

EconEnv is on PyPI: <https://pypi.org/project/econenv/>

```bash
pip install econenv
```

Core dependencies are `pandas`, `numpy`, `ipython` and `statsmodels` — the last
because Python is one of the four comparable engines and `compare_ols` needs its
OLS adapter. Nothing commercial is pulled in, and nothing is bundled.

## Extras

```bash
pip install "econenv[stata]"    # stata_setup (optional helper)
pip install "econenv[eviews]"   # comtypes; Windows only
pip install "econenv[arrow]"    # pyarrow; fast R transfer
pip install "econenv[all]"
pip install "econenv[dev]"      # pytest, ruff, mypy, pre-commit
```

`econenv[r]` installs rpy2 **on non-Windows platforms only**. On Windows the
subprocess backend is the supported route and needs nothing from PyPI. See
[engines/r.md](engines/r.md).

## Engine requirements

| Engine | Minimum | Provided by | Notes |
|---|---|---|---|
| Python | 3.9 | you | the host kernel |
| R | 4.0 | you | discovered automatically |
| Stata | **17** | you | PyStata ships with Stata 17+ |
| EViews | 12 | you | Windows only; COM automation |

EconEnv **does not install, bundle or redistribute** Stata or EViews. You must
obtain and license them yourself. See [LICENSE](../LICENSE).

## Platform support

| | Python | R | Stata | EViews |
|---|---|---|---|---|
| Windows | ✅ verified | ✅ verified | ✅ verified | ✅ verified |
| Linux | ✅ | ✅ by design | ✅ by design | ✖ no COM |
| macOS | ✅ | ✅ by design | ✅ by design | ✖ no COM |

"by design" means the code path is platform-neutral but has not been run on
that OS by the author. Reports welcome.

The absence of EViews never blocks installation. On Linux and macOS the EViews
engine reports itself unavailable and everything else works.

## From source

```bash
git clone https://github.com/merwanroudane/econenv
cd econenv
pip install editables            # hatchling needs it for editable installs
pip install -e ".[dev]"
pytest -m "not stata and not eviews"
```

## Verifying

```bash
econenv doctor
```

Exit code 0 means no errors. Warnings are fine — a missing engine is a warning,
not an error.
