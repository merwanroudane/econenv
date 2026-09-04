# Reproducibility and provenance

## Environment snapshot (brief §20)

```python
econenv.snapshot()
econenv.snapshot(deep=True)                 # start engines to read true versions
econenv.transfer.save_snapshot("env.json")
```

```bash
econenv snapshot env.json --deep
```

Records EconEnv's version; OS, release, architecture, processor; Python version,
implementation and executable; every installed Python distribution; each
engine's state, version, edition, home and backend; and — when R is running —
its installed packages with versions.

`deep=True` starts each available engine so the version reported is the one that
would actually run, not the one found on disk. For EViews those can differ; see
[engines/eviews.md](engines/eviews.md).

A snapshot is the thing to attach to a replication package, and the thing to
attach to a bug report. It contains no licence keys or serial numbers.

## Provenance records (brief §21)

```python
econenv.transfer.provenance(engine="stata", code=command, data=df, elapsed=1.2)
```

```python
{'engine': 'stata',
 'engine_version': '19.5',
 'econenv_version': '0.1.0',
 'code_sha256_16': 'a1b2c3d4e5f60718',
 'data_sha256_16': '0f1e2d3c4b5a6978',
 'n_obs': 240,
 'timestamp': '2026-09-04T09:12:44.512+00:00',
 'duration_seconds': 1.2,
 'host': 'WORKSTATION',
 'platform': 'Windows-10-...'}
```

`hash_frame` covers the values **and** the column dtypes, so a frame silently
cast to `float32` hashes differently. `hash_code` is a plain SHA-256 of the
source.

Together they answer, months later: which engine, which version, which code,
which data, when, and how long it took.

## Dataset history

Every transfer appends to the frame's `DatasetMetadata.history`:

```python
frame = econenv.move("stata", "eviews", "auto")
econenv.transfer.metadata(frame).history
# ['stata -> python -> eviews']
```

and `dataset_report` prints the whole picture:

```python
econenv.transfer.dataset_report(frame)
# ['source engine: stata', 'time variable: date', 'frequency: QS',
#  'history: stata -> python -> eviews',
#  'stata pull:\n  [info] Stata extended missing values (.a-.z) all arrive as NaN ...']
```

## What v0.1 does not do yet

Provenance is available but not captured automatically for every cell. The
record shape and the hashing are settled so that turning it on later is a change
of policy, not of design — that is v0.5 on the roadmap.
