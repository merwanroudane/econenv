"""EconEnv — One Notebook. Multiple Econometric Engines.

Python, R, Stata and EViews in a single Jupyter session, with one Python kernel.

    %load_ext econenv

    %%R
    fit <- lm(y ~ x, data = df)

    %%stata
    regress y x

    %%eviews
    equation eq1.ls y c x

EconEnv distributes **no** commercial software. Stata and EViews must be
installed and licensed independently; see the LICENSE and README.
"""

from __future__ import annotations

from typing import Any, Optional

from ._logging import configure as configure_logging
from ._logging import get_logger
from ._version import __version__
from .exceptions import (
    CapabilityError,
    ConfigurationError,
    DataTransferError,
    EconEnvError,
    EngineError,
    EngineExecutionError,
    EngineNotConfiguredError,
    EngineNotFoundError,
    EngineStartError,
    EngineTimeoutError,
    EngineUnavailableError,
    LossyConversionError,
    ModelSpecificationError,
    SessionError,
    UnsupportedDataTypeError,
)
from .export import export, export_figures, export_table
from .results import ExecutionResult, Figure, ModelResult
from .schema import ColumnSchema, ConversionReport, DatasetMetadata, LogicalType

__all__ = [
    "CapabilityError",
    "ColumnSchema",
    "ComparisonResult",
    "ConfigurationError",
    "ConversionReport",
    "DataTransferError",
    "DatasetMetadata",
    "EconEnvError",
    "EngineError",
    "EngineExecutionError",
    "EngineNotConfiguredError",
    "EngineNotFoundError",
    "EngineStartError",
    "EngineTimeoutError",
    "EngineUnavailableError",
    "ExecutionResult",
    "Figure",
    "LogicalType",
    "LossyConversionError",
    "ModelResult",
    "ModelSpec",
    "ModelSpecificationError",
    "SessionError",
    "UnsupportedDataTypeError",
    "__version__",
    "broadcast",
    "compare_ols",
    "configure_logging",
    "doctor",
    "engine",
    "engines",
    "export",
    "export_figures",
    "export_table",
    "get_logger",
    "load_ipython_extension",
    "move",
    "pull",
    "push",
    "snapshot",
    "status",
    "transfer_matrix",
    "unload_ipython_extension",
]


# --------------------------------------------------------------------------- #
# top-level convenience API
# --------------------------------------------------------------------------- #
def engine(name: str, **options: Any):
    """Return the engine registered as *name*, creating its instance if needed."""
    from .engines import registry

    return registry.get(name, **options)


def engines() -> list:
    """Snapshot of every registered engine."""
    from .engines import registry

    return [info.to_dict() for info in registry.info()]


def status():
    """The engine table, ready for display."""
    from . import services

    return services.status_frame()


def doctor(engine_name: Optional[str] = None, *, deep: bool = False):
    """Run the diagnostics (brief §14)."""
    from . import diagnostics

    return diagnostics.run(engine_name, deep=deep)


def snapshot(**kwargs: Any) -> dict:
    """A reproducibility snapshot of the whole environment (brief §20)."""
    from . import transfer

    return transfer.snapshot(**kwargs)


def push(engine_name: str, name: str, obj: Any, **kwargs: Any) -> None:
    """Send a Python object into an engine."""
    from . import transfer

    transfer.push(engine_name, name, obj, **kwargs)


def pull(engine_name: str, name: Optional[str] = None, **kwargs: Any):
    """Fetch an object out of an engine."""
    from . import transfer

    return transfer.pull(engine_name, name, **kwargs)


def broadcast(name: str, obj: Any, engines: Any = None, **kwargs: Any):
    """Push one dataset into every available engine at once."""
    from .transfer import broadcast as _broadcast

    return _broadcast(name, obj, engines, **kwargs)


def transfer_matrix():
    """Which engines can send and receive data on this machine."""
    from .transfer import transfer_matrix as _matrix

    return _matrix()


def move(source: str, target: str, name: str, **kwargs: Any):
    """Move a dataset from one engine to another without touching a file."""
    from . import transfer

    return transfer.move(source, target, name, **kwargs)


def compare_ols(*args: Any, **kwargs: Any):
    """Run the same OLS in every available engine and compare (brief §22)."""
    from .models import compare_ols as _compare

    return _compare(*args, **kwargs)


def __getattr__(name: str) -> Any:
    """Lazily expose the model classes without importing pandas machinery early."""
    if name == "ModelSpec":
        from .models.spec import ModelSpec

        return ModelSpec
    if name == "ComparisonResult":
        from .models.compare import ComparisonResult

        return ComparisonResult
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# --------------------------------------------------------------------------- #
# IPython extension entry point
# --------------------------------------------------------------------------- #
def load_ipython_extension(ipython: Any) -> None:
    """``%load_ext econenv``.

    Registers every magic and reports which implementation won each name. No
    engine is started here — loading the extension must be fast and must not
    consume a Stata or EViews licence seat.
    """
    from ._logging import configure, level_from_env
    from .magics import register_all

    configure(level_from_env())
    registration = register_all(ipython)

    print(f"EconEnv {__version__} loaded — one notebook, multiple econometric engines.")
    for magic_name, owner in registration.items():
        print(f"  {magic_name:<22} {owner}")
    print("  %econ status · %econ doctor · %econ help")


def unload_ipython_extension(ipython: Any) -> None:
    """Stop every engine when the extension is unloaded."""
    from .engines import registry

    registry.stop_all()
