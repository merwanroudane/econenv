# MATLAB

Driven through the **MATLAB Engine API for Python** — the interface MathWorks
ships inside every MATLAB installation and publishes on PyPI as `matlabengine`.
EconEnv uses it rather than a console subprocess because it is the supported
route and it exchanges arrays natively, so a DataFrame becomes a real MATLAB
`table` rather than parsed text.

## Installing the bridge

The engine package is versioned to the MATLAB release **and** to your Python,
and both windows are narrow:

| MATLAB | Install | Python |
|---|---|---|
| R2024a | `pip install "matlabengine==24.1.*"` | 3.9 – **3.11** |
| R2024b | `pip install "matlabengine==24.2.*"` | 3.9 – 3.12 |
| R2025a | `pip install "matlabengine==25.1.*"` | 3.9 – 3.12 |
| R2025b | `pip install "matlabengine==25.2.*"` | 3.9 – 3.12 |
| R2026a | `pip install "matlabengine==26.1.*"` | 3.9 – **3.13** |

**Python 3.13 needs R2026a or newer** — it is the first release whose Engine API
supports it. On an earlier MATLAB, run EconEnv on a Python that release can
drive:

```bash
conda create -n econ python=3.11
conda activate econ
pip install econenv "matlabengine==24.1.*"
```

A release newer than this table still resolves: MathWorks numbers the series to
a rule — `R20YYa` is `YY.1`, `R20YYb` is `YY.2` — so EconEnv computes the pin for
R2026b and beyond rather than falling off the end of a lookup table.

`econenv doctor` works this out for you: it names a pin for every MATLAB
release you have installed, and when your Python suits none of them it says
which release *would* work on it and which Python your own MATLAB can drive —
rather than handing you a command that cannot work.

## Which release actually starts

If several MATLAB releases are installed, the one that starts is the one your
*engine package* matches — not the newest on disk. On a machine with R2024a and
R2025a and `matlabengine 24.1.4`, it is **R2024a** that runs, and that is what
`%econ status` reports.

Reporting the newest install instead would repeat the mistake the EViews adapter
used to make: naming a version you are not running.

## Using it

```python
%%matlab -i df -o beta
fit = fitlm(df, 'y ~ x1 + x2');
beta = fit.Coefficients.Estimate;
disp(fit)
```

| Flag | Meaning |
|---|---|
| `-i NAME` | push a DataFrame in as a MATLAB `table` |
| `-o NAME` | bring a MATLAB variable back to Python |
| `-q` | suppress output |
| `--no-graphs` | do not capture figures this cell draws |
| `--result` | return the `ExecutionResult` instead of displaying it |

## Starting is slow — once

A cold start takes roughly a minute. The first cell that uses MATLAB pays for
the whole session; every later one is fast. That is also why `%econ status`
never starts it: detection reads the disk and the registry only.

If MATLAB is already open, share it and EconEnv attaches instead of launching a
second copy:

```matlab
matlab.engine.shareEngine
```

```python
%econ config matlab.shared MATLAB_shared
```

## Getting data in and out

`-i` sends a Python object into MATLAB; `-o` brings a MATLAB variable back.
Repeat either flag for several names.

```python
%%matlab -i x -i df -o beta -o T
fit  = fitlm(df, 'y ~ x1 + x2');
beta = fit.Coefficients.Estimate;
T    = fit.Coefficients;
```

### Python → MATLAB

| Python | MATLAB |
|---|---|
| `int`, `float`, NumPy scalar | `double` scalar |
| `bool` | `logical` |
| `complex` | complex `double` |
| `str` | `char` |
| list, tuple, 1-D array | `double` **column** vector |
| 2-D array | `double`, shape preserved |
| list of `str` | `string` array |
| `pandas.Series` | one-column `table` |
| `pandas.DataFrame` | `table` |

A 1-D sequence lands as a **column**, because that is the orientation a
regressor, a series and a table column all already use. To get a row instead:

```python
%econ config matlab.vectors row
```

`None` is refused rather than quietly becoming `NaN` — MATLAB has no
equivalent, and guessing which one you meant is worse than asking.

### MATLAB → Python

| MATLAB | Python |
|---|---|
| numeric scalar | `float` (`int` for `int8`…`uint64`) |
| complex scalar | `complex` |
| logical scalar | `bool` |
| `char` / scalar `string` | `str` |
| row **or** column vector | 1-D `numpy.ndarray` |
| 2-D matrix | 2-D `numpy.ndarray` |
| `string` array, cellstr | `list` of `str` |
| `table` / `timetable` | `pandas.DataFrame` |

A vector comes back **flat** whichever way MATLAB stored it. MATLAB has no 1-D
array — `[1 2 3]` is 1×3 and `[1;2;3]` is 3×1 — so preserving the singleton
axis would hand Python a `(1, 3)` array for something every researcher reads as
three numbers. Reshape in MATLAB when the orientation is itself the result.

A struct, a mixed cell array or a model object raises `DataTransferError`
naming the MATLAB class, rather than guessing at a conversion:

```
's' is a MATLAB struct, which EconEnv cannot convert to Python.
Hint: Convert it in MATLAB first: struct2table for a struct, a table for
mixed columns, or pull the fields you need one at a time.
```

### `pull` and `pull_value`

`econenv.pull` is frame-oriented — that is the contract `move` and `broadcast`
depend on, and it is why a table comes back as a DataFrame. `pull_value` gives
the natural type instead, and is what `-o` uses:

```python
econenv.pull("matlab", "T")          # DataFrame — a table or a matrix
econenv.pull_value("matlab", "y")    # 10.0 — a number is a number
```

Asking `pull` for a scalar says so and names the other one, instead of failing
inside pandas.

## Google Colab, through a local runtime

Colab normally runs on a Linux VM at Google, where your MATLAB is not installed
and your licence does not reach. The **local runtime** keeps the Colab
interface in the browser and runs the kernel on your own machine, so MATLAB,
EViews and a local Stata all work exactly as in a local notebook.

```
Colab UI (browser) → local Jupyter server → EconEnv → MATLAB
```

Everything below is available from a cell with `%econ matlab colab`.

**1. Activate the environment that has EconEnv** — Windows CMD or PowerShell:

```bat
<your-env>\Scripts\activate
python --version
```

**2. Start Jupyter so Colab is allowed to talk to it** — same terminal:

```bash
jupyter notebook --ServerApp.allow_origin="https://colab.research.google.com" --ServerApp.allow_credentials=True
```

Jupyter picks a free port itself; there is nothing special about 8888. Add
`--ServerApp.port=8890` if you need a fixed one, and if it is busy Jupyter says
so and you can pick another.

**3. Copy the address it prints**, token and all:

```
http://localhost:<PORT>/?token=<TOKEN>
```

**4. In Colab**: Connect → *Connect to local runtime* → paste → Connect.

**5. Check the kernel really is yours** — Python cell:

```python
import sys; print(sys.executable)
```

It must show your own environment, not `/usr/bin/python3`.

**6. Then nothing is different** — Python cell:

```python
%load_ext econenv
%econ status

%%matlab
version
```

> **Security.** The local runtime executes notebook code on your computer, with
> your files and your installed software. Connect only notebooks you trust, and
> never share the token — it is the credential to your kernel.

Variables set in one Colab cell are found by `-i` without any help. Earlier
versions looked in two namespaces and missed the one Colab uses, so `%%matlab
-i x` raised `NameError` until you wrote `get_ipython().user_ns["x"] = x` by
hand. That workaround is no longer needed.

## Finding MATLAB commands

```python
%econ matlab                     # the categories
%econ matlab timeseries          # unit roots, ARIMA, VAR
%econ matlab find cointegration  # search everything
%econ matlab colab               # the local-runtime setup above
%econ matlab export              # saving figures and tables
%econ matlab doctor              # diagnose the setup
```

102 commands, every one resolved against a live MATLAB, each naming the toolbox
it needs — because a function you have not licensed fails with `Unrecognized
function or variable`, which reads like a typo and is not one. The full list is
[matlab-commands.md](matlab-commands.md).

## Figures

Captured automatically, once each — MATLAB keeps figures open until closed, so
without a memory of what has been shown one plot would reappear under every
later cell.

```python
%econ config matlab.graphics pdf    # png | svg | pdf | off
%econ config matlab.dpi 300
```

For journal submission use `pdf`: vector figures stay sharp at any size. See
[export.md](../export.md).

## OLS, and the comparison

MATLAB implements `_fit_ols` through `fitlm`, so it appears in
`compare_ols` alongside the other four:

```python
econenv.compare_ols(df, "y ~ x1 + x2")
```

```
         python    eviews    matlab         r     stata
_cons  1.480534  1.480534  1.480534  1.480534  1.480534
x1     1.933102  1.933102  1.933102  1.933102  1.933102
```

MATLAB's `fitlm` reports AIC and BIC on the same $-2\ell + 2k$ basis as
statsmodels and Stata, so those three agree where R's and EViews' differ. R
counts $\sigma^2$ as a parameter; EViews divides by $n$.

## Tables in the notebook

`disp(tbl)` returns MATLAB's own console output — monospace text, exactly as
MATLAB printed it. For a real Jupyter table, name it on the way out:

```python
%%matlab -o coefs
mdl = fitlm(df, 'y ~ x');
coefs = mdl.Coefficients;
```

```python
coefs      # a DataFrame, rendered as a table
```

## Troubleshooting

**`matlab.engine` will not import.** Almost always a version mismatch — either
the engine package against the MATLAB release, or against your Python. Run
`econenv doctor`; it prints the exact pin.

**`Unrecognized function or variable`.** The function may be in a toolbox you do
not have, or on a path MATLAB has not been told about:

```python
%%matlab
addpath('C:/path/to/code')
```

**A cell seems to hang.** The first one is starting MATLAB. Subsequent cells are
fast; share an already-open session to skip the wait entirely.

**`'x' is not defined in Python`** for a variable you can see. Fixed in 1.2.0 —
the lookup consulted two namespaces and Colab's local runtime uses a third.
Upgrade rather than working around it with `get_ipython().user_ns[...]`.

**`ValueError: Must pass 2-d input. shape=()`** from `-o`. Also fixed in 1.2.0:
every pull went through `pandas.DataFrame`, so a scalar failed inside pandas.
Scalars now come back as numbers.

**`Unrecognized function or variable` for a function that exists.** It is in a
toolbox this licence does not cover. `%econ matlab find <name>` says which one,
and `ver` lists what you have.

---

Related: [export](../export.md) · [data exchange](../data-exchange.md) ·
[magics](../magics.md)
