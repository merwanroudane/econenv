"""The AST EconLang parses into.

Deliberately small. The specification's architecture (§2) puts the *meaning* in
the Econometric IR, not in the syntax tree — so these nodes record what was
written and where, and nothing about what it implies. Validation and lowering
happen afterwards, which is what keeps a language from turning into a
translator with opinions baked into its grammar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .errors import Location


@dataclass
class Node:
    """Every node knows where it came from, so every error can point at it."""

    location: Optional[Location] = field(default=None, kw_only=True)


@dataclass
class Project(Node):
    """``project "inflation-study"``"""

    name: str


@dataclass
class Setting(Node):
    """A top-level ``key = value``, such as ``backend = auto``."""

    key: str
    value: Any


@dataclass
class DataLoad(Node):
    """``data "macro.csv"``, optionally with a block of options."""

    path: str
    options: Dict[str, Any] = field(default_factory=dict)
    option_locations: Dict[str, Location] = field(default_factory=dict)


@dataclass
class TimeDecl(Node):
    """``set time:`` with ``variable`` and ``frequency``."""

    variable: str
    frequency: Optional[str] = None


@dataclass
class PanelDecl(Node):
    """``set panel:`` with ``id`` and ``time``."""

    entity: str
    time: str


@dataclass
class Model(Node):
    """``model ols name:`` and its options.

    ``estimator`` is kept as the word the user wrote. Deciding whether it is
    supported belongs to the capability layer, not to the parser — so an
    unknown estimator produces a capability error naming the backends that do
    have it, rather than a syntax error.
    """

    estimator: str
    name: str
    options: Dict[str, Any] = field(default_factory=dict)
    #: Where each option was written, so an error can point at the line the
    #: user needs to change rather than at the block header.
    option_locations: Dict[str, Location] = field(default_factory=dict)


@dataclass
class Command(Node):
    """A one-line verb applied to a target: ``show code m1``, ``dryrun m1``."""

    verb: str
    target: Optional[str] = None
    arguments: List[Any] = field(default_factory=list)


@dataclass
class Program(Node):
    """A whole ``.econ`` file."""

    statements: List[Node] = field(default_factory=list)
    source: str = ""

    def of_type(self, kind: type) -> List[Node]:
        return [node for node in self.statements if isinstance(node, kind)]
