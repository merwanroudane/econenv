# EconEnv Unified Research Layer
## Full implementation prompt for future releases

**Project:** EconEnv  
**Repository:** https://github.com/merwanroudane/econenv  
**PyPI:** https://pypi.org/project/econenv/  
**Documentation:** https://merwanroudane.github.io/econenv/

---

# 1. Vision

EconEnv should evolve from:

> **One Notebook. Multiple Engines.**

to:

> **One Research Language. Multiple Engines. Unified Results.**

Today, EconEnv unifies execution environments: Python, R, Stata, EViews, and MATLAB can be used in one notebook. The next major step should unify the **research specification itself**.

The researcher should define a model once, then change only the execution engine.

Example:

```python
result = econ.ols(
    data=data,
    formula="y ~ x1 + x2",
    engine="stata"
)
```

Changing the engine should require only:

```python
engine="r"
```

or:

```python
engine="python"
```

or:

```python
engine="eviews"
```

or:

```python
engine="matlab"
```

The model specification remains unchanged.

---

# 2. Why this layer is needed

The same OLS model is written differently in every engine.

Stata:

```stata
regress y x1 x2
```

R:

```r
lm(y ~ x1 + x2, data=data)
```

Python:

```python
sm.OLS(y, X).fit()
```

EViews:

```eviews
equation eq1.ls y c x1 x2
```

MATLAB:

```matlab
fitlm(data, 'y ~ x1 + x2')
```

EconEnv already unifies where these commands run. The next release should unify the **research intent** while preserving native code access.

---

# 3. Core architecture

Do not translate directly from one language to another.

Use this architecture:

```text
Researcher
   |
   v
Unified Research API
   |
   v
Research Intermediate Representation (Research IR)
   |
   +-------------------+
   |                   |
   v                   v
Validation        Capability Registry
   |                   |
   +---------+---------+
             |
             v
      Engine Adapter Layer
             |
   +---------+---------+---------+---------+
   |         |         |         |         |
   v         v         v         v         v
 Python      R       Stata     EViews    MATLAB
   |         |         |         |         |
   +---------+---------+---------+---------+
             |
             v
       Unified Result
             |
     +-------+-------+
     |       |       |
     v       v       v
 Compare   Export  Explain
```

---

# 4. Research Intermediate Representation

Create a neutral internal specification.

Conceptual example:

```python
ModelSpec(
    task="regression",
    estimator="ols",
    dependent="y",
    regressors=["x1", "x2"],
    constant=True,
    covariance="nonrobust",
    cluster=None,
    weights=None,
    options={}
)
```

Potential core specification objects:

```text
ResearchSpec
ModelSpec
TestSpec
ForecastSpec
PlotSpec
DataSpec
ExportSpec
EngineRequest
```

Do not force this exact schema if the repository already has compatible abstractions.

---

# 5. Public API

Recommended style:

```python
from econenv import econ
```

Examples:

```python
econ.describe(...)
econ.corr(...)
econ.ols(...)
econ.logit(...)
econ.adf(...)
econ.kpss(...)
econ.var(...)
econ.forecast(...)
econ.plot(...)
```

Later releases may add:

```python
econ.panel(...)
econ.iv(...)
econ.gmm(...)
econ.did(...)
econ.ardl(...)
econ.cointegration(...)
econ.garch(...)
econ.quantile(...)
econ.svar(...)
econ.vecm(...)
econ.wavelet(...)
econ.optimize(...)
```

Do not implement everything at once.

---

# 6. First MVP

Start with **OLS only**.

The MVP should support:

```python
econ.ols(
    data=data,
    formula="y ~ x1 + x2",
    engine="python"
)
```

and the same call with:

```text
r
stata
eviews
matlab
```

The goal is to prove the architecture before adding more methods.

---

# 7. Engine adapters

Each engine needs its own adapter.

Conceptual interface:

```python
class ResearchEngineAdapter:
    def supports(self, spec):
        ...

    def compile(self, spec):
        ...

    def prepare_data(self, spec, data):
        ...

    def execute(self, spec, data):
        ...

    def normalize(self, raw_result):
        ...
```

Adapters:

```text
PythonAdapter
RAdapter
StataAdapter
EViewsAdapter
MatlabAdapter
```

---

# 8. Native code must remain visible

EconEnv must never become a black box.

Example:

```python
result = econ.ols(...)
```

Then:

```python
result.code
```

should return the generated native code.

For Stata:

```stata
regress y x1 x2
```

For R:

```r
lm(y ~ x1 + x2, data=data)
```

For EViews:

```eviews
equation eq1.ls y c x1 x2
```

For MATLAB:

```matlab
fitlm(data, 'y ~ x1 + x2')
```

Also provide:

```python
result.explain()
```

with:

- requested task
- selected engine
- generated code
- data used
- model options
- routing reason if engine="auto"

---

# 9. Dual mode

The new API must not replace native engine mode.

Keep:

```stata
%%stata
...
```

```r
%%Rec
...
```

```eviews
%%eviews
...
```

```matlab
%%matlab
...
```

Unified mode should simplify common workflows. Native mode remains the escape hatch for advanced engine-specific features.

---

# 10. Engine selection modes

Support:

## Explicit engine

```python
engine="stata"
```

## Multiple engines

```python
engines=["python", "r", "stata"]
```

## Automatic engine

```python
engine="auto"
```

Do not silently switch engines if the user explicitly selected one.

---

# 11. Capability registry

Build a structured capability system.

Example concept:

```yaml
ols:
  python:
    supported: true
    robust_covariance: true
    clustered_covariance: true
  r:
    supported: true
  stata:
    supported: true
  eviews:
    supported: true
  matlab:
    supported: true
```

Possible user-facing calls:

```python
econ.capabilities()
econ.capabilities("ols")
econ.capabilities(engine="stata")
```

Magic equivalents:

```text
%econ capabilities
%econ capabilities ols
%econ capabilities stata
```

Capabilities must come from implemented/tested adapters, not assumptions.

---

# 12. Explainable auto routing

For:

```python
engine="auto"
```

the router should inspect:

1. requested task
2. requested options
3. installed engines
4. engine readiness
5. package/toolbox availability
6. engine capabilities
7. user preferences
8. operating-system constraints

The router must explain its choice.

Example:

```text
Selected engine: Stata

Reason:
- Stata is installed and ready.
- OLS is supported.
- Requested clustered covariance is supported.
- User preference ranks Stata first for regression.

Alternatives:
- R: supported
- Python: supported
```

Never claim one engine is objectively best unless a routing policy explicitly defines the preference.

---

# 13. Unified Result Object

All engines should return a common result interface where meaningful.

Example:

```python
result.engine
result.method
result.coefficients
result.std_errors
result.tvalues
result.pvalues
result.conf_int
result.nobs
result.r2
result.r2_adj
result.residuals
result.fitted
result.code
result.raw
result.metadata
```

Preserve native/raw results:

```python
result.raw
```

Never fabricate a field that an engine/method does not provide.

---

# 14. Unified summary

Provide:

```python
result.summary()
```

for stable EconEnv formatting.

Also preserve native output:

```python
result.native_summary()
```

when possible.

---

# 15. One model, multiple engines

Major feature:

```python
results = econ.ols(
    data=data,
    formula="y ~ x1 + x2",
    engines=["python", "r", "stata", "eviews", "matlab"]
)
```

Return a:

```text
MultiEngineResult
```

Access:

```python
results["python"]
results["r"]
results["stata"]
results["eviews"]
results["matlab"]
```

---

# 16. Cross-engine comparison

Provide:

```python
results.compare()
```

Example output:

| Engine | const | x1 | x2 | R² | N |
|---|---:|---:|---:|---:|---:|
| Python | ... | ... | ... | ... | ... |
| R | ... | ... | ... | ... | ... |
| Stata | ... | ... | ... | ... | ... |
| EViews | ... | ... | ... | ... | ... |
| MATLAB | ... | ... | ... | ... | ... |

Support numerical tolerance:

```python
results.compare(atol=1e-8, rtol=1e-6)
```

Possible statuses:

```text
PASS
WARNING
DIFFERENT SPECIFICATION
FAILED
UNAVAILABLE
```

---

# 17. Specification equivalence

Cross-engine comparisons are only valid when specifications are equivalent.

Track:

- intercept
- sample
- missing-value handling
- covariance estimator
- degrees-of-freedom corrections
- categorical encoding
- weights
- clustering
- optimization defaults
- time-series initialization

If engines use materially different defaults:

- harmonize them explicitly, or
- report the difference

Never silently claim equivalence.

---

# 18. Formula support

Support a common formula interface where practical:

```python
formula="y ~ x1 + x2"
```

Advanced formula syntax can be added gradually.

Do not attempt to support every engine-specific formula feature in the first version.

---

# 19. Canonical data representation

Continue using the existing EconEnv data bridge, with `pandas.DataFrame` as the canonical common representation where appropriate.

Flow:

```text
Python DataFrame
    |
    v
Validation
    |
    v
Engine transfer
    |
    v
Native dataset/table
```

No manual CSV/Excel should be required for normal unified execution.

---

# 20. Data validation

Before execution validate:

- dependent variable exists
- regressors exist
- duplicate column names
- missing values
- unsupported dtypes
- infinite values
- sample size
- panel identifiers when required
- time index when required

Errors should be actionable.

---

# 21. Engine-specific options

Allow an escape hatch for native options.

Example:

```python
result = econ.ols(
    data=data,
    formula="y ~ x1 + x2",
    engine="stata",
    native_options={
        "vce": "cluster id"
    }
)
```

Do not pollute the neutral IR with every native engine option.

---

# 22. Compile-only mode

Provide:

```python
econ.compile(
    method="ols",
    formula="y ~ x1 + x2",
    engine="stata"
)
```

Return native code without executing it.

Useful for:

- teaching
- debugging
- reviewing generated syntax

---

# 23. Dry-run mode

Example:

```python
econ.ols(
    data=data,
    formula="y ~ x1 + x2",
    engine="stata",
    dry_run=True
)
```

Expected:

```text
No model executed.

Generated Stata code:
regress y x1 x2
```

---

# 24. Translation view

Provide:

```python
econ.translate(
    method="ols",
    formula="y ~ x1 + x2"
)
```

Example result:

| Engine | Generated syntax |
|---|---|
| Python | ... |
| R | ... |
| Stata | `regress y x1 x2` |
| EViews | `equation eq1.ls y c x1 x2` |
| MATLAB | `fitlm(...)` |

Generate this from the same adapters used for execution.

Do not build a separate translation system.

---

# 25. Teaching mode

Potential feature:

```python
econ.ols(
    data=data,
    formula="y ~ x1 + x2",
    engines=["r", "stata", "eviews"],
    teach=True
)
```

Could show:

- neutral specification
- generated code in each engine
- result comparison
- short syntax explanation

This makes EconEnv useful for teaching cross-software methodology.

---

# 26. Method registry

Avoid giant `if/elif` chains.

Use a method registry.

Conceptual:

```python
research_registry.register("ols", OLSMethod)
research_registry.register("adf", ADFMethod)
research_registry.register("var", VARMethod)
```

Each method should define:

- spec schema
- validation
- supported engine adapters
- normalization schema
- comparison logic

---

# 27. Suggested package structure

Conceptual only:

```text
econenv/
  research/
    api.py
    registry.py
    routing.py
    capabilities.py
    validation.py

    specs/
      base.py
      regression.py
      timeseries.py

    results/
      base.py
      regression.py
      multi.py

    adapters/
      python/
      r/
      stata/
      eviews/
      matlab/

    methods/
      ols.py
      adf.py
      var.py

    compare/
    help/
```

Adapt this to the actual repository.

---

# 28. Result parsing rules

Prefer structured outputs.

Priority:

```text
1. Native structured object/API
2. Engine workspace/stored results
3. Machine-readable result object
4. Text parsing only as last resort
```

Examples:

### Stata
Prefer stored results such as `e(b)`, `e(V)`, `e(N)`, `e(r2)`.

### R
Prefer `coef()`, `vcov()`, `residuals()`, fitted values, and native model object fields.

### Python
Preserve statsmodels/scikit-learn native result objects.

### EViews
Use COM/workfile objects and structured programmatic access when possible.

### MATLAB
Use Engine variables/model-object properties.

---

# 29. Unified export

Every result should connect to the academic output layer.

Examples:

```python
result.export("results.xlsx")
result.export("results.tex")
result.export("results.docx")
result.export("results.pdf")
result.export("results.html")
```

Figures:

```python
result.figure.export("figure1.pdf")
```

Publication tables should support:

- coefficient
- standard error
- p-value
- confidence interval
- significance
- model metadata
- captions/notes where appropriate

---

# 30. Reproducibility metadata

Every result should record where available:

- EconEnv version
- engine
- engine version
- Python version
- package/toolbox versions
- operating system
- timestamp
- generated code
- variables used
- sample size
- dropped observations
- model options
- random seed if relevant

Expose:

```python
result.metadata
```

---

# 31. Snapshot integration

Integrate with:

```text
%econ snapshot
```

Possible:

```python
result.snapshot()
```

or attach snapshot metadata automatically.

---

# 32. Error model

Recommended explicit errors:

```text
UnsupportedMethodError
UnsupportedOptionError
EngineUnavailableError
EngineCapabilityError
DataValidationError
SpecificationError
ExecutionError
NormalizationError
ComparisonError
```

Error messages must state:

- requested task
- requested engine
- unsupported option
- available alternatives
- suggested fix

---

# 33. No silent fallback

If:

```python
engine="stata"
```

fails, do not silently use R.

Only automatic routing may switch engines:

```python
engine="auto"
```

---

# 34. Engine preferences

Future config may support:

```text
preferred engines:
stata > r > python > eviews > matlab
```

or method-specific preferences:

```text
regression -> stata
visualization -> r
wavelet -> matlab
data preparation -> python
time series -> eviews
```

These must be user-configurable.

---

# 35. Help system

Add:

```text
%econ research
%econ research help
%econ research methods
%econ research engines
%econ research capabilities
%econ research examples
%econ research find <keyword>
```

Example:

```text
%econ research ols
```

Should show:

- description
- unified syntax
- supported engines
- common options
- examples
- engine-specific differences

---

# 36. Research catalog

Organize methods by:

```text
Descriptive statistics
Regression
Panel data
Time series
Causality
Volatility
Forecasting
Optimization
Wavelet/Frequency
Visualization
Machine learning
```

---

# 37. Research recipes — future

Potential YAML workflow:

```yaml
project: example-study

steps:
  - task: describe

  - task: ols
    formula: y ~ x1 + x2
    engine: stata

  - task: adf
    variable: y
    engine: eviews
```

Then:

```python
econ.run_recipe("study.yml")
```

Useful for reproducibility and teaching.

---

# 38. Natural-language layer — future

A later AI layer may accept:

```text
Run OLS of y on x1 and x2 in Stata.
```

or:

```text
Run the same model in R and Stata and compare coefficients.
```

The AI must produce a validated Research IR specification first.

Architecture:

```text
Natural language
   |
   v
Research IR
   |
   v
Validation
   |
   v
Engine Adapter
```

Do not let the AI bypass the specification layer.

---

# 39. Logging and debug mode

Provide execution trace:

```python
result.log
```

Example:

```text
1. Specification validated
2. Stata selected
3. Data transferred
4. Native command generated
5. Model executed
6. Results parsed
7. Unified result created
```

Debug mode should expose:

- IR
- routing decision
- native code
- transfer steps
- parser
- normalization

---

# 40. Golden cross-engine test

Use deterministic synthetic data.

Example:

```python
x = 1..20
y = 5 + 2*x + 0.3*sin(x)
```

Expected OLS approximately:

```text
const ≈ 5.052057
x ≈ 1.996468
R² ≈ 0.999655
```

Run the same spec across engines and compare within tolerance.

---

# 41. Testing requirements

Test:

- Research IR validation
- capability checks
- compile-only
- execution
- result normalization
- raw result preservation
- generated code
- multi-engine execution
- comparison
- unsupported options
- unavailable engines
- backward compatibility

Also rerun existing tests for:

```text
Python
R
Stata
EViews
MATLAB
push
pull
move
magics
doctor
status
snapshot
```

---

# 42. Phase plan

## Phase 1 — Foundation

Implement:

- Research IR
- registry
- capability system
- UnifiedResult
- OLS
- Python + R + Stata
- compile
- execute
- explain
- tests

## Phase 2 — Complete OLS engines

Add:

- EViews
- MATLAB
- MultiEngineResult
- comparison
- export

## Phase 3 — Common methods

Add:

```text
describe
corr
logit
ADF
KPSS
VAR
forecast
plot
```

## Phase 4 — Advanced methods

Add gradually:

```text
panel
IV
GMM
ARDL
cointegration
GARCH
quantile
DiD
SVAR
VECM
wavelet
```

## Phase 5 — Intelligent routing

Add:

- engine="auto"
- preference profiles
- explainable routing
- natural-language interface

---

# 43. MVP acceptance criteria

The first Unified Research Layer release is complete when:

1. One OLS specification runs in at least three engines.
2. Changing only `engine=` changes the backend.
3. Generated native code is inspectable.
4. Raw engine results remain available.
5. Unified coefficients/p-values are available.
6. Capability checks occur before execution.
7. Unsupported options raise clear errors.
8. Multi-engine comparison works.
9. Numerical consistency is tested on deterministic data.
10. Existing EconEnv APIs remain intact.

---

# 44. Backward compatibility

The following must continue working:

```text
%econ
%Rec / %%Rec
%R / %%R
%stata / %%stata
%eviews / %%eviews
%matlab / %%matlab
push
pull
move
doctor
status
snapshot
config
```

The Unified Research Layer is additive.

---

# 45. Non-negotiable rules

- No silent engine substitution.
- No silent estimator substitution.
- No fabricated statistics.
- No hiding generated native code.
- No deleting raw/native output.
- No breaking native magics.
- No breaking push/pull/move.
- No unnecessary CSV/Excel intermediate files.
- No hardcoded local paths.
- No direct language-to-language architecture.
- No giant engine-specific conditional logic in the core.

Use:

```text
Unified API
   ↓
Research IR
   ↓
Engine Adapter
   ↓
Native Execution
   ↓
Unified Result
```

---

# 46. Full implementation prompt for Flowd

Use the current EconEnv repository and implement a new **Unified Research Layer** above the existing engine system.

Do not rewrite the existing execution engines.

Before coding:

1. Inspect repository architecture.
2. Identify current:
   - engine registry
   - capabilities
   - push/pull/move
   - configuration
   - diagnostics
   - magics
   - result structures
   - export layer
3. Reuse existing abstractions.
4. Preserve backward compatibility.

Build:

1. Research Intermediate Representation.
2. Method/spec registry.
3. Capability registry.
4. Engine adapter interface.
5. OLS specification.
6. Python OLS adapter.
7. R OLS adapter.
8. Stata OLS adapter.
9. EViews OLS adapter.
10. MATLAB OLS adapter.
11. UnifiedResult.
12. MultiEngineResult.
13. Native-code compilation.
14. Explain mode.
15. Dry-run mode.
16. Cross-engine comparison.
17. Academic export integration.
18. Help/catalog integration.
19. Tests.
20. Documentation.

The key public behavior must be:

```python
result = econ.ols(
    data=data,
    formula="y ~ x1 + x2",
    engine="stata"
)
```

Changing only:

```python
engine="r"
```

must execute the same research specification through R.

Changing only:

```python
engine="eviews"
```

must execute through EViews.

Changing only:

```python
engine="matlab"
```

must execute through MATLAB.

Changing only:

```python
engine="python"
```

must execute through Python.

The generated native code must be retained and inspectable.

The raw engine result must be retained.

Do not add `engine="auto"` until capability-based routing is reliable and explainable.

---

# 47. Deliverables expected from Flowd

Please work in this order:

1. Architecture review.
2. Proposed public API.
3. Proposed Research IR.
4. Proposed module/package structure.
5. Capability model.
6. OLS spec.
7. Engine adapters.
8. UnifiedResult.
9. MultiEngineResult.
10. compile/dry-run/explain.
11. comparison.
12. deterministic cross-engine tests.
13. documentation.
14. help/catalog.
15. backward-compatibility report.
16. changelog.

Do not expand to many methods until OLS is stable.

---

# 48. Final target

The deeper positioning of EconEnv should become:

> **A research abstraction layer where the researcher defines the analytical task once, selects the execution engine, inspects the generated native code, compares implementations, and receives unified reproducible results.**

The engine becomes the backend.

The research specification becomes the primary object.

Possible future tagline:

> **One Research Language. Multiple Engines. Unified Results.**

Alternative:

> **Define the model once. Choose the engine later.**
