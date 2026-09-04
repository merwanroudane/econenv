# Architecture

## Layers

```
JupyterLab / Notebook
      │
      ▼
IPython / Python kernel                    ← the one and only kernel
      │
      ▼
econenv (IPython extension)
      │
      ├── magics/      %econ · %R/%Rec · %stata · %eviews
      ├── services.py  the shared service layer (CLI and magics both call it)
      ├── models/      ModelSpec · registry · cross-engine comparison
      ├── diagnostics  doctor
      ├── transfer.py  push / pull / move · snapshots · provenance
      │
      ▼
engines/registry.py                        ← the extension point
      │
      ├── PythonEngine   host interpreter
      ├── REngine        subprocess | rpy2
      ├── StataEngine    PyStata
      └── EViewsEngine   COM (comtypes)
              │
              ▼
        bridges/        pandas ↔ engine-native, per engine
```

## Three rules

### 1. No custom kernel in v0.1

A polyglot Jupyter kernel means implementing the Jupyter messaging protocol,
owning completion, introspection, interrupt and display for four languages, and
maintaining it against four vendors' release schedules. An IPython extension
gets the same user-visible result — one notebook, four engines — for a fraction
of that. The trade is evaluated again in the roadmap, not assumed away.

Note that EViews 14 ships `XeusEViews.exe`, its own Jupyter kernel. Using it
would mean a *second* notebook, which is the problem this project exists to
solve.

### 2. Nothing above the engine layer touches a vendor API

`magics/`, `services.py`, `models/` and `diagnostics.py` import
`econenv.engines.registry` and call `BaseEngine` methods. None of them imports
`pystata`, `comtypes` or `rpy2`. That is what makes "add MATLAB" a matter of
writing one adapter rather than editing the core.

The one place this is visibly enforced: `%eviews_show` does not reach into the
COM handle; `EViewsEngine.set_visible()` exists so it does not have to.

### 3. Never hide a difference

* Lossy conversions emit a `UserWarning` naming the column and what changed.
* `ConversionReport` travels with the frame so it can be inspected later.
* Cross-engine comparison applies **both** an absolute and a relative
  tolerance, and lists the documented reasons two engines can legitimately
  differ.
* `EngineInfo.version` is the version of the *connected* session, never the one
  found on disk — for EViews those genuinely differ.

## The engine contract

Every engine implements five hooks:

| Hook | Responsibility |
|---|---|
| `_detect()` | Locate the software. Cheap, no side effects, never starts anything. |
| `_start()` | Bring up a persistent session. |
| `_stop()` | Tear it down. Safe to call twice. |
| `_execute(code)` | Run code, return an `ExecutionResult`. |
| `_version()` | The version of the running session. |

and optionally `_push_frame`, `_pull_frame`, `_push_scalar`, `_pull_scalar`,
`_pull_matrix`, `_fit_ols`.

`BaseEngine` owns everything shared: lifecycle bookkeeping, autostart, timing,
error translation, capability gating, and the `EngineInfo` snapshot. An adapter
that forgets to set `result.engine` still gets it set.

### States

```
UNKNOWN → NOT_INSTALLED          detect() found nothing
        → CONFIGURED             found, EconEnv knows how to start it
        → RUNNING                a live session exists
        → STOPPED / FAILED
```

`available` is true for CONFIGURED, RUNNING and STOPPED. `%econ status` shows
the state; `%econ doctor` explains it.

## Adding an engine

```python
from econenv.engines.base import BaseEngine, Capability
from econenv.engines.registry import register

@register
class JuliaEngine(BaseEngine):
    name = "julia"
    display_name = "Julia"
    declared_capabilities = (Capability.EXECUTE, Capability.PERSISTENT_SESSION)

    def _detect(self): ...
    def _start(self): ...
    def _stop(self): ...
    def _execute(self, code, **kwargs): ...
```

Third-party packages can register without importing EconEnv at all, through the
`econenv.engines` entry point group:

```toml
[project.entry-points."econenv.engines"]
julia = "econenv_julia.engine:JuliaEngine"
```

A plugin that fails to import is reported in `%econ status`, not raised — one
broken third-party engine must not take the other four down with it.

## Why `pandas.DataFrame` is the interchange object

It is the only structure all four ecosystems already convert to and from
reliably, and it is what the user already has. The transports underneath differ
per engine (PyStata's in-memory API, COM arrays, Arrow or typed CSV), but the
`push_frame` / `pull_frame` contract does not — which is what lets
`transfer.move()` connect any pair of engines without knowing which two.

Arrow is used where both sides support it, and the design leaves room for an
Arrow-first backend later without changing the contract.
