# API reference

## Top level

```python
import econenv

econenv.__version__
econenv.engine(name, **options)      -> BaseEngine
econenv.engines()                    -> list[dict]
econenv.status()                     -> DataFrame
econenv.doctor(engine=None, deep=False) -> diagnostics.Report
econenv.snapshot(**kwargs)           -> dict
econenv.push(engine, name, obj)
econenv.pull(engine, name=None)
econenv.move(source, target, name)   -> DataFrame
econenv.compare_ols(data, formula=None, *, depvar=None, exog=None,
                    engines=None, constant=True, vcov=None) -> ComparisonResult
```

Extension hooks: `load_ipython_extension`, `unload_ipython_extension`.

## `econenv.engines`

```python
from econenv.engines import registry

registry.names()          -> list[str]
registry.get(name)        -> BaseEngine        (singleton per name)
registry.info(name=None)  -> list[EngineInfo]
registry.available()      -> list[str]
registry.running()        -> list[str]
registry.register(cls, replace=False)
registry.unregister(name)
registry.stop_all()
registry.reset(name=None)
registry.plugin_errors()  -> dict[str, str]
```

### `BaseEngine`

```python
engine.detect(force=False) -> bool
engine.available           -> bool
engine.running             -> bool
engine.state               -> EngineState
engine.configure(**options)
engine.start() / stop() / restart() / cleanup()
engine.ensure_started()
engine.execute(code, **kwargs) -> ExecutionResult
engine.version()           -> str | None
engine.push(name, obj, **kwargs)
engine.pull(name=None, **kwargs)
engine.pull_scalar(expression)
engine.pull_matrix(name)
engine.capabilities()      -> list[Capability]
engine.has(capability)     -> bool
engine.info()              -> EngineInfo
```

`Capability`: `EXECUTE`, `PERSISTENT_SESSION`, `PUSH_FRAME`, `PULL_FRAME`,
`PUSH_SCALAR`, `PULL_SCALAR`, `PULL_MATRIX`, `GRAPHICS`, `OLS`, `RESTART`,
`INTERRUPT`.

`EngineState`: `UNKNOWN`, `NOT_INSTALLED`, `INSTALLED`, `CONFIGURED`,
`RUNNING`, `FAILED`, `STOPPED`.

Engine-specific: `EViewsEngine.set_visible(bool)`, `.graph_names()`,
`.capture_graph(name)`; `REngine.r_packages()`, `.has_r_package(name)`;
`StataEngine.load_official_magics(ipython)`; `PythonEngine.packages()`,
`.all_packages()`, `.namespace`.

## `econenv.config`

```python
config.as_dict()                       -> dict[str, dict]
config.get_option(section, key, default=None)
config.section(name)                   -> dict
config.set_option(section, key, value)     # runtime layer; validates the key
config.reset(section=None)
config.config_path()                   -> Path
config.sources()                       -> dict
config.reload()
```

Sections and keys: `core.{log_level, autostart, timeout}`;
`r.{home, backend, executable, graphics, width, height, dpi, transfer,
claim_r_magic}`; `stata.{home, edition, splash, graph_format,
use_official_magics}`; `eviews.{progid, instance, busy_retries, show_window,
graphics, width, height, keep_temp}`.

## `econenv.transfer`

```python
transfer.push / pull / move
transfer.conversion_report(frame) -> ConversionReport | None
transfer.metadata(frame)          -> DatasetMetadata | None
transfer.annotate(frame, *, name, time_var, panel_var, frequency)
transfer.dataset_report(frame)    -> list[str]
transfer.snapshot(include_packages=True, deep=False)
transfer.save_snapshot(path, **kwargs)
transfer.hash_code(code) / hash_frame(df)
transfer.provenance(*, engine, code, data=None, elapsed=None)
```

## `econenv.schema`

`LogicalType`, `Severity`, `ColumnSchema`, `DatasetMetadata`,
`ConversionNote`, `ConversionReport`; `logical_type_of(series)`,
`describe_frame(df, ...)`, `restore_categoricals(df, meta)`.

## `econenv.results`

`ExecutionResult`, `ModelResult`, `Figure` — see [results.md](results.md).

## `econenv.models`

```python
ModelSpec(depvar, exog, estimator="ols", constant=True, vcov=None, ...)
ModelSpec.from_formula("y ~ x1 + x2")
parse_spec("y x1 x2")
model_registry.get(key) / .keys() / .matrix()
run_spec(spec, data, engines=None, rtol=, atol=, strict=False)
compare_ols(...)
ComparisonResult.coefficients() / .summary() / .differences() / .explain() / .agree
```

## `econenv.diagnostics`

`Status`, `Check`, `Report`, `run(engine=None, deep=False)`, and the individual
`check_host`, `check_config`, `check_r`, `check_stata`, `check_eviews`.

## `econenv.discovery`

`Installation`, `find_r(configured=None)`, `find_stata(configured=None)`,
`find_eviews()`, `eviews_progids()`, `pystata_path(home)`, `host_info()`.

## Exceptions

```
EconEnvError
├── ConfigurationError
├── EngineError
│   ├── EngineNotFoundError
│   ├── EngineUnavailableError
│   ├── EngineNotConfiguredError
│   ├── EngineStartError
│   ├── EngineNotStartedError
│   ├── EngineExecutionError      (.code, .stdout, .stderr)
│   ├── EngineTimeoutError
│   └── SessionError
├── DataTransferError
│   ├── UnsupportedDataTypeError
│   └── LossyConversionError
├── ModelSpecificationError
└── CapabilityError
```

Every `EngineError` carries `.engine`, `.raw` (the untouched vendor exception)
and often `.hint`. Helpers: `describe(exc)`, `com_message(exc)`.
