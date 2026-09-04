# Diagnostics

```bash
econenv doctor
econenv doctor eviews
econenv doctor --deep          # also start each engine
econenv doctor --json
```

```python
%econ doctor
%econ doctor r --deep
report = econenv.doctor()
report.ok           # False if anything is ERROR
report.warnings
report.to_dict()
```

## The rule

Every WARNING and ERROR carries a **fix**. A diagnostic that says "R not found"
without saying what to do about it is only half a diagnostic — and there is a
test asserting that no warning or error ships without one.

```
! WARNING COM version binding: several EViews versions are installed and the
          generic EViews.Manager ProgID binds to whichever registered last
              → Pin one: `%econ config eviews.progid EViews14.Manager`.
                `%econ status` always shows the version actually connected.
```

## What is checked

**host** — Python version and path, OS, architecture, IPython, pandas, numpy,
jupyterlab, pyarrow, a writable temp directory.

**config** — which config file, which environment variables, which runtime
overrides are in play.

**r** — every installation found and how; `R_HOME`; R on `PATH`; the console
front-end (`Rterm.exe` / `bin/R`); whether rpy2 is importable and therefore
which backend is live.

**stata** — every installation, its edition, whether it has
`utilities/pystata`; `stata_setup`; whether the configured edition contradicts
the executable found.

**eviews** — `comtypes`; installations on disk; registered COM ProgIDs; whether
the generic ProgID is ambiguous; `pyeviews`'s state (informational — EconEnv
does not use it).

## `--deep`

Starts each available engine and runs a trivial command. It proves the licence
works and reports the version actually connected. It is opt-in because it
launches Stata and EViews and can consume a licence seat.

## Status meanings

| | |
|---|---|
| PASS | works |
| WARNING | works, but something is ambiguous or suboptimal |
| ERROR | will not work as configured |
| SKIP | not applicable here (EViews off Windows, rpy2 not installed) |

A missing engine is a **warning**, not an error. EconEnv is useful with any
subset.

## Exit codes

`econenv doctor` returns 0 when there are no errors, 1 when there are — usable
in CI.

## Reporting a problem

```bash
econenv doctor --deep --json > doctor.json
econenv snapshot snapshot.json
```

Neither contains licence keys or serial numbers: EconEnv's logging redacts
anything matching a credential or serial pattern before it reaches a record
(brief §33).
