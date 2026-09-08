# EconLang / EconEnv Unified Econometrics Language
## المسودة الشاملة لبناء لغة عالية المستوى لتوحيد العمل بين EViews وStata وR وPython وMATLAB وGAUSS

> **الفكرة المركزية:** بناء طبقة موحدة تجعل الباحث يكتب **ما يريد إنجازه اقتصاديًا وقياسيًا** بدل أن يكتب Syntax خاصًا بكل برنامج، ثم تتولى المنصة التحليل الدلالي، التحقق القياسي، اختيار أو استخدام الـBackend، الترجمة، التنفيذ، توحيد النتائج، التخزين، الرسوم، الأخطاء، والتصدير.

---

# 1. الرؤية

يوجد في الاقتصاد القياسي عدد كبير من البيئات القوية، وأشهرها:

- EViews
- Stata
- R
- Python
- MATLAB
- GAUSS

المشكلة ليست في ضعف هذه البرامج، بل في تشتت الباحث بين لغات وواجهات وفلسفات مختلفة. لكل برنامج طريقة خاصة في:

- تحميل البيانات.
- تعريف Time Series وPanel Data.
- التحويلات.
- الإحصاء الوصفي.
- الاختبارات السابقة للتقدير.
- Estimation.
- Post-estimation.
- استخراج النتائج.
- الرسوم.
- حفظ النماذج والنتائج.
- إدارة الأخطاء.
- التصدير.

الهدف من المشروع هو إنشاء **Unified High-Level Econometrics Language**، وليكن اسمها المؤقت:

- EconLang
- EconScript
- EconDSL
- EconEnv Language
- Universal Econometrics Language

الشعار المقترح:

> **Write Econometrics, Not Software Syntax.**

أو:

> **Model Once. Run Anywhere.**

---

# 2. المبدأ المعماري الأساسي

لا نبني مترجمًا مباشرًا مثل:

```text
EconLang → Stata
```

بل:

```text
Researcher
   ↓
EconLang Source
   ↓
Lexer / Parser
   ↓
AST
   ↓
Semantic + Econometric Validation
   ↓
Econometric Intermediate Representation (IR)
   ↓
Capability Resolver
   ↓
Execution Planner
   ↓
Backend Adapter / Compiler
   ├── Python
   ├── R
   ├── Stata
   ├── EViews
   ├── MATLAB
   └── GAUSS
   ↓
Execution
   ↓
Raw Backend Output
   ↓
Unified Result Parser
   ↓
Unified Result Objects
   ↓
Tables / Graphs / Reports / Export / Reproducibility
```

هذه النقطة هي التي تجعل المشروع منصة حقيقية وليس مجرد Command Translator.

---

# 3. فلسفة اللغة

## 3.1 الباحث يكتب اقتصادًا قياسيًا لا تعليمات برنامج

مثال:

```econ
model ols wage_model:
    y = wage
    x = education, age, experience
```

بدل أن يتعلم الباحث ست صيغ مختلفة.

## 3.2 اللغة High-Level

يجب أن تكون:

- واضحة.
- قصيرة.
- قابلة للقراءة بعد أشهر.
- لا تحتاج خبرة برمجية عالية.
- مستقلة قدر الإمكان عن البرامج.
- قابلة للتوسع.
- قابلة للفحص قبل التنفيذ.
- قابلة لإعادة الإنتاج.

## 3.3 لا اعتماد على LLM داخل Core

الـLLM يمكن أن يكون طبقة اختيارية لاحقًا:

```text
Natural Language
→ Proposed EconLang
→ Parser
→ Validator
→ Execution
```

لكن EconLang نفسها يجب أن تكون حتمية Deterministic وقابلة للاختبار.

---

# 4. مستويات الكتابة

## Beginner Mode

```econ
estimate linear regression

dependent = income
independent = education, age, experience
```

## Standard Mode

```econ
model ols m1:
    y = income
    x = education, age, experience
```

## Expert Mode

```econ
model ols m1:
    y = income
    x = education, age, experience
    intercept = yes
    vcov = HC3
    missing = listwise
    weights = sampling_weight
```

كلها تتحول إلى نفس الـIR.

---

# 5. قواعد Syntax

- الكلمات الأساسية بالإنجليزية في الإصدار الأول.
- Blocks تبدأ بـ `:`.
- Indentation ذات معنى.
- التعليقات تبدأ بـ `#`.
- Strings داخل quotes.
- Lists مفصولة بفواصل.
- أسماء النماذج اختيارية لكن مستحسنة.
- Autocomplete وSyntax Highlighting يجب أن يكونا ممكنين مستقبلًا.

مثال:

```econ
# Load the data
data "macro.xlsx"

# Define time structure
set time:
    variable = year
    frequency = annual

model ols baseline:
    y = gdp
    x = inflation, exchange_rate, unemployment
```

---

# 6. المشروع Project

```econ
project "inflation-study"
```

إعدادات عامة:

```econ
backend = auto
seed = 2026
theme = publication
language = en
strict = standard
verbosity = normal
```

اقتراح ملف:

```text
econproject.toml
```

مثال:

```toml
[project]
name = "inflation-study"

[defaults]
backend = "auto"
theme = "publication"
seed = 2026
strict = "standard"

[paths]
data = "data"
results = "results"
graphs = "graphs"
exports = "exports"
logs = "logs"
```

---

# 7. هيكل المشروع على القرص

```text
project/
├── econproject.toml
├── analysis.econ
├── data/
│   ├── raw/
│   ├── processed/
│   └── cache/
├── models/
├── results/
├── graphs/
├── tables/
├── reports/
├── exports/
├── logs/
├── cache/
├── temp/
└── project.json
```

---

# 8. تحميل البيانات

```econ
data "macro.xlsx"
```

أو:

```econ
data load "macro.xlsx":
    sheet = "Sheet1"
    header = yes
    missing = ".", "NA", "-"
```

دعم مستقبلي:

- CSV
- XLS/XLSX
- Parquet
- Arrow
- Stata DTA
- SPSS SAV
- SAS
- RDS/RData
- MAT
- EViews exports/workfiles حسب الإمكان
- SQL
- API
- URL

---

# 9. Data Object الموحد

```text
Dataset
├── id
├── name
├── source
├── source_type
├── schema
├── rows
├── columns
├── variable_types
├── variable_labels
├── value_labels
├── units
├── missing_rules
├── time_structure
├── panel_structure
├── transformations
├── provenance
├── active_sample
├── dataset_hash
└── metadata
```

يفضل استعمال Apache Arrow/Parquet كصيغة داخلية Canonical كلما كان ذلك عمليًا.

---

# 10. استكشاف البيانات

```econ
describe
schema
summary
head 10
tail 10
missing report
duplicates report
```

لمتغيرات محددة:

```econ
describe gdp inflation unemployment
```

---

# 11. أنواع المتغيرات

دعم:

- integer
- float
- numeric
- string
- categorical
- boolean
- date
- datetime
- annual
- quarterly
- monthly
- weekly
- daily
- panel identifier
- geographic identifier

مثال:

```econ
type country = category
type year = annual
type gdp = numeric
```

---

# 12. تعريف Time Series

```econ
set time:
    variable = year
    frequency = annual
```

اختصار:

```econ
time = year
```

Quarterly:

```econ
set time:
    variable = quarter
    frequency = quarterly
```

يجب اكتشاف:

- duplicate time values.
- gaps.
- unsorted observations.
- invalid date format.
- inconsistent frequency.

---

# 13. تعريف Panel Data

```econ
set panel:
    id = country
    time = year
```

يجب اكتشاف:

- Balanced / Unbalanced.
- عدد الوحدات N.
- عدد الفترات T.
- duplicates لـ `(id,time)`.
- gaps.
- singleton groups.

---

# 14. تنظيف البيانات

```econ
clean:
    trim_strings
    standardize_missing
    remove_duplicates
```

## Missing

```econ
missing report
```

```econ
missing drop:
    variables = income, age
```

```econ
missing impute:
    variables = income
    method = median
```

طرق محتملة:

- mean
- median
- mode
- interpolation
- forward fill
- backward fill
- KNN
- MICE
- model-based imputation

## Outliers

```econ
outliers detect:
    variables = income
    method = iqr
```

```econ
outliers winsorize:
    variables = income
    lower = 1%
    upper = 99%
```

## Duplicates

```econ
duplicates check
duplicates drop
```

---

# 15. التحويلات

```econ
transform:
    lgdp = log(gdp)
    gdp2 = gdp ^ 2
    growth = diff(log(gdp)) * 100
    lag_inf = lag(inflation, 1)
    policy_crisis = policy * crisis
```

دعم:

- log
- exp
- sqrt
- powers
- lag
- lead
- first difference
- seasonal difference
- growth rates
- percentage changes
- interactions
- polynomials
- dummies
- seasonal dummies
- trends
- z-score
- min-max scaling
- winsorization
- filters: HP / BK / CF لاحقًا

كل Transformation يسجل في Data Provenance.

---

# 16. Provenance

مثال داخلي:

```text
001 load macro.xlsx
002 define year as annual time index
003 log(gdp) -> lgdp
004 diff(lgdp) -> dlgdp
005 drop 2 rows with missing inflation
006 sample 1990:2025
```

أمر:

```econ
provenance show
```

---

# 17. Sample Management

```econ
sample:
    year >= 2000
```

```econ
sample:
    country in ["Algeria", "Morocco", "Tunisia"]
```

```econ
sample reset
```

كل Result يجب أن يحفظ العينة التي استعملت.

---

# 18. Snapshots

```econ
snapshot save raw_data
snapshot save cleaned_data
snapshot restore cleaned_data
```

يمكن إضافة:

```econ
undo
```

لكن Snapshot أكثر أمانًا وقابلية للتتبع.

---

# 19. الإحصاء الوصفي

```econ
summary gdp inflation unemployment
```

أو:

```econ
summary:
    variables = gdp, inflation
    statistics = n, mean, median, sd, min, max, skewness, kurtosis
```

By-group:

```econ
summary wage by gender
```

---

# 20. Correlation / Covariance

```econ
correlation gdp inflation unemployment
```

```econ
correlation:
    variables = gdp, inflation, unemployment
    method = spearman
```

دعم:

- Pearson
- Spearman
- Kendall
- partial correlation

---

# 21. Pre-Estimation Framework

بدل أن تكون الاختبارات أوامر مشتتة، يوجد Block موحد:

```econ
precheck:
    missing
    outliers
    multicollinearity
    stationarity
    structural_breaks
```

ينتج Model/Data Readiness Report:

```text
✓ Required variables exist
✓ No duplicated time index
✓ Sufficient observations
⚠ GDP appears highly persistent
⚠ INF has 3 missing observations
⚠ Correlation between EXR and CPI = 0.94
```

---

# 22. Unit Root Tests

```econ
unitroot gdp:
    test = adf
    deterministic = trend
    lags = auto
    criterion = AIC
```

دعم على مراحل:

- ADF
- PP
- KPSS
- DF-GLS
- ERS
- Ng-Perron
- Zivot-Andrews
- Lee-Strazicich
- Fourier tests
- Panel unit-root tests

يجب أن تكون النتائج Structured لا نصًا فقط.

---

# 23. Cointegration

```econ
cointegration:
    variables = gdp, consumption, investment
    method = johansen
```

دعم مستقبلي:

- Engle-Granger
- Johansen
- Phillips-Ouliaris
- ARDL Bounds
- Gregory-Hansen
- Hatemi-J
- Maki
- Panel cointegration

---

# 24. Lag Selection

```econ
lagselect:
    variables = gdp, inflation, interest_rate
    max_lag = 8
    criteria = AIC, BIC, HQ
```

يجب إعادة object منظم يحتوي الاختيارات والقيم.

---

# 25. OLS

```econ
model ols m1:
    y = income
    x = education, age, experience
```

خيارات:

```econ
model ols m1:
    y = income
    x = education, age, experience
    intercept = yes
    weights = sample_weight
    vcov = HC3
    missing = listwise
```

---

# 26. WLS / GLS / Robust

```econ
model wls m1:
    y = y
    x = x1, x2
    weights = w
```

```econ
model gls m1:
    y = y
    x = x1, x2
```

```econ
model robust m1:
    y = y
    x = x1, x2
    method = huber
```

---

# 27. Instrumental Variables

```econ
model iv iv1:
    y = wage
    endogenous = education
    instruments = distance_college
    controls = age, experience
```

دعم:

- 2SLS
- LIML
- Fuller
- GMM
- first-stage diagnostics
- weak IV
- overidentification
- endogeneity tests

---

# 28. GMM

```econ
model gmm gmm1:
    y = y
    x = x1, x2
    instruments = z1, z2
    weighting = two_step
```

تجب مراعاة اختلاف implementation بين backends.

---

# 29. Limited Dependent Variable Models

```econ
model logit m1:
    y = employed
    x = education, age
```

دعم تدريجي:

- logit
- probit
- cloglog
- ordered logit/probit
- multinomial logit
- Tobit
- Heckman
- Poisson
- Negative Binomial
- zero-inflated models

---

# 30. Quantile Regression

```econ
model quantile q50:
    y = wage
    x = education, experience
    quantile = 0.50
```

متعدد:

```econ
model quantile wage_q:
    y = wage
    x = education, experience
    quantiles = 0.10, 0.25, 0.50, 0.75, 0.90
```

---

# 31. Time-Series Models

## ARIMA

```econ
model arima a1:
    y = inflation
    order = 1,1,1
```

Auto:

```econ
model arima a1:
    y = inflation
    order = auto
    criterion = AIC
```

## ARDL

```econ
model ardl ardl1:
    y = gdp
    x = inflation, exchange_rate
    max_lag = 4
    select = AIC
```

## ECM

```econ
derive ecm ecm1 from ardl1
```

## VAR

```econ
model var var1:
    variables = gdp, inflation, interest_rate
    lags = auto
    max_lag = 8
    criterion = AIC
```

## SVAR

```econ
model svar svar1:
    from = var1
    identification = short_run
```

## VECM

```econ
model vecm vecm1:
    variables = gdp, consumption, investment
    rank = auto
```

---

# 32. Volatility Models

```econ
model garch vol1:
    y = returns
    mean = ARMA(1,1)
    variance = GARCH(1,1)
    distribution = student_t
```

دعم مستقبلي:

- ARCH
- GARCH
- EGARCH
- GJR-GARCH
- APARCH
- FIGARCH
- DCC-GARCH
- BEKK
- Stochastic Volatility

---

# 33. Panel Data

## Fixed Effects

```econ
model fe fe1:
    y = growth
    x = investment, trade
    effects = entity
```

Two-Way:

```econ
model fe fe2:
    y = growth
    x = investment, trade
    effects = entity, time
```

Clustered SE:

```econ
model fe fe3:
    y = growth
    x = investment, trade
    cluster = country
```

## Random Effects

```econ
model re re1:
    y = growth
    x = investment, trade
```

## Hausman

```econ
compare fe1 re1:
    test = hausman
```

---

# 34. Dynamic Panel

```econ
model system_gmm gmm1:
    y = growth
    lag_y = 1
    x = investment, trade
    endogenous = investment
    instruments = lag(2:4)
```

دعم مستقبلي:

- Difference GMM
- System GMM
- bias-corrected LSDV
- PMG
- MG
- DFE
- CCE
- CS-ARDL
- panel quantile
- threshold panel

يجب إضافة warnings لـ:

- instrument proliferation.
- weak instruments.
- too few groups.
- invalid lag ranges.

---

# 35. Causal Inference

## DID

```econ
model did did1:
    outcome = employment
    unit = firm
    time = year
    treatment = treated
```

دعم:

- 2x2 DID
- staggered adoption
- event studies
- Callaway-Sant'Anna
- Sun-Abraham
- imputation estimators

## RDD

```econ
model rd rd1:
    y = outcome
    running = score
    cutoff = 50
```

## Matching

```econ
model matching mt1:
    treatment = treated
    outcome = wage
    covariates = age, education, experience
    method = propensity_score
```

## Synthetic Control

```econ
model synth s1:
    outcome = gdp
    treated_unit = Algeria
    treatment_year = 2015
```

## DML

```econ
model dml dml1:
    y = outcome
    treatment = policy
    controls = x1, x2, x3
    learner = random_forest
    folds = 5
```

---

# 36. ML Layer

يمكن دعم ML دون تحويل المشروع إلى مكتبة ML عامة.

```econ
model random_forest rf1:
    y = default
    x = income, debt, age
    task = classification
```

```econ
validate rf1:
    method = cross_validation
    folds = 10
```

دعم محتمل:

- ridge
- lasso
- elastic net
- random forest
- gradient boosting
- XGBoost
- LightGBM
- CatBoost
- SVM
- neural networks

---

# 37. Post-Estimation Framework

```econ
diagnostics m1:
    heteroskedasticity
    autocorrelation
    normality
    multicollinearity
    specification
    stability
```

---

# 38. Heteroskedasticity

```econ
test m1:
    heteroskedasticity = breusch_pagan
```

دعم:

- Breusch-Pagan
- White
- Goldfeld-Quandt
- ARCH LM

---

# 39. Serial Correlation

```econ
test m1:
    autocorrelation = breusch_godfrey
    lags = 4
```

دعم:

- Durbin-Watson
- Breusch-Godfrey
- Ljung-Box
- Wooldridge panel serial correlation

---

# 40. Normality

```econ
test m1:
    normality = jarque_bera
```

---

# 41. Multicollinearity

```econ
test m1:
    vif
```

---

# 42. Specification

دعم:

- Ramsey RESET
- omitted-variable diagnostics
- functional-form tests

---

# 43. Stability / Structural Breaks

```econ
stability m1:
    cusum
    cusumsq
```

دعم:

- CUSUM
- CUSUMSQ
- recursive residuals
- Chow
- Quandt-Andrews
- Bai-Perron

---

# 44. Granger Causality

```econ
granger:
    cause = money
    effect = inflation
    lags = 4
```

لاحقًا:

- Toda-Yamamoto
- panel Granger
- nonlinear Granger
- frequency-domain causality

---

# 45. Marginal Effects

```econ
margins m1
```

```econ
margins m1:
    at = age(20,30,40,50)
```

---

# 46. Predictions / Residuals

```econ
predict m1:
    save = yhat
```

```econ
residuals m1:
    save = ehat
```

---

# 47. Forecasting

```econ
forecast m1:
    horizon = 12
    interval = 95
    save = forecast_series
```

---

# 48. IRF / FEVD

```econ
irf var1:
    impulse = interest_rate
    response = inflation
    horizon = 20
```

```econ
fevd var1:
    horizon = 20
```

---

# 49. Hypothesis Testing

```econ
test m1:
    hypothesis = beta(inflation) = 0
```

```econ
test m1:
    hypothesis = beta(x1) + beta(x2) = 1
```

---

# 50. Bootstrap

```econ
bootstrap m1:
    reps = 1000
    seed = 12345
```

---

# 51. Robust Covariance

```econ
model ols m1:
    y = y
    x = x1, x2
    vcov = HC3
```

```econ
model ols m2:
    y = y
    x = x1, x2
    vcov = newey_west
    lag = 4
```

```econ
model fe m3:
    y = y
    x = x1, x2
    cluster = country
```

---

# 52. Unified ModelResult

```text
ModelResult
├── id
├── name
├── model_type
├── estimator_family
├── backend
├── backend_version
├── generated_backend_code
├── dataset_id
├── dataset_hash
├── sample
├── nobs
├── coefficients
├── standard_errors
├── test_statistics
├── p_values
├── confidence_intervals
├── covariance_info
├── fit_statistics
├── residuals
├── fitted_values
├── predictions
├── diagnostics
├── convergence
├── warnings
├── execution_time
├── timestamp
└── reproducibility_metadata
```

واجهة:

```econ
show m1.coefficients
show m1.pvalues
show m1.aic
show m1.bic
show m1.residuals
```

---

# 53. TestResult

```text
TestResult
├── id
├── test_type
├── source_model
├── statistic
├── p_value
├── critical_values
├── df
├── null_hypothesis
├── decision
├── backend
└── metadata
```

---

# 54. Result Registry

```econ
models
```

يعرض مثلًا:

```text
m1  OLS   Python  completed
m2  FE    Stata   completed
m3  ARDL  EViews  completed_with_warning
```

Statuses:

- pending
- running
- completed
- completed_with_warning
- failed
- cancelled
- cached

---

# 55. Result Storage

اقتراح:

- SQLite للـmetadata/registry.
- Parquet/Arrow للبيانات والنتائج الجدولية الكبيرة.
- JSON للـsmall structured artifacts.
- ملفات منفصلة للرسوم.
- logs منفصلة.

تجنب الاعتماد على Pickle كصيغة أساسية طويلة المدى.

---

# 56. Model Lineage

```econ
derive ecm ecm1 from ardl1
```

النظام يحفظ:

```text
ardl1 → ecm1
```

ونفس الشيء للـforecast والdiagnostics والتables.

---

# 57. Model Comparison

```econ
compare m1 m2 m3:
    metrics = aic, bic, r2
```

```econ
select best:
    from = m1, m2, m3
    criterion = BIC
```

---

# 58. Backend Selection

```econ
backend = stata
```

أو داخل نموذج:

```econ
model ols m1:
    backend = eviews
    y = gdp
    x = inflation, exr
```

---

# 59. Auto Backend

```econ
backend = auto
```

الـplanner ينظر إلى:

- هل البرنامج مثبت.
- هل النسخة مدعومة.
- هل النموذج مدعوم.
- هل package/toolbox المطلوب موجود.
- تفضيلات المستخدم.
- نظام التشغيل.
- الأداء.
- reproducibility.

لا يجوز تغيير معنى estimator بصمت.

---

# 60. Capability Matrix

مثال داخلي:

```yaml
models:
  ols:
    python: full
    r: full
    stata: full
    eviews: full
    matlab: full
    gauss: full

  system_gmm:
    python: partial
    r: full
    stata: full
    eviews: partial
    matlab: custom
    gauss: custom
```

والـoption-level capabilities مهمة أيضًا.

---

# 61. Fallback

مثال رسالة:

```text
E731 — Backend capability limitation

Requested estimator:
    System GMM

Selected backend:
    EViews

Support level:
    Partial

Recommended backends:
    Stata
    R

Suggested action:
    backend = stata
```

---

# 62. مقارنة Backends

```econ
compare backends:
    model = m1
    backends = python, r, stata, eviews
```

المقارنة توحد:

- coefficients
- SE
- p-values
- CI
- N
- fit statistics
- sample

مع Tolerance موثق.

---

# 63. Backend Contract

```python
class Backend:
    def detect(self): ...
    def version(self): ...
    def capabilities(self): ...
    def validate(self, ir): ...
    def compile(self, ir): ...
    def execute(self, plan): ...
    def parse_result(self, raw): ...
    def cleanup(self): ...
```

---

# 64. Python Backend

Packages محتملة:

- pandas
- polars
- numpy
- scipy
- statsmodels
- linearmodels
- arch
- pmdarima
- scikit-learn
- doubleml

لا يتم ربط Core بهذه الحزم مباشرة؛ فقط adapter.

---

# 65. R Backend

Integrations محتملة:

- subprocess + Rscript
- rpy2 اختياري وليس requirement وحيد
- temporary structured exchange

Packages محتملة:

- stats
- lmtest
- sandwich
- plm
- fixest
- vars
- urca
- forecast
- dynlm
- ARDL
- pgmm-related tools
- did

---

# 66. Stata Backend

يجب دعم أكثر من طريقة حسب البيئة:

- Stata executable + generated do-file.
- PyStata عند توفره.
- temp DTA/CSV/Parquet conversion.
- machine-readable result extraction كلما أمكن.
- log parsing كحل أخير وليس الأول.

يجب اكتشاف:

- Stata/BE
- Stata/SE
- Stata/MP
- version
- path

---

# 67. EViews Backend

على Windows:

- COM automation عندما يكون مدعومًا.
- generated EViews program files.
- workfile/data exchange.
- CSV/Excel intermediary data.
- saved results extraction.

يجب عزل التفاصيل كليًا داخل adapter.

---

# 68. MATLAB Backend

- MATLAB Engine API for Python عند توفره.
- batch execution كبديل.
- `.mat` exchange.
- اكتشاف Econometrics Toolbox.
- اكتشاف version.

---

# 69. GAUSS Backend

- CLI / batch execution.
- generated GAUSS source.
- data exchange.
- structured parsing أو standardized output bridge.

---

# 70. `econ doctor`

```bash
econ doctor
```

يفحص:

- Python executable/version.
- R executable/version.
- Stata path/version/edition.
- EViews path/version.
- MATLAB path/version/toolboxes.
- GAUSS path/version.
- required packages.
- permissions.
- temp folder.
- backend connectivity.

---

# 71. CLI

```bash
econ run analysis.econ
econ validate analysis.econ
econ doctor
econ backends
econ models
econ help ardl
```

---

# 72. Jupyter Integration

```text
%%econ
model ols m1:
    y = gdp
    x = inflation, exr
```

وأيضًا:

```text
%econ backend stata
```

Outputs يجب أن تكون Rich قدر الإمكان:

- tables.
- warnings.
- graph.
- generated code tab.
- backend metadata.

---

# 73. GUI/IDE مستقبلًا

Panels:

- Editor.
- Data Viewer.
- Variable Explorer.
- Model Explorer.
- Results.
- Tables.
- Graphs.
- Diagnostics.
- Backend Selector.
- Console.
- Project Browser.

---

# 74. Autocomplete

عند:

```econ
model 
```

يقترح estimators.

داخل:

```econ
model ardl:
```

يقترح فقط خيارات ARDL.

عند:

```econ
y =
```

يقترح numeric variables من dataset الحالي.

---

# 75. Parser

خيارات:

- Lark
- ANTLR
- Tree-sitter
- pyparsing

للـMVP: Parser بسيط وموثوق أهم من التعقيد.

Tree-sitter ممتاز لاحقًا للـincremental parsing والـIDE tooling.

---

# 76. AST مثال

```text
ModelNode(
    model_type="ols",
    name="m1",
    dependent="gdp",
    regressors=["inflation", "exr"],
    options={"vcov": "HC3"}
)
```

---

# 77. Econometric IR مثال

```json
{
  "operation": "estimate",
  "estimator_family": "linear_regression",
  "estimator": "ols",
  "dependent": ["gdp"],
  "exogenous": ["inflation", "exr"],
  "covariance": {
    "type": "HC3"
  }
}
```

الـIR يجب أن يمثل **المعنى الإحصائي** وليس syntax برنامج.

---

# 78. Semantic Validation

يتحقق من:

- المتغير موجود.
- النوع مناسب.
- model name غير مكرر.
- الخيارات صالحة.
- time/panel structure موجودة عند الحاجة.
- instrument ليس مفقودًا.
- quantile بين 0 و1.
- lags منطقية.
- no duplicate arguments.

---

# 79. Econometric Validation

طبقة مستقلة عن Syntax.

أمثلة:

- FE بدون Panel structure.
- ARDL بدون time ordering.
- System GMM مع عدد مجموعات صغير جدًا.
- DID بدون treatment/timing.
- VAR بمتغير واحد.
- weak instrument warning.
- too many instruments warning.
- perfect collinearity.
- singular design matrix.

---

# 80. Error Taxonomy

- `E1xx`: Data
- `E2xx`: Syntax
- `E3xx`: Semantic
- `E4xx`: Econometric
- `E5xx`: Backend
- `E6xx`: Execution
- `E7xx`: Capability
- `E8xx`: Export
- `E9xx`: Internal

أمثلة:

```text
E101 Variable not found
E102 Dataset not loaded
E103 Duplicate time index
E104 Invalid data type
E105 Missing values
E201 Invalid syntax
E202 Unexpected keyword
E203 Missing block
E301 Undefined model
E302 Invalid model option
E401 Insufficient observations
E402 Perfect multicollinearity
E403 Singular matrix
E404 Nonstationarity warning/error depending on strictness
E405 Panel structure missing
E406 Invalid instruments
E501 Backend unavailable
E502 Unsupported backend version
E503 Required package unavailable
E601 Execution timeout
E602 Backend process crashed
E701 Estimator unsupported by backend
E801 Export format unavailable
```

---

# 81. تصميم رسالة الخطأ

مثال:

```text
E101 — Variable not found

Variable:
    GDP

GDP is not available in the active dataset.

Did you mean:
    gdp
    GDP_real
    logGDP

Available variables:
    year
    gdp
    inflation
    exchange_rate

Suggested fix:
    Replace GDP with gdp
```

كل Error يفضل أن يحتوي:

1. code.
2. title.
3. what happened.
4. location.
5. probable cause.
6. suggested fix.
7. valid example.
8. Did you mean.
9. docs reference.
10. raw backend error فقط في verbose/debug.

---

# 82. Econometric-Friendly Error

```text
E405 — Panel structure is missing

You requested a Fixed Effects model.

Required:
    entity variable
    time variable

Missing:
    panel declaration

Use:

set panel:
    id = country
    time = year
```

---

# 83. Warnings

Warnings لا تمنع التنفيذ عادة.

أمثلة:

- possible spurious regression.
- small sample.
- few clusters.
- weak instruments.
- too many instruments.
- non-convergence.
- near multicollinearity.
- unbalanced panel.
- heteroskedasticity.
- residual autocorrelation.
- extrapolation.

مثال:

```text
W401 — Possible spurious regression

GDP and CPI appear highly persistent.

Consider:
    unitroot GDP CPI
    cointegration GDP CPI
```

---

# 84. Strictness

```econ
strict = low
strict = standard
strict = high
```

- Low: تحذيرات أكثر، منع أقل.
- Standard: الإعداد الافتراضي.
- High: يمنع حالات خطرة أو غير معرفة بوضوح.

---

# 85. Explain Error

```econ
explain error E405
```

يعرض شرحًا تعليميًا.

---

# 86. Dry Run

```econ
dryrun m1
```

يعرض:

- parsed interpretation.
- semantic checks.
- econometric checks.
- backend selection.
- packages required.
- generated backend code.
- expected artifacts.

دون تنفيذ.

---

# 87. Show Generated Code

```econ
show code m1
```

مثال:

```text
Backend: Stata
Generated code:
reg gdp inflation exchange_rate, vce(robust)
```

---

# 88. Explain Model

```econ
explain m1
```

يمكن أن يعرض:

- estimator.
- dependent variable.
- regressors.
- sample.
- covariance estimator.
- assumptions.
- diagnostics recommended.

---

# 89. Graph Specification

```econ
plot line:
    x = year
    y = gdp
```

```econ
plot scatter:
    x = inflation
    y = growth
```

```econ
plot histogram:
    x = income
```

---

# 90. أنواع الرسوم

- line
- scatter
- histogram
- density
- boxplot
- violin
- bar
- area
- correlogram
- ACF
- PACF
- residual plot
- QQ plot
- coefficient plot
- event-study plot
- IRF
- FEVD
- forecast
- actual vs fitted
- ROC
- confusion matrix
- SHAP plots
- panel trajectories
- heatmaps

---

# 91. Theme System

```econ
theme = research
```

Themes:

- research
- publication
- presentation
- light
- dark
- monochrome
- colorblind_safe

مثال:

```econ
plot line:
    x = year
    y = gdp
    theme = publication
    title = "GDP Evolution"
    xlabel = "Year"
    ylabel = "GDP"
    caption = "Source: World Bank"
```

---

# 92. قواعد الألوان والرسوم

- لوحة ألوان ثابتة لكل Theme.
- Colorblind-safe كخيار أساسي.
- عدم الاعتماد على اللون وحده عند تعدد السلاسل.
- fonts موحدة.
- title/subtitle/caption.
- legend rules موحدة.
- high-DPI raster.
- SVG/PDF للنشر.
- PNG للعروض والويب.
- دعم transparent background اختياري.
- support for LaTeX-style labels لاحقًا.

---

# 93. GraphResult

```text
GraphResult
├── id
├── graph_type
├── source_data
├── source_model
├── specification
├── theme
├── dimensions
├── output_paths
├── backend_used_for_rendering
└── metadata
```

---

# 94. Tables

```econ
table m1
```

```econ
table m1 m2 m3:
    show = coefficients, se, stars
    stats = n, r2, aic, bic
```

دعم:

- descriptive tables.
- regression tables.
- model comparison.
- diagnostics.
- custom labels.
- significance stars configurable.

---

# 95. Export

```econ
export m1 to "results.xlsx"
export table reg_table to "table.tex"
export graph g1 to "figure.svg"
```

Formats:

- CSV
- XLSX
- JSON
- Parquet
- HTML
- Markdown
- LaTeX
- PNG
- SVG
- PDF

لاحقًا:

- Word
- PowerPoint
- Quarto report

---

# 96. Reporting

```econ
report create:
    title = "Macroeconomic Analysis"
    include = summary, m1, diagnostics, graphs
    format = html
```

لاحقًا:

- Quarto.
- Jupyter Book.
- Word.
- LaTeX/PDF.

---

# 97. Reproducibility

كل Result يحفظ:

- EconLang source.
- normalized IR.
- generated backend code.
- backend name/version.
- packages/toolboxes versions.
- dataset hash.
- active sample.
- seed.
- system info.
- timestamp.
- execution time.

أوامر:

```econ
audit m1
reproducibility report m1
```

---

# 98. Caching

Cache key يعتمد على:

- normalized IR.
- dataset hash.
- backend.
- backend version.
- package versions.
- seed.

إذا تغير شيء جوهري لا تستخدم نتيجة قديمة.

---

# 99. Seeds

```econ
seed = 12345
```

يترجم للـbackend المختار.

---

# 100. Logging

يجب تسجيل:

- user source.
- normalized source.
- generated backend code.
- stdout.
- stderr.
- warnings.
- execution timing.
- parse status.
- result serialization.

Verbosity:

```econ
verbosity = quiet
verbosity = normal
verbosity = verbose
verbosity = debug
```

---

# 101. Security

لا يسمح بتنفيذ shell عشوائي في الـcore DSL.

يجب حماية:

- paths.
- subprocess args.
- command injection.
- temporary directories.
- SQL parameters.
- secrets.
- credentials.
- logs.
- resource consumption.
- timeout.

---

# 102. Raw Backend Mode

للمستخدم المتقدم فقط:

```econ
raw stata:
    regress y x1 x2
```

أو:

```econ
raw r:
    fit <- lm(y ~ x1 + x2, data=df)
```

يجب إظهار أن هذا:

- غير portable.
- لا يستفيد من كل التحقق الدلالي.
- قد لا يعاد إنتاجه على backend آخر.

---

# 103. Package Management

```econ
packages check
```

يمكن دعم installation اختياريًا، لكن لا تثبيت packages بصمت.

---

# 104. Version Awareness

النظام يجب أن يعرف:

- backend version.
- package version.
- feature introduced/removed.
- incompatible syntax.

Capability Matrix يجب أن تكون version-aware.

---

# 105. Licensing

المشروع لا يتجاوز licenses.

مثال:

```text
Stata detected: Yes
Edition: MP
Version: 19
License availability: detected/unknown
```

أو:

```text
MATLAB detected.
Econometrics Toolbox: unavailable.
```

---

# 106. Performance

- lazy loading عندما يناسب.
- Arrow/Parquet.
- avoid unnecessary copies.
- parallel execution فقط للعمليات المستقلة.
- streaming logs.
- cache.
- cancellation.

---

# 107. Parallel Backend Comparison

```econ
compare backends:
    model = m1
    backends = r, stata, python
    parallel = yes
```

---

# 108. Timeouts

```econ
execution:
    timeout = 300
```

يجب أن يتم cleanup بعد timeout.

---

# 109. Cancellation

Notebook/GUI يجب أن يسمح بإيقاف العملية بأمان دون ترك temp files/processes قدر الإمكان.

---

# 110. Transaction/Resume

إذا pipeline توقف:

- تبقى artifacts المكتملة.
- يسجل failed step.
- يمكن resume.

```econ
resume pipeline macro_pipeline
```

---

# 111. Pipelines

```econ
pipeline macro_pipeline:
    load
    clean
    unitroot
    ardl
    diagnostics
    forecast
    export
```

يمكن في النسخة الأولى أن تكون مجرد orchestration syntax بسيطة.

---

# 112. Reusable Groups

```econ
group controls = age, gender, education
group macro = inflation, interest_rate, exchange_rate
```

```econ
model ols m1:
    y = growth
    x = macro
```

---

# 113. High-Level Loops

لا نبني لغة برمجة كاملة مبكرًا، لكن يمكن دعم:

```econ
for v in gdp, inflation, unemployment:
    unitroot v:
        test = adf
```

---

# 114. Scenarios

```econ
scenario optimistic:
    inflation = 2
    interest_rate = 3
```

```econ
forecast m1:
    scenario = optimistic
```

---

# 115. Spatial Econometrics لاحقًا

```econ
spatial weights W:
    method = queen
```

```econ
model sar s1:
    y = growth
    x = investment
    weights = W
```

دعم:

- SAR
- SEM
- SDM
- SAC
- spatial panel

---

# 116. SEM لاحقًا

```econ
model sem sem1:
    equations:
        y1 <- x1 + x2
        y2 <- y1 + x3
```

---

# 117. Bayesian Econometrics لاحقًا

```econ
model bayes_linear b1:
    y = y
    x = x1, x2
    prior beta = normal(0,10)
```

---

# 118. DSGE لاحقًا

يفضل Module خاصًا بسبب:

- equations.
- calibration.
- priors.
- solution methods.
- filtering.
- Bayesian estimation.
- IRFs.

لا يضاف إلى MVP.

---

# 119. Documentation Commands

```econ
help ardl
```

يعرض:

- description.
- syntax.
- required fields.
- optional fields.
- examples.
- backend support.
- common errors.
- references.

يمكن إضافة:

```econ
learn ardl
```

لشرح تعليمي مفصل.

---

# 120. Internationalization

Syntax يفضل أن يبقى إنجليزيًا.

لكن:

```econ
language = ar
```

يمكن أن يجعل:

- errors بالعربية.
- warnings بالعربية.
- explanations بالعربية.
- help بالعربية.

---

# 121. Example Arabic Error

```text
E405 — بنية Panel غير معرّفة

طلبت تقدير نموذج Fixed Effects، لكن لم يتم تعريف:
    متغير الوحدة
    متغير الزمن

استخدم:

set panel:
    id = country
    time = year
```

---

# 122. Plugin Architecture

Estimator plugin يمكن أن يضيف:

- estimator specification.
- semantic rules.
- IR schema/extension.
- backend compilers.
- result parser.
- docs.
- tests.

هيكل محتمل:

```text
plugins/
└── local_projection/
    ├── spec.py
    ├── validators.py
    ├── python_backend.py
    ├── r_backend.py
    ├── stata_backend.py
    ├── docs.md
    └── tests/
```

---

# 123. Future Backends

- Julia
- Gretl
- OxMetrics
- SAS
- SPSS
- cloud workers

الـCore لا يتغير جوهريًا.

---

# 124. Backend-Specific Escape Options

للحالات النادرة:

```econ
model ols m1:
    y = y
    x = x1, x2

    backend_options:
        stata:
            noheader = yes
```

يجب إبقاؤها في آخر الأولويات حتى لا تفسد portability.

---

# 125. Testing Strategy

## Unit Tests

- lexer/parser.
- AST.
- validators.
- IR.
- capability resolver.
- planners.
- result parsers.
- error formatter.

## Golden Compiler Tests

Input:

```econ
model ols m1:
    y = y
    x = x1, x2
```

Expected backend code لكل Backend.

## Integration Tests

تشغيل حقيقي عند توفر البرامج.

## Cross-Backend Numerical Tests

نفس dataset والنموذج، ثم مقارنة النتائج بتسامح Tolerance موثق.

---

# 126. Test Datasets

يفضل datasets صغيرة وثابتة لـ:

- OLS
- IV
- Logit
- ARDL
- VAR
- FE
- RE
- GMM
- DID

مع expected outputs موثقة.

---

# 127. Result Validation

بعد parsing:

- عدد coefficients منطقي.
- أسماء coefficients صحيحة.
- N موجود.
- p-values ضمن [0,1].
- convergence status محفوظ.
- missing statistics مسجلة لا مخفية.
- backend warnings محفوظة.

---

# 128. Numeric Tolerance

Cross-backend comparisons يجب أن تستخدم:

- absolute tolerance.
- relative tolerance.

ولا تفترض التطابق التام، لأن defaults والخوارزميات قد تختلف.

---

# 129. AI Assistant Layer

اختياري:

```text
User: Estimate an ARDL of GDP on inflation and exchange rate, max lag 4.
```

AI يقترح:

```econ
model ardl m1:
    y = gdp
    x = inflation, exchange_rate
    max_lag = 4
    select = AIC
```

ثم Validator الحقيقي يفحصه.

---

# 130. AI Guardrails

المسار:

```text
Natural language
→ proposed EconLang
→ parser
→ validation
→ plan
→ execution
```

لا:

```text
LLM → arbitrary shell/backend execution
```

---

# 131. MVP 0.1

## Backends

- Python
- R
- Stata
- EViews

MATLAB وGAUSS: Adapter interfaces/stubs في البداية إذا لزم.

## Features

- project.
- data load.
- describe/schema/summary.
- transformations الأساسية.
- time declaration.
- panel declaration.
- OLS.
- FE.
- RE.
- ADF.
- ARDL أساسي.
- heteroskedasticity.
- serial correlation.
- normality.
- VIF.
- predict/residuals.
- line/scatter/histogram.
- unified tables.
- unified errors.
- unified results.
- CSV/XLSX/HTML export.
- dryrun.
- show generated code.
- econ doctor.

---

# 132. Vertical Slice الأولى

لا تبدأ بمئة Model.

ابنِ المسار الكامل التالي أولًا:

```text
Load CSV/XLSX
→ Parse one OLS model
→ Semantic validation
→ Econometric IR
→ Python backend compiler
→ Execute statsmodels
→ Parse result
→ ModelResult
→ Table
→ Export
```

ثم R، ثم Stata، ثم EViews.

---

# 133. المرحلة الثانية

- IV.
- Logit/Probit.
- VAR/VECM.
- GARCH.
- Dynamic Panel GMM.
- advanced tables.
- report generation.
- cross-backend comparison.

---

# 134. المرحلة الثالثة

- DID/RDD/Synthetic Control.
- DML.
- spatial.
- Bayesian.
- ML.
- plugins.
- remote execution.
- GUI/IDE.

---

# 135. ما يجب تجنبه

- تقليد Stata syntax بالكامل.
- ربط parser مباشرة ببرنامج.
- تحويل اللغة إلى Python wrapper فقط.
- إظهار stack traces للمستخدم العادي.
- parsing للـhuman-readable output إذا كان structured API متوفرًا.
- تجاهل backend versions.
- تجاهل sample metadata.
- تجاهل data provenance.
- تثبيت packages تلقائيًا دون إذن.
- تغيير estimator بصمت.
- اعتماد الـCore على LLM.
- إضافة كل النماذج قبل استقرار المعمارية.

---

# 136. مثال Workflow كامل — Time Series

```econ
project "inflation-study"

backend = auto
seed = 2026
theme = publication
strict = standard

data load "macro.xlsx":
    sheet = "data"

set time:
    variable = year
    frequency = annual

describe
missing report
duplicates report

transform:
    l_gdp = log(gdp)
    d_l_gdp = diff(l_gdp)

unitroot l_gdp:
    test = adf
    deterministic = trend
    lags = auto
    criterion = AIC

unitroot inflation:
    test = adf
    deterministic = constant
    lags = auto

model ardl ardl_main:
    y = l_gdp
    x = inflation, exchange_rate
    max_lag = 4
    select = AIC

diagnostics ardl_main:
    autocorrelation
    heteroskedasticity
    normality
    stability

derive ecm ecm_main from ardl_main

forecast ardl_main:
    horizon = 5
    interval = 95
    save = gdp_forecast

plot forecast:
    model = ardl_main
    theme = publication
    title = "GDP Forecast"

table ardl_main ecm_main:
    show = coefficients, se, pvalues
    stats = n, aic, bic

export table to "tables/model_results.xlsx"
export graph to "graphs/forecast.svg"

report create:
    title = "Inflation and GDP Study"
    include = data_summary, ardl_main, ecm_main, diagnostics, graphs
    format = html
```

---

# 137. مثال Workflow كامل — Panel

```econ
project "panel-growth"

data "panel.xlsx"

set panel:
    id = country
    time = year

precheck:
    missing
    duplicates
    multicollinearity

model fe fe1:
    y = growth
    x = investment, trade, inflation
    effects = entity, time
    cluster = country

model re re1:
    y = growth
    x = investment, trade, inflation

compare fe1 re1:
    test = hausman

diagnostics fe1:
    heteroskedasticity
    autocorrelation
    cross_sectional_dependence

table fe1 re1:
    show = coefficients, se, stars
```

---

# 138. مثال Workflow — Causal DID

```econ
project "policy-did"

data "firms.dta"

set panel:
    id = firm
    time = year

model did did1:
    outcome = employment
    unit = firm
    time = year
    treatment = treated
    method = staggered
    controls = size, age

diagnostics did1:
    pretrends

plot event_study:
    model = did1
    theme = publication
```

---

# 139. تعريف النجاح

ينجح المشروع عندما يستطيع الباحث:

1. تحميل البيانات مرة واحدة.
2. تعريف البنية الزمنية/Panel مرة واحدة.
3. كتابة model واحد بلغة واضحة.
4. تشغيله على backend مختلف دون إعادة كتابة التحليل.
5. الحصول على Result موحد.
6. رؤية أخطاء مفهومة.
7. معرفة الكود الأصلي الذي نفذه كل Backend.
8. مقارنة النتائج بين البرامج.
9. تصدير النتائج والرسوم بسهولة.
10. إعادة المشروع لاحقًا مع metadata كاملة.

---

# 140. Prompt كامل لـClaude

انسخ النص التالي بالكامل إلى Claude عند بدء مرحلة التصميم والتنفيذ:

```text
You are a principal software architect, compiler engineer, econometrician, and Python systems developer.

I want you to design and implement a production-quality open-source project that creates a HIGH-LEVEL UNIFIED ECONOMETRICS LANGUAGE called EconLang (working name).

The goal is NOT to create another statistical package and NOT to copy Stata, R, EViews, Python, MATLAB, or GAUSS syntax.

The goal is to create a backend-independent high-level econometrics DSL where researchers write WHAT econometric operation they want, while the system translates the request into an intermediate representation, validates it semantically and econometrically, chooses or uses a backend, executes the appropriate software, parses the result, and returns a unified result object.

Target backends:
1. Python
2. R
3. Stata
4. EViews
5. MATLAB
6. GAUSS

The architecture must allow future backends such as Julia, Gretl, OxMetrics, SAS, and others.

CORE DESIGN PRINCIPLE:
Write Econometrics, Not Software Syntax.

Example desired code:

data "macro.xlsx"

set time:
    variable = year
    frequency = annual

model ardl growth_model:
    y = gdp
    x = inflation, exchange_rate
    max_lag = 4
    select = AIC

diagnostics growth_model:
    autocorrelation
    heteroskedasticity
    normality
    stability

forecast growth_model:
    horizon = 5

export growth_model to "results.xlsx"

==================================================
ARCHITECTURE
==================================================

Use a layered architecture:

EconLang Source
→ Lexer/Parser
→ AST
→ Semantic Validator
→ Econometric Validator
→ Econometric Intermediate Representation (IR)
→ Capability Resolver
→ Execution Planner
→ Backend Compiler/Adapter
→ Backend Execution
→ Raw Output Parser
→ Unified Result Object
→ Result Store / Tables / Graphs / Reports / Export

Do NOT translate source code directly to Stata/R/Python/etc.
The IR must be backend-independent and represent econometric meaning rather than backend syntax.

Design a clean Backend interface such as:

detect()
version()
capabilities()
validate(ir)
compile(ir)
execute(plan)
parse_result(raw_output)
cleanup()

==================================================
LANGUAGE DESIGN
==================================================

Design a readable indentation-based DSL.

Support:
- comments
- named models
- reusable groups
- model blocks
- diagnostics blocks
- graph blocks
- export blocks
- project settings
- backend settings
- strictness settings
- seeds
- beginner and expert options

Example:

model ols m1:
    y = income
    x = education, age, experience
    vcov = HC3

Do not overcomplicate the grammar.
The parser must generate informative syntax errors.

Evaluate Lark, ANTLR, Tree-sitter, or another suitable parser technology. Explain the choice.
Tree-sitter may later be useful for IDE tooling, but select the best implementation path for an MVP.

==================================================
DATA LAYER
==================================================

Design a canonical Dataset object.
It should store:
- source
- schema
- variable names
- variable types
- labels
- units
- missing rules
- time structure
- panel structure
- transformations
- provenance
- dataset hash
- sample metadata

Prefer Apache Arrow / Parquet internally where practical.

Support loading:
CSV
Excel
Stata DTA
R files where practical
EViews exports where practical
MAT files
Parquet
Arrow
SQL later
URL/API later

Commands should include:
data
describe
schema
summary
head
tail
missing report
duplicates report
sample
transform
snapshot

==================================================
TIME AND PANEL STRUCTURE
==================================================

Support:

set time:
    variable = year
    frequency = annual

set panel:
    id = country
    time = year

Detect:
duplicate time values
gaps
unbalanced panels
invalid dates
frequency problems
duplicate id-time pairs
singleton groups when relevant

==================================================
TRANSFORMATIONS
==================================================

Support:
log
exp
sqrt
lags
leads
differences
growth rates
percentage changes
interactions
polynomials
dummy variables
seasonal dummies
trends
standardization
winsorization
outlier handling
missing-value handling

Every transformation must be recorded in data provenance.

==================================================
PRE-ESTIMATION
==================================================

Support a precheck system.

Examples:

precheck:
    missing
    outliers
    multicollinearity
    stationarity

Include interfaces for:
unit root tests
cointegration tests
lag selection
structural breaks
panel dependence
descriptive statistics
correlation
data readiness checks

The system should be able to produce a Model Readiness Report.

==================================================
ESTIMATION
==================================================

Design an estimator registry so new estimators can be added without rewriting the core.

Eventually support:
OLS
WLS
GLS
robust regression
IV / 2SLS
LIML
GMM
logit
probit
ordered models
multinomial models
Tobit
Heckman
Poisson
Negative Binomial
quantile regression

TIME SERIES:
AR
MA
ARMA
ARIMA
ARDL
ECM
VAR
SVAR
VECM
ARCH
GARCH
EGARCH
GJR-GARCH
other volatility models

PANEL:
Fixed Effects
Random Effects
Two-Way FE
Difference GMM
System GMM
PMG
MG
DFE
CCE
CS-ARDL
panel quantile

CAUSAL:
Difference-in-Differences
staggered DID
event studies
RDD
matching
synthetic control
DML

Later:
spatial econometrics
Bayesian econometrics
SEM
DSGE
machine learning

DO NOT implement everything in version 0.1.
Design the interfaces for extensibility, but build an MVP first.

==================================================
POST-ESTIMATION
==================================================

Support interfaces for:
heteroskedasticity tests
serial correlation tests
normality tests
VIF
RESET
stability
structural breaks
Hausman
weak-instrument tests
overidentification tests
marginal effects
predictions
residuals
IRF
FEVD
Granger causality
forecasting

==================================================
UNIFIED RESULTS
==================================================

Create structured result classes.

A ModelResult should include at least:
id
name
model_type
estimator_family
backend
backend_version
generated_backend_code
dataset_id
dataset_hash
sample
nobs
coefficients
standard_errors
test_statistics
p_values
confidence_intervals
covariance_info
fit_statistics
residuals
fitted_values
predictions
diagnostics
convergence
warnings
execution_time
timestamp
reproducibility_metadata

Do not store backend results only as human-formatted text.

Users should later be able to write:
show m1.coefficients
show m1.pvalues
show m1.aic
show m1.residuals

Also design TestResult, GraphResult, TableResult, ForecastResult, and ExportResult where appropriate.

==================================================
RESULT STORE
==================================================

Create a registry for:
datasets
models
tests
graphs
tables
exports
reports

Suggested project layout:

project/
    data/
    models/
    results/
    graphs/
    tables/
    reports/
    exports/
    logs/
    cache/
    project.json

Consider SQLite + JSON + Parquet/Arrow.

==================================================
GRAPHICS
==================================================

Create a backend-independent graph specification.

Support:
line
scatter
histogram
density
boxplot
violin
bar
ACF
PACF
QQ
residual plots
coefficient plots
forecast plots
actual-vs-fitted
IRF
FEVD
event-study plots
ROC
confusion matrix

Implement a unified theme system:
research
publication
presentation
light
dark
monochrome
colorblind_safe

Graphs should support:
titles
subtitles
axis labels
legends
captions
sources
high DPI
PNG
SVG
PDF

Store graph metadata in GraphResult objects.

==================================================
TABLES AND EXPORT
==================================================

Support:
descriptive-statistics tables
regression tables
model comparison
diagnostic tables

Example:

table m1 m2 m3:
    show = coefficients, se, stars
    stats = n, r2, aic, bic

Support export to:
CSV
Excel
JSON
Parquet
HTML
Markdown
LaTeX
PNG
SVG
PDF

Plan Word/PDF reports later.

==================================================
ERROR SYSTEM
==================================================

This is CRITICAL.
Do not expose raw backend errors to normal users.

Create stable error codes.

Suggested categories:
E1xx Data
E2xx Syntax
E3xx Semantic
E4xx Econometric
E5xx Backend
E6xx Execution
E7xx Capability
E8xx Export
E9xx Internal

Example:

E101 — Variable not found

Variable: GDP

GDP does not exist in the active dataset.

Did you mean:
    gdp
    GDP_real
    logGDP

Available variables:
    year
    gdp
    inflation
    exchange_rate

Another example:

E405 — Panel structure is missing

A Fixed Effects model requires:
entity variable
time variable

Example:

set panel:
    id = country
    time = year

Every error should ideally provide:
error code
human-readable title
what happened
where
probable cause
suggested fix
valid example
Did-you-mean suggestions
documentation reference
raw backend error only in verbose/debug mode

==================================================
WARNINGS
==================================================

Warnings should not necessarily block execution.

Examples:
possible spurious regression
small sample
few clusters
weak instruments
too many instruments
non-convergence
near multicollinearity
unbalanced panel
heteroskedasticity
autocorrelation
extrapolation

Support:
strict = low
strict = standard
strict = high

==================================================
BACKEND CAPABILITY MATRIX
==================================================

Design a capability registry that can answer:
Does backend X support estimator Y?
Does it support option Z?
Does it require package Q?
What version is required?
Is support full/partial/experimental/unavailable?

Provide user-facing messages such as:

Requested:
System GMM

Backend:
EViews

Support:
Partial

Recommended:
Stata
R

==================================================
BACKEND AUTO-SELECTION
==================================================

Support:
backend = auto

Selection may consider:
backend availability
model support
version
license/toolbox availability
required packages
performance
user preferences
operating system
reproducibility

Do not silently change estimators or covariance definitions.
If a fallback changes statistical meaning, it must be surfaced explicitly.

==================================================
BACKEND COMPARISON
==================================================

Support running the same model in multiple engines.

Example:

compare backends:
    model = m1
    backends = python, r, stata, eviews

Normalize coefficients, standard errors, p-values, sample size and fit statistics.
Use documented numerical tolerances.
Record methodological/default differences.

==================================================
BACKEND IMPLEMENTATION
==================================================

PYTHON:
Potential packages:
pandas
polars
numpy
scipy
statsmodels
linearmodels
arch
scikit-learn
doubleml

R:
Use subprocess or another robust strategy.
Do not require rpy2 as the only possible integration.
Potential packages:
stats
lmtest
sandwich
plm
fixest
vars
urca
forecast
dynlm
ARDL
did
others as needed

STATA:
Support executable detection.
Potential integration approaches:
batch do-files
PyStata when available
temporary data exchange
structured result extraction
log parsing only where necessary

Do not assume PyStata is always available.
Detect edition and version where possible.

EVIEWS:
On Windows consider:
COM automation if supported
generated EViews program files
workfile/data exchange
saved result extraction

Keep EViews integration isolated behind the adapter.

MATLAB:
Consider MATLAB Engine API for Python and batch execution.
Detect Econometrics Toolbox availability.

GAUSS:
Use CLI/batch execution where possible.
Generate GAUSS code and parse standardized outputs.

==================================================
EXECUTION
==================================================

Implement:
timeouts
cancellation
temporary working directories
stdout capture
stderr capture
cleanup
execution status
structured logs
safe process invocation

Statuses:
pending
running
completed
completed_with_warning
failed
cancelled
cached

==================================================
REPRODUCIBILITY
==================================================

Every result should record:
original EconLang source
normalized IR
generated backend code
backend name
backend version
package/toolbox versions
dataset hash
sample
seed
system metadata
execution timestamp
execution duration

Provide:
audit m1
reproducibility report m1
show code m1
dryrun m1

==================================================
DRY RUN
==================================================

dryrun should show:
parsed meaning
semantic validation
econometric validation
selected backend
required packages
generated backend command/code
planned outputs

without executing.

==================================================
CACHING
==================================================

Use a cache key built from:
normalized IR
dataset hash
backend
backend version
package versions
seed

Never return stale results if material inputs changed.

==================================================
PROJECT FILE
==================================================

Use or evaluate econproject.toml.

Example:

[project]
name = "macro-study"

[defaults]
backend = "auto"
theme = "publication"
seed = 12345
strict = "standard"

[paths]
data = "data"
results = "results"
graphs = "graphs"
exports = "exports"
logs = "logs"

==================================================
CLI
==================================================

Create a CLI such as:

econ run analysis.econ
econ validate analysis.econ
econ doctor
econ backends
econ models
econ help ardl

`econ doctor` should detect:
Python
R
Stata
EViews
MATLAB
GAUSS
versions
paths
packages/toolboxes
basic connectivity
write permissions

==================================================
JUPYTER
==================================================

Design support for:

%%econ

and possibly:

%econ backend stata

Notebook output should display:
clean tables
warnings
graphs
generated-code tabs
backend metadata

==================================================
GUI / IDE
==================================================

Do not build a heavy GUI in the first milestone, but design for it.
Future IDE panes:
Editor
Data Viewer
Variable Explorer
Model Explorer
Results
Tables
Graphs
Diagnostics
Backend Selector
Console
Project Browser

Plan for syntax highlighting and autocomplete.

==================================================
AUTOCOMPLETE
==================================================

Autocomplete should be semantic.

After:
model
suggest estimators.

Inside:
model ardl:
suggest only ARDL options.

For:
y =
suggest numeric variables from the active dataset.

==================================================
SECURITY
==================================================

Do not execute arbitrary shell code from normal EconLang.

Implement:
path validation
safe subprocess calls
temporary directories
command injection protection
SQL parameterization
secret redaction
timeouts
resource limits where practical

Create an explicit advanced RAW BACKEND mode if needed, clearly marked as non-portable and advanced.

==================================================
AI
==================================================

The core system must NOT require an LLM.
Optionally later add:

Natural language
→ proposed EconLang
→ parser
→ validator
→ execution

The LLM must not execute backend code directly.
EconLang should remain the reproducible source of truth.

==================================================
TESTING
==================================================

Create:
parser unit tests
AST tests
semantic-validation tests
econometric-validation tests
IR tests
backend compiler golden tests
result-parser tests
error-message tests
integration tests
cross-backend numerical tests

For golden tests:
Given EconLang input,
assert exact or normalized generated backend code.

For cross-backend tests:
run known datasets and compare coefficients using documented tolerance.

==================================================
PLUGIN SYSTEM
==================================================

Plan an estimator plugin architecture.
A plugin should be able to contribute:
estimator specification
semantic/econometric validation
backend implementations
result parser
documentation
tests

Avoid requiring parser-core changes for every ordinary estimator if possible.

==================================================
MVP
==================================================

Build version 0.1 around:

Backends:
Python
R
Stata
EViews

Core operations:
data load
describe
schema
summary
transform
time declaration
panel declaration
OLS
Fixed Effects
Random Effects
ADF
basic ARDL
heteroskedasticity
serial correlation
normality
VIF
predictions
residuals
basic tables
line/scatter/histogram
unified errors
unified results
CSV/Excel/HTML export
show generated code
dry run
econ doctor

Do not implement MATLAB and GAUSS in the first full implementation unless creating adapter stubs/interfaces.

==================================================
CODE QUALITY
==================================================

Use a modern supported Python baseline, preferably Python 3.11+ unless compatibility requirements justify otherwise.

Use:
type hints
dataclasses or Pydantic where appropriate
clear interfaces
small modules
pytest
structured logging
ruff
mypy where useful
pre-commit
GitHub Actions
semantic versioning

Do not produce one giant Python file.

==================================================
DOCUMENTATION
==================================================

Create:
README.md
ARCHITECTURE.md
LANGUAGE_SPEC.md
BACKENDS.md
ERROR_CODES.md
CONTRIBUTING.md
examples/
docs/

Provide complete examples for:
OLS
time series
panel
cross-backend comparison

==================================================
IMPLEMENTATION PROCESS
==================================================

Do not jump immediately into hundreds of files.

First produce:
1. architecture decision record
2. proposed repository tree
3. formal MVP scope
4. grammar proposal
5. AST design
6. IR design
7. error-code specification
8. Backend abstract interface
9. Dataset schema
10. Result object schemas
11. execution lifecycle
12. capability matrix design
13. storage/reproducibility design
14. graph specification
15. test strategy

Then implement a vertical slice:

data load
→ parse one OLS model
→ validate
→ create IR
→ compile to Python
→ execute
→ parse result
→ Unified ModelResult
→ table output
→ export

After that add R.
Then Stata.
Then EViews.

For each backend, keep the same tests wherever statistically meaningful.

==================================================
IMPORTANT DEVELOPMENT RULES
==================================================

1. Never tightly couple the core to one backend.
2. Never expose raw exceptions as the normal UX.
3. Never use an LLM as the parser.
4. Never lose generated backend code.
5. Never lose data provenance.
6. Never silently change statistical methodology.
7. Never assume every backend has identical capabilities.
8. Never hard-code package-specific details into the language layer.
9. Preserve reproducibility metadata.
10. Prefer structured objects over parsing human-formatted text whenever APIs permit.
11. Clearly separate syntax errors from econometric warnings.
12. Write tests before adding many estimators.
13. Keep the first release small but architecturally correct.
14. Make Windows integration a first-class concern because Stata and EViews will often run there.
15. Keep the portable core compatible with Linux/macOS whenever possible.
16. Clearly mark proprietary-software integration code.
17. Never install packages silently.
18. Never overwrite user data or results without explicit policy.
19. Make every backend execution auditable.
20. Design error codes to be stable public API identifiers.

==================================================
DELIVERABLE I WANT FROM YOU
==================================================

Start by giving me a complete technical design before writing a large amount of code.

For the first implementation response, I want:

A. Proposed architecture
B. Repository tree
C. DSL grammar
D. AST definitions
E. Econometric IR schemas
F. Semantic and econometric validator design
G. Error taxonomy
H. Backend interface
I. Dataset schema
J. ModelResult/TestResult/GraphResult schemas
K. Execution plan design
L. Capability registry design
M. Storage/reproducibility design
N. Graph/theme design
O. Python backend design
P. R/Stata/EViews adapter designs
Q. Testing strategy
R. MVP roadmap
S. Risks and technical tradeoffs
T. Exact vertical-slice implementation plan

After the design is complete, implement the MVP vertical slice.

When writing code:
- provide complete files, not fragments
- show each filename
- maintain import consistency
- include tests
- include sample `.econ` programs
- include a small reproducible example dataset generator
- include setup instructions
- include Windows-first integration notes
- keep the core portable
- mark proprietary backend requirements explicitly

Treat this as a serious compiler/runtime/econometrics infrastructure project, not as a simple command translator.
```

---

# 141. القرار النهائي الذي يجب الحفاظ عليه

لا تسأل أولًا:

> كيف نحول أمر OLS إلى ست لغات؟

بل:

> ما التمثيل المجرد Econometric Meaning لنموذج OLS داخل منصتنا؟

ثم:

```text
Source
→ Meaning
→ Validation
→ IR
→ Execution Plan
→ Backend
→ Unified Results
```

هذا هو الفرق بين **Translator صغير** و**Econometrics Runtime/Language قابلة للتوسع لسنوات**.

---

# 142. الخلاصة

المشروع في صورته الكاملة يتكون من أربع طبقات فكرية كبرى:

1. **Unified Language** — لغة موحدة عالية المستوى.
2. **Unified Execution** — تشغيل على عدة محركات قياسية.
3. **Unified Results** — نتائج وجداول ورسوم موحدة.
4. **Econometric Intelligence & Validation** — فهم المتطلبات والأخطاء والتحذيرات القياسية قبل وبعد التنفيذ.

والهدف النهائي:

```text
One econometric workflow
        ↓
Multiple statistical engines
        ↓
One consistent research experience
```

> **Write Econometrics, Not Software Syntax.**
