# Milestone and issue plan

Proposed GitHub milestones and issues (brief §54). Labels to create first:

`engine:python` `engine:r` `engine:stata` `engine:eviews`
`interoperability` `jupyter` `models` `bug` `enhancement` `documentation`
`testing` `platform:windows` `platform:linux` `platform:macos` `good-first-issue`

---

## Milestone v0.1 — Execution and engine management ✅ **complete**

| Issue | Labels |
|---|---|
| Repository and technology audit | `documentation` |
| Engine abstraction and registry | `enhancement` |
| Layered configuration and discovery | `enhancement` |
| Python engine | `engine:python` |
| R engine, subprocess backend | `engine:r` |
| Stata engine via PyStata | `engine:stata` |
| EViews engine via COM | `engine:eviews` |
| Data bridges for all three | `interoperability` |
| Magics, with collision handling | `jupyter` |
| `ExecutionResult` / `ModelResult` / `Figure` | `enhancement` |
| Diagnostics with actionable fixes | `enhancement` |
| Cross-engine OLS comparison | `models` |
| CLI and service layer | `enhancement` |
| Test suite, CI, docs, examples | `testing` `documentation` |

---

## Milestone v0.2 — Data interoperability, deepened

| Issue | Labels | Notes |
|---|---|---|
| Stata value labels from pandas categoricals | `engine:stata` `interoperability` | currently sent as strings with a warning |
| Preserve Stata extended missing values (`.a`–`.z`) | `engine:stata` `interoperability` | needs a pandas extension dtype or a sidecar |
| Stata variable labels round-trip | `engine:stata` | `sfi.Data.setVarLabel` |
| EViews alpha series beyond 5000 rows | `engine:eviews` | current per-observation loop is too slow |
| EViews matrix/scalar push | `engine:eviews` | `Put` for matrices |
| Read EViews alpha series on pull | `engine:eviews` | `GetSeries` does not return them |
| Arrow transport for Stata and EViews | `interoperability` | via temp `.dta` / Excel where COM allows |
| `%%R` timezone fidelity | `engine:r` | currently normalised to UTC |
| Verify rpy2 backend | `engine:r` `testing` | never run — no rpy2 on the dev machine |
| Verify Linux and macOS | `platform:linux` `platform:macos` `testing` | designed for, never run |

---

## Milestone v0.3 — Estimators beyond OLS

| Issue | Labels |
|---|---|
| Logit and Probit across four engines | `models` |
| IV / 2SLS | `models` |
| Panel FE and RE | `models` |
| WLS and weights in `ModelSpec` | `models` |
| Cluster-robust covariance, with each engine's convention documented | `models` |
| `ModelResult` for multi-equation output | `models` |

Each carries the same obligation as OLS: implement it in every engine that
supports it, keep `raw`, and document every default that differs.

---

## Milestone v0.4 — Time series and comparison depth

| Issue | Labels |
|---|---|
| ARIMA, VAR, VECM, ARDL, GARCH | `models` |
| Unit-root and cointegration tests | `models` |
| Comparison report export (HTML / LaTeX) | `enhancement` |
| Tolerance profiles per estimator | `models` |

---

## Milestone v0.5 — Reproducibility and provenance

| Issue | Labels |
|---|---|
| Automatic per-cell provenance capture | `enhancement` |
| Run manifest export | `enhancement` |
| Replay a manifest and verify the results | `enhancement` |
| Lockfile-style environment pinning | `enhancement` |

---

## Milestone v1.0 — Stable API

| Issue | Labels |
|---|---|
| Freeze the public API; deprecation policy | `enhancement` |
| JupyterLab cell-toolbar extension | `jupyter` |
| Polyglot cell metadata (engine in cell metadata) | `jupyter` |
| Evaluate a custom EconEnv kernel — cost vs benefit | `jupyter` |
| MATLAB, Julia, Gretl adapters | `enhancement` |

---

## Open questions to settle before v1.0

1. **Custom kernel or not.** The extension approach has worked. A kernel buys
   cell-level engine selection without magics and proper per-language
   completion; it costs the Jupyter messaging protocol, four sets of
   completion/introspection/interrupt semantics, and a maintenance burden
   against four vendors' release cycles. Decide with evidence, not aesthetics.

2. **How far to take formula translation.** `ModelSpec` deliberately refuses
   interactions today. Options: keep refusing (honest, limited); build a real
   intermediate representation with per-engine expansion (large, correct);
   or expand interactions in pandas before dispatch (simple, changes the data).

3. **Concurrency.** One notebook, four engines, one thread. Whether parallel
   cross-engine estimation is worth the session-safety work is unresolved —
   PyStata in particular is not obviously thread-safe.

4. **Licence compliance in shared deployments.** EconEnv cannot police Stata
   and EViews concurrent-session limits. Documented; whether it should warn
   more loudly on a server is open.
