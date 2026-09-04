"""Engine-neutral model specification and cross-engine comparison (sections 22-26 of the brief)."""

from .compare import ComparisonResult, compare_ols, run_spec
from .registry import ModelRegistry, model_registry
from .spec import ModelSpec

__all__ = [
    "ComparisonResult",
    "ModelRegistry",
    "ModelSpec",
    "compare_ols",
    "model_registry",
    "run_spec",
]
