"""EconLang — writing econometrics instead of software syntax.

A high-level language in which a researcher states *what* to estimate, and
EconEnv decides how to say it to Python, R, Stata, EViews, MATLAB or GAUSS:

    project "inflation-study"

    data "macro.csv"

    set time:
        variable = year
        frequency = annual

    model ols baseline:
        y = gdp
        x = inflation, unemployment
        vcov = HC3

    show code baseline

The pipeline is the one the specification insists on, and each stage is a
module you can read on its own::

    source → lexer → parser → AST → lowering → Econometric IR
           → runtime → engine → unified ModelResult

The IR is the point. Backends never see EconLang syntax; they see a
:class:`~econenv.models.spec.ModelSpec`, which is the same neutral object
``compare_ols`` already hands to all six engines. That is what makes this a
runtime rather than a translator, and what makes adding a backend a lowering
rather than a rewrite.

This is the first vertical slice: data, a time declaration, OLS, and the
commands that make the generated code visible. It is deliberately narrow — the
architecture is meant to be proved before it spreads to more estimators.
"""

from __future__ import annotations

from typing import Optional

from .compilers import compile_for, translate
from .errors import CODES, Diagnostics, EconLangError, LangWarning, Location
from .ir import ModelPlan, ResearchProgram
from .lowering import lower
from .parser import parse
from .runtime import RunResult, Runtime

__all__ = [
    "CODES",
    "Diagnostics",
    "EconLangError",
    "LangWarning",
    "Location",
    "ModelPlan",
    "ResearchProgram",
    "RunResult",
    "Runtime",
    "compile_for",
    "lower",
    "parse",
    "run",
    "run_file",
    "translate",
]


def run(source: str, *, dry_run: bool = False) -> RunResult:
    """Parse, check and run an EconLang program.

    ``dry_run=True`` stops before touching data or an engine, and reports the
    interpretation and the generated code instead — which is what makes the
    language teachable.
    """
    diagnostics = Diagnostics()
    program = lower(parse(source), diagnostics)
    result = Runtime(dry_run=dry_run).run(program)
    result.diagnostics.warnings[:0] = diagnostics.warnings
    return result


def run_file(path, *, dry_run: bool = False) -> RunResult:
    """Run a ``.econ`` file."""
    import pathlib

    text = pathlib.Path(path).read_text(encoding="utf-8")
    return run(text, dry_run=dry_run)


def check(source: str) -> Optional[EconLangError]:
    """The first error in *source*, or None. Never raises."""
    try:
        lower(parse(source))
    except EconLangError as exc:
        return exc
    return None
