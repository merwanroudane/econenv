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
carries two things across:

- **values**, using GAUSS's own `save` and `load` — matrices to `.fmt`, strings
  to `.fst`, in a session directory;
- **procedure definitions**, re-declared in each later cell.

```python
%%gauss
proc (1) = sq(a);
    retp(a .* a);
endp;
```

```python
%%gauss
print sq(9);     /* 81 — the procedure survived into a new process */
```

Redefining a procedure wins, and the old definition is not emitted alongside it
(GAUSS rejects two definitions of one name in the same program).

Carrying a *definition* is safe in a way that replaying statements is not: a
`proc ... endp;` block computes nothing and touches nothing, so re-declaring it
cannot change an answer. Re-running `x = x + 1;` or a `writetable` could, which
is why EconEnv does not rebuild a session from the cells you have run.

**What still does not carry**: `#include`s, `library` statements, and anything
whose effect is not a value or a procedure. Those need the licensed GAUSS
Engine, which gives a genuinely persistent workspace.

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

Today only the CLI backend exists, and the reason is worth stating plainly:
**the GAUSS Engine is a separate product.** A desktop installation contains no
`mteng` library, and its `gauss.dll` exports no `GAUSS_*` symbols — so on a
normal machine there is nothing to bind to, and nothing to test a binding
against.

Two other routes were tried and do not work:

- **Piping `tgauss`.** It consumes lines written to its stdin and prints its
  prompt, but produces no results through the pipe; it wants a real console.
  This is precisely why Aptech sells the Engine API.
- **A driver program that `run`s a command file in a loop.** `run` *does* share
  the workspace, but it transfers control rather than returning, so the loop
  never continues.

So a persistent GAUSS workspace — one where procedures and `#include`s survive
between cells — needs the licensed Engine. If you have it, EconEnv finds it:

```python
%econ config gauss.backend native
%econ doctor gauss
```

reports whether the library is present (looked for under `MTENGHOME`, then
beside the installation) and distinguishes "not on this machine" from "found,
but EconEnv has no binding yet". `auto` and `cli` are unaffected.

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
