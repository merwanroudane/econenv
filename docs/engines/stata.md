# Stata

**Stata 17 or newer.** PyStata ships with Stata 17; earlier releases cannot be
driven from Python.

## PyStata is not on PyPI

It lives inside your Stata installation at `<STATA_HOME>/utilities/pystata`.
EconEnv puts that directory on `sys.path` itself. `stata_setup` does the same
job and is used when present, but it is **not** required.

```bash
pip install "econenv[stata]"    # adds stata_setup; optional
```

## Discovery

`STATA_HOME` → `PATH` → the Windows registry (`HKLM\SOFTWARE\Stata`) → the
usual install roots.

Discovery validates the **executable**, not just the folder — a machine can
easily have a `C:\Program Files\Stata18` directory left over from an uninstall
with no `.exe` inside, and a folder-only check would pick it and then fail at
`init`. An installation is only offered if it has both a launcher and
`utilities/pystata`.

```python
%econ config stata.home "C:/Program Files/StataNow19"
%econ config stata.edition mp        # be | se | mp
```

The edition must be the one you are licensed for; `pystata.config.init` fails
otherwise, and EconEnv's error says so explicitly.

## Magics are PyStata's

`%stata`, `%%stata`, `%mata`, `%%mata`, `%pystata` and the Stata tab-completer
are StataCorp's. EconEnv loads them rather than reimplementing them — they are
maintained against the binary and would only go stale in a copy.

PyStata has no `load_ipython_extension`. `pystata.config.init()` imports
`pystata.ipython.stpymagic`, whose module body calls
`get_ipython().register_magics(...)`, so starting the engine inside IPython
registers `%stata` as a side effect. EconEnv checks the magics manager
afterwards rather than assuming it worked, and reports the real answer in
`%econ engines`.

EconEnv adds four helpers under names that cannot collide:

```
%stata_run / %%stata_run     run and get an EconEnv ExecutionResult
%stata_pull [frame]          Stata's dataset as a DataFrame
%stata_push <df> [as <frame>]
%stata_matrix <name>         r(table), e(b), e(V) ... as an ndarray
```

## Precision

Reading a number out of Stata with `display` rounds it to about **nine
significant figures**. That is enough to make Stata look like it disagrees with
statsmodels at 1e-9 when the two are actually identical to 1e-16.

EconEnv therefore reads through Stata's Function Interface:

* `r()` / `e()` / `s()` → `stata.get_return()` / `get_ereturn()` /
  `get_sreturn()`, which return numpy values
* scalars → `sfi.Scalar.getValue`
* macros and `c()` class → `sfi.Macro.getGlobal`
* matrices → `sfi.Matrix.get`, with `getColNames` for the term names
* anything else → `display %21x`, the exact hexadecimal double, decoded with
  `float.fromhex`

## Frames

`push` with a name creates a Stata **frame**; `"default"` uses the main
dataset.

```python
econenv.push("stata", "default", df)      # clear + load
econenv.push("stata", "panel", df)        # frame create panel
```

Stata refuses to drop the frame it is currently in, so EconEnv steps back to
`default` before recreating a named frame — otherwise the second push of the
same name fails with r(110).

## Session lifetime

`pystata.config.init()` can be called **once per process**. There is no
supported way to re-initialise against a different edition.

* `%econ stop stata` drops EconEnv's handles. It deliberately does **not** call
  `pystata.config.shutdown()`, which would make the session unrecoverable
  without restarting the kernel.
* `%econ restart stata` runs `clear all`.
* Changing edition genuinely needs a fresh kernel. EconEnv says so rather than
  pretending otherwise.

## Errors

PyStata raises `SystemError`. EconEnv translates it, keeps the raw exception,
and points at the right help topic:

```
[stata] variable nosuchvar not found
r(111); (Stata return code r(111); `help r(111)`)
Hint: Run the command with `set trace on` in Stata for a full traceback.
```

`ExecutionResult.metadata["rc"]` carries `c(rc)` for commands that set a return
code without raising.

## OLS

`_fit_ols` runs `regress`, reads `r(table)` through `sfi` (full precision), and
runs `estat ic` for AIC/BIC — which Stata does not put in `e()` after
`regress`. The note about Stata's normalisation still travels with the result;
see [../comparison.md](../comparison.md).

```python
%econ config stata.graph_format svg    # svg | png | pdf
```


## `%%stata` is StataCorp's own magic

EconEnv does not wrap `%stata` / `%%stata` / `%mata` — it loads the official
ones that ship with Stata 17+, because reimplementing them would be strictly
worse (brief §8).

The practical consequence: **EconEnv flags do not apply to it.** This fails:

```python
%%stata --result          # SyntaxError: option --result not allowed
regress y x
```

Use Stata's own options, and move data with `%econ`:

```python
%econ push stata df       # Python -> Stata
```

```python
%%stata
regress y x, robust
```

```python
%econ pull stata          # Stata -> Python
```

`%%stata?` lists what the official magic does accept.
