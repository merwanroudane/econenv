# GAUSS

Driven through GAUSS's terminal executable, `tgauss`. Everything on this page
was established by running GAUSS 26.1.1 rather than read from documentation —
which matters, because several plausible assumptions turned out to be wrong.

## Installing

Nothing to install beyond GAUSS itself. EconEnv looks, in order, at:

1. `%econ config gauss.home`
2. the `GAUSSHOME`, `MTENGHOME` and `GAUSS_HOME` environment variables
3. `C:\gauss*` and `C:\Program Files\GAUSS*` on Windows,
   `/usr/local/gauss*` and `/opt/gauss*` on Linux, `/Applications/GAUSS*` on macOS

GAUSS does **not** install into Program Files by default on Windows — a typical
path is `C:\gauss26` — so looking only where other vendors put things finds
nothing.

```python
%econ config gauss.home C:/gauss26
```

## Which installation runs

Several GAUSS versions can be installed and they do not all work. `%econ doctor
gauss` names the one EconEnv will actually use and lists the others:

```
GAUSS
  ✔ PASS  GAUSS installation: using C:\gauss26 (also installed: C:\gauss25)
  ✔ PASS  GAUSS executable: tgauss.exe — 26.1.1
  ✔ PASS  GAUSS backend: cli — one process per cell
```

Reporting the newest directory instead would repeat the mistake the EViews
adapter made with ProgIDs and the MATLAB adapter with engine releases: naming a
version you are not running.

## Using it

```python
%%gauss
x = rndn(100, 3);
print meanc(x);
```

`%econ gauss` is a searchable catalogue of 95 commands — `%econ gauss
regression`, `%econ gauss find missing`. The full list is
[gauss-commands.md](gauss-commands.md).

### Three things that catch everyone out

**Every statement ends with a semicolon.** A missing one is a syntax error.

**A bare expression prints nothing.** Python echoes the last value; GAUSS needs
`print x;`.

**`~` joins columns and `|` stacks rows.** This is how a design matrix is
built, and it has no counterpart in the other engines' syntax:

```gauss
X = ones(rows(y),1) ~ x1 ~ x2;
```

### And one that looks like a bug

GAUSS **compiles the whole cell before running any of it**. A mistyped name on
the last line means the first line never ran either, so a cell can produce no
output at all rather than a partial result. EconEnv says so:

```
GAUSS compile error — G0025: Undefined symbol: 'no_such_thing'
  at line 2 of the cell
  GAUSS compiles the whole cell before running any of it, so nothing in
  this cell ran — not even the lines before the error.
```

Without that sentence the natural reading is "my print statement did nothing",
which sends people looking in the wrong place.

## Getting data in and out

```python
%%gauss -i df -o b
y = df[.,3];
X = ones(rows(df),1) ~ df[.,1] ~ df[.,2];
b = y / X;
```

### Python → GAUSS

| Python | GAUSS |
|---|---|
| `int`, `float`, NumPy scalar | scalar |
| `bool` | 1 or 0 |
| `str` | string |
| list, tuple, 1-D array | column vector |
| 2-D array | matrix, shape preserved |
| `pandas.DataFrame` | numeric matrix |

A GAUSS matrix holds **only numbers**. A DataFrame's text columns cannot cross,
and they are **named in a warning** rather than dropped in silence — a
regression run on a frame that quietly lost a column is the worst outcome
available here. The column names are kept on the Python side, so the frame
comes back with them.

`NaN` crosses as a GAUSS missing value and returns as `NaN`, so a gap stays a
gap instead of becoming a number that would enter a regression.

A name GAUSS already owns — `vec`, `rows`, `ones`, `sumc` — cannot take a
variable. EconEnv refuses it before GAUSS sees it and suggests another, rather
than letting a raw `G0276` through.

### GAUSS → Python

| GAUSS | Python |
|---|---|
| 1×1 matrix | `float` |
| row or column vector | 1-D `numpy.ndarray` |
| matrix | 2-D `numpy.ndarray` |
| string | `str` |

### Precision

Numbers cross at **seventeen significant digits**, which round-trips an IEEE
double exactly.

This is not a detail. GAUSS's own `csvWriteM` writes about fifteen, and a round
trip through it moves a double by roughly 3×10⁻¹⁵ — enough to put GAUSS out of
step with the machine-precision agreement that is the point of `compare_ols`.
EconEnv ships its own writer (`econenv_bridge.gss`) for that reason, and the
measured round-trip difference is **0**.

## What carries between cells, and what does not

Each cell is a fresh `tgauss` process, so nothing survives on its own. EconEnv
carries the **values** across using GAUSS's own `save` and `load` — matrices to
`.fmt`, strings to `.fst`, in a session directory.

**Procedures, `#include`s and library loads do not carry.** Define a `proc` in
the same cell that uses it.

That limit is stated rather than worked around. Rebuilding a session by
replaying earlier cells would silently re-run their side effects, which is worse
than carrying less.

## Figures

Plots are captured and displayed automatically:

```python
%%gauss
x = seqa(0, 0.1, 100);
y = sin(x);
struct plotControl p;
p = plotGetDefaults("xy");
plotSetTitle(&p, "Sine wave");
plotXY(p, x, y);
```

The default is **SVG** — vector, and what most journals ask for.

```python
%econ config gauss.graphics svg    # svg | png | pdf | off
%econ config gauss.width 1600      # pixels, for png only
%econ config gauss.height 1200
```

A cell that draws nothing produces no figure. EconEnv only asks GAUSS to save a
plot when the cell actually contains a plotting call — otherwise `plotSave`
would write out whatever was drawn last, and the same figure would reappear
under every later cell.

`--no-graphs` turns capture off for one cell.

> **`plotSave` measures raster and vector differently.** The two numbers are
> *pixels* for PNG and *inches* for SVG and PDF, so the same `12 | 9` that gives
> a sensible SVG gives a 12×9 **pixel** PNG. EconEnv passes the right units for
> the format you chose.

> **A `struct` cannot be carried between cells.** GAUSS refuses to `save` one —
> it is a compile error. Since a plotting cell declares `struct plotControl p;`
> and then assigns to `p`, EconEnv recognises struct declarations and leaves
> them out of the carried workspace. You will not notice this unless you expect
> a plot control to survive into the next cell, which it does not.

## OLS, and the comparison

GAUSS's own `ols` procedure, so the comparison carries GAUSS's numbers:

```python
econenv.compare_ols(df, "y ~ x1 + x2")
```

```
         python    eviews     gauss    matlab         r     stata
term
_cons  1.542691  1.542691  1.542691  1.542691  1.542691  1.542691
x1     2.028686  2.028686  2.028686  2.028686  2.028686  2.028686
x2    -0.485249 -0.485249 -0.485249 -0.485249 -0.485249 -0.485249
```

Maximum disagreement with Python is 1.8×10⁻¹⁵. R², adjusted R²,
log-likelihood, AIC, BIC and RMSE match statsmodels, Stata and MATLAB exactly.

`ols` reports coefficients, standard errors, sigma and R² and stops there, so
the t statistics, p-values, confidence interval and information criteria are
computed **in GAUSS from its own residuals**, using `cdftc` and `cdftci`, on
statsmodels' conventions — so a difference between engines is a real difference
and not a normalisation choice.

## Google Colab

Works through Colab's **local runtime**, where the kernel runs on your own
machine. See [the Colab guide](../colab.md); `%econ gauss colab` prints the
setup from inside the notebook.

On a hosted Colab runtime GAUSS is possible only if you install a Linux GAUSS
and hold a licence covering it — the same situation as Stata and MATLAB.

## The backend, and what comes next

`GaussEngine` selects a *backend* rather than talking to a process directly, so
a native binding to the GAUSS Engine C API can be added without changing
anything above it. That would bring a persistent workspace and faster transfers.

Today only the CLI backend exists. `%econ config gauss.backend native` is
reported as unavailable rather than silently downgraded, because a user who
asked for the native backend should know they did not get it.

## Troubleshooting

**A cell printed nothing.** Almost always the compile-before-run rule above.
Check the error text — it names the line.

**`Illegal use of reserved word`.** The name belongs to a GAUSS built-in. Use
another; `%econ gauss find <name>` says what the built-in does.

**A variable from an earlier cell is gone.** Only top-level values carry.
Procedures and library state do not.

**`No GAUSS installation was found`.** Set the path:
`%econ config gauss.home C:/gauss26`.

---

Related: [command reference](gauss-commands.md) · [comparison](../comparison.md) ·
[data exchange](../data-exchange.md) · [magics](../magics.md)
