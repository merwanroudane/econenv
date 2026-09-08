"""The Econometric Intermediate Representation.

This is the layer the specification insists on (section 2): the AST records what
was *written*, and the IR records what it *means*, so no backend ever sees
syntax. That separation is what makes this a runtime rather than a translator —
a new backend is a new lowering from the IR, and touches nothing else.

The IR deliberately reuses :class:`econenv.models.spec.ModelSpec`, which
already carries the neutral description of an estimation and is what
``compare_ols`` and every engine's ``_fit_ols`` speak. Inventing a parallel
schema would mean two things to keep in step.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..models.spec import ModelSpec
from .errors import Location


@dataclass
class DataSource:
    """Where the data came from, kept for provenance (section 16)."""

    path: str
    options: Dict[str, Any] = field(default_factory=dict)
    location: Optional[Location] = None


@dataclass
class TimeStructure:
    """A declared time index."""

    variable: str
    frequency: Optional[str] = None
    location: Optional[Location] = None


@dataclass
class PanelStructure:
    """A declared panel index."""

    entity: str
    time: str
    location: Optional[Location] = None


@dataclass
class ModelPlan:
    """One model, lowered: what to estimate, where, and how it was written.

    ``spec`` is the neutral description. ``engine`` is resolved separately by
    the planner, so the same plan can be run on several backends without being
    rebuilt — which is what makes the cross-engine comparison honest.
    """

    name: str
    estimator: str
    spec: ModelSpec
    engine: str = "python"
    options: Dict[str, Any] = field(default_factory=dict)
    option_locations: Dict[str, Location] = field(default_factory=dict)
    location: Optional[Location] = None

    def where(self, option: str) -> Optional[Location]:
        """Where *option* was written, for an error that points at it."""
        return self.option_locations.get(option, self.location)

    def described(self) -> str:
        """One line a researcher would recognise as their own model."""
        right = " + ".join(self.spec.exog) if self.spec.exog else "1"
        text = f"{self.spec.depvar} ~ {right}"
        if not self.spec.constant:
            text += " - 1"
        return text


@dataclass
class Action:
    """Something to do with a model once it exists: show, explain, export."""

    verb: str
    target: Optional[str] = None
    arguments: List[Any] = field(default_factory=list)
    location: Optional[Location] = None


@dataclass
class ResearchProgram:
    """A whole program, lowered and ready to run."""

    project: Optional[str] = None
    settings: Dict[str, Any] = field(default_factory=dict)
    data: Optional[DataSource] = None
    time: Optional[TimeStructure] = None
    panel: Optional[PanelStructure] = None
    models: Dict[str, ModelPlan] = field(default_factory=dict)
    actions: List[Action] = field(default_factory=list)
    source: str = ""

    @property
    def default_engine(self) -> str:
        return str(self.settings.get("backend", "python"))

    def __str__(self) -> str:
        parts = []
        if self.project:
            parts.append(f"project {self.project!r}")
        if self.data:
            parts.append(f"data {self.data.path!r}")
        if self.time:
            parts.append(f"time on {self.time.variable}")
        if self.panel:
            parts.append(f"panel {self.panel.entity}/{self.panel.time}")
        parts.append(f"{len(self.models)} model(s)")
        return "ResearchProgram(" + ", ".join(parts) + ")"
