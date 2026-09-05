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

## Google Colab

No local installation at all:

```python
%pip install econenv
```

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/merwanroudane/econenv/blob/main/examples/11_colab_quickstart.ipynb)

| Engine | On Colab | |
|---|---|---|
| **Python** | works | it is the kernel |
| **R** | works | R is on the Colab image |
| **Stata** | **possible** | Stata for Linux exists, and pystata supports Linux |
| **EViews** | no | no Linux build, and no permitted workaround |

### Stata on Colab

This does work, if you hold a Stata **Linux** licence. Stata for Linux installs
from a tarball, and [pystata officially supports
Linux](https://www.stata.com/python/pystata17/install.html) via
`stata_setup.config(path, edition)`.

Keep the Linux tarball and your `stata.lic` in Google Drive, then in a Colab
cell:

```python
from google.colab import drive
drive.mount('/content/drive')
```

```bash
!mkdir -p /usr/local/stata19
!tar -xzf "/content/drive/MyDrive/stata/Stata19Linux64.tar.gz" -C /usr/local/stata19
!cd /usr/local/stata19 && yes | ./install
!cp "/content/drive/MyDrive/stata/stata.lic" /usr/local/stata19/
```

EconEnv then finds it with no configuration — Linux executable names
(`stata-mp`, `stata-se`, `stata`) and `/usr/local` are already part of
discovery:

```python
%load_ext econenv
%econ status
```

Three caveats, none of them technical:

- You need a **Linux** licence entitlement. A Windows-only licence does not
  cover this.
- The runtime is destroyed at the end of the session, so this repeats every
  time. Fine as a cell at the top of a notebook; irritating as a habit.
- Whether your licence permits installation on a disposable cloud VM is a
  question for StataCorp, not for EconEnv. Check before relying on it.

### All five engines in Colab — connect it to your own machine

There is a way to get **Python, R, Stata, EViews and MATLAB** while still working in the
Colab interface, and it sidesteps every objection above: Colab's **local
runtime**.

Colab runs in a browser *on your PC*. Google lets you point that interface at a
Jupyter server running on your own machine instead of at a cloud VM. The
notebook UI stays Colab; the kernel — and therefore every engine — is your
Windows PC.

Nothing is exposed to the internet. Your browser talks to `localhost`; Google's
servers never reach your machine, and EViews is driven by local COM exactly as
it would be in a local notebook. This is not the prohibited "web server access
to EViews via COM": there is no web server in front of EViews.

**It needs the classic Jupyter stack.** The bridge package
`jupyter_http_over_ws` was last released in March 2020 and is a `notebook 5/6`
server extension. It does **not** load on `notebook 7` or `jupyter_server 2` —
the enable step fails with *"The module could not be found"*, and
`/http_over_websocket` returns 404. Verified here on notebook 7.5.5 and 6.5.7,
both of which run on jupyter_server 2.

So use a dedicated environment:

```bash
python -m venv colab-runtime
```

```bash
colab-runtime/Scripts/pip install "notebook==6.4.12" jupyter_http_over_ws econenv
```

```bash
colab-runtime/Scripts/jupyter serverextension enable --py jupyter_http_over_ws
```

```bash
colab-runtime/Scripts/jupyter notebook --no-browser --port=8888 --NotebookApp.port_retries=0 --NotebookApp.allow_origin="https://colab.research.google.com"
```

Copy the `http://localhost:8888/?token=...` line it prints. In Colab, click the
**Connect** arrow, choose **Connect to a local runtime**, paste the URL.

Verified on this machine: with `notebook 6.4.12` the extension validates and
`/http_over_websocket` answers `HTTP 400` — the endpoint exists and is waiting
for the websocket upgrade Colab performs. On the modern stack the same probe
returns 404.

Then everything works, because the kernel is your PC:

```python
%load_ext econenv
%econ status      # Python, R, Stata, EViews and MATLAB — all five
```

Two caveats worth knowing:

- Your PC must stay awake and the server running for as long as the notebook is
  open.
- That environment is separate from your usual one, so install into it whatever
  the notebook needs.

### EViews *on* a Colab cloud runtime — genuinely not possible

Not a limitation EconEnv can route around:

1. **There is no Linux build of EViews.** It ships for Windows and macOS only.
2. **Wine does not work.** EViews cannot read a valid machine ID under Wine, so
   licence activation fails. This is longstanding and unresolved.
3. **Driving a Windows copy remotely is forbidden by EViews.** The obvious
   workaround — run EViews on your own Windows machine and reach it from Colab
   over a tunnel — is ruled out by EViews' own documentation, which states that
   *"web server access to EViews via COM is not allowed"*, and limits remote
   Distributed COM to a single instance.

Point 3 is the important one: the workaround is technically straightforward and
contractually prohibited, so EconEnv will not ship it.

For EViews, use a local Windows machine and
[the four-engine notebook](../examples/10_real_data_all_engines.ipynb).
