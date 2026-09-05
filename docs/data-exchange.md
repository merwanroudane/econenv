# Data exchange

The point of brief §10: create a DataFrame **once**, in Python, and use it
everywhere — with no `to_csv` / `import delimited` / `write.csv` chain.

## The three operations

```python
econenv.push(engine, name, obj)          # Python  → engine
econenv.pull(engine, name)               # engine  → Python
econenv.move(source, target, name)       # engine  → engine
```

They exist as magics too:

```python
%econ push r df --as mydata
%econ pull stata --as back
%econ move stata r auto
```

and per-engine shorthands: `%stata_push`, `%stata_pull`, `%eviews_push`,
`%eviews_pull`, `%Rec_push`, `%Rec_pull`; and inline in a cell magic:

```python
%%Rec -i df -o results
```

## What `move` actually does

Routes through pandas, because pandas is the canonical interchange object. The
frame is returned, so both legs' conversion notes stay inspectable:

```python
frame = econenv.move("stata", "eviews", "auto")
econenv.transfer.conversion_report(frame)
econenv.transfer.metadata(frame).history
# ['stata -> python -> eviews']
```

The user never writes a file. Temp files that a transport needs internally live
in a private directory and are deleted immediately.

## Transports per engine

| Engine | Transport | Notes |
|---|---|---|
| Python | direct object | no copy |
| R | Arrow feather, else typed CSV + JSON schema | see [engines/r.md](engines/r.md) |
| Stata | PyStata `pdataframe_to_data` / `_from_data` | in-memory, no file |
| EViews | COM `PutSeries` / `GetSeries`, series by series | VARIANT-marshalled and verified |

## Naming

Each engine has its own rules, and each rename is **reported**, never silent:

| Engine | Limit |
|---|---|
| Stata | 32 chars, `[A-Za-z_][A-Za-z0-9_]*`, no reserved words |
| EViews | 24 chars, no reserved words (`c`, `resid`, `na`, `trend`, …) |
| R | no leading digit, no reserved word |

```
UserWarning: EconEnv push -> stata: [warning] GDP growth: renamed to
'GDP_growth' for Stata
```

Collisions after sanitising are disambiguated with a numeric suffix, also
reported.

## Indexes

| Index | Stata | R | EViews |
|---|---|---|---|
| `RangeIndex` | dropped | dropped | dropped |
| named index | becomes a column | becomes a column | becomes a column |
| `DatetimeIndex` | becomes a `%tc`/`%td` column | becomes a `Date`/`POSIXct` column | becomes the **workfile frequency** |
| 2-level `MultiIndex` | two columns; recorded as (panel, time) | two columns | two columns |

EViews is the one that uses the index structurally: a quarterly
`DatetimeIndex` produces `create Q 2000Q1 2009Q4`, and the dates come back on
pull.

## Scalars and matrices

```python
econenv.engine("stata").pull_scalar("e(r2)")        # full precision
econenv.engine("stata").pull_matrix("r(table)")     # ndarray
econenv.engine("eviews").pull_scalar("eq1.@r2")
econenv.engine("eviews").pull_matrix("m1")
econenv.engine("r").pull_scalar("sd(x)")
```

## Type fidelity

See [data-types.md](data-types.md) for the full table and the measured
round-trip results.

## One dataset, every engine

The common opening move of a multi-engine session:

```python
econenv.broadcast("macro", df)
```

```
{'eviews': None, 'matlab': None, 'r': None, 'stata': None}
```

`None` means it arrived. An engine that is missing or fails is recorded rather
than stopping the rest — a machine without MATLAB should still get the data into
R and Stata. Pass `strict=True` to raise instead, or name the engines you want:

```python
econenv.broadcast("macro", df, ["r", "stata"])
```

## What can move where, on this machine

```python
econenv.transfer_matrix()
```

```
        available       state  receives  sends version
engine
Python       True  configured      True   True  3.11.0
EViews       True     running      True   True      13
MATLAB       True     running      True   True  R2024a
R            True     running      True   True   4.5.2
Stata        True     running      True   True    19.5
```

This reports what is possible *here*, not in principle. An engine that is
installed but not configured cannot take your data, and finding that out before
you start is cheaper than a failure mid-session.

## Engine to engine

```python
econenv.move("stata", "matlab", "macro")
econenv.move("eviews", "r", "macro", target_name="from_eviews")
```

The frame passes through pandas so the conversion notes from both legs stay
inspectable, but no file is written and you never handle the intermediate.

## A note on EViews naming

Pushing to EViews creates a **page of series**, not an object named after the
frame — there is no `macro` object in the workfile, only `X`, `Y`, `Z`. EconEnv
remembers the name you pushed under so `pull("eviews", "macro")` returns the page
rather than failing, which keeps the round trip symmetric with the other four.
Inside a `%%eviews` cell, refer to the series by their own names.
