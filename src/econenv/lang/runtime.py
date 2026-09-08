"""Running an EconLang program.

This is the layer that loads the data, checks the model against it, hands the
neutral :class:`ModelSpec` to an engine, and collects the results. It is
deliberately thin: the estimation itself is EconEnv's existing engine layer,
which already fits OLS in six programs and agrees with itself to machine
precision. Re-implementing any of that here would create a second answer to the
same question.

The econometric checks that need data live here rather than in lowering, so
``dryrun`` can report everything checkable without opening a file.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from ..engines import registry as engine_registry
from ..results import ModelResult
from .compilers import compile_for, translate
from .errors import Diagnostics, EconLangError, suggest, variable_not_found
from .ir import Action, ModelPlan, ResearchProgram, TimeStructure

#: Extensions the language loads today, and how.
READERS = {
    ".csv": lambda path, **kw: pd.read_csv(path, **kw),
    ".tsv": lambda path, **kw: pd.read_csv(path, sep="\t", **kw),
    ".xlsx": lambda path, **kw: pd.read_excel(path, **kw),
    ".xls": lambda path, **kw: pd.read_excel(path, **kw),
    ".parquet": lambda path, **kw: pd.read_parquet(path, **kw),
    ".dta": lambda path, **kw: pd.read_stata(path, **kw),
    ".json": lambda path, **kw: pd.read_json(path, **kw),
}

#: The smallest sample that can identify a model at all.
_MIN_PER_PARAMETER = 1


@dataclass
class RunResult:
    """Everything one program produced."""

    program: ResearchProgram
    data: Optional[pd.DataFrame] = None
    models: Dict[str, ModelResult] = field(default_factory=dict)
    code: Dict[str, str] = field(default_factory=dict)
    output: List[str] = field(default_factory=list)
    diagnostics: Diagnostics = field(default_factory=Diagnostics)
    elapsed: float = 0.0

    def say(self, text: str = "") -> None:
        self.output.append(text)

    def __str__(self) -> str:
        return "\n".join(self.output)

    def _repr_html_(self) -> str:
        from html import escape

        return f"<pre style='white-space:pre-wrap'>{escape(str(self))}</pre>"


class Runtime:
    """Executes a lowered program."""

    def __init__(self, *, dry_run: bool = False) -> None:
        self.dry_run = dry_run

    # ------------------------------------------------------------------ #
    def run(self, program: ResearchProgram) -> RunResult:
        started = time.time()
        result = RunResult(program=program)

        if program.project:
            result.say(f"project: {program.project}")

        data = None if self.dry_run else self._load(program, result)
        result.data = data

        for name, plan in program.models.items():
            self._check_against_data(plan, data, result)
            result.code[name] = compile_for(plan, self._engine_for(plan, result))
            if not self.dry_run and data is not None:
                result.models[name] = self._estimate(plan, data, result)

        for action in program.actions:
            self._act(action, program, result)

        result.elapsed = time.time() - started
        return result

    # ------------------------------------------------------------------ #
    # data
    # ------------------------------------------------------------------ #
    def _load(self, program: ResearchProgram, result: RunResult) -> pd.DataFrame:
        if program.data is None:
            raise EconLangError(
                "E102",
                "No dataset has been loaded.",
                example='data "macro.csv"',
            )

        path = Path(program.data.path)
        if not path.exists():
            near = []
            if path.parent.exists():
                near = suggest(path.name, [p.name for p in path.parent.iterdir() if p.is_file()])
            raise EconLangError(
                "E106",
                f"{program.data.path!r} does not exist.",
                location=program.data.location,
                did_you_mean=near,
                cause=f"Looked in {path.parent.resolve()}",
            )

        reader = READERS.get(path.suffix.lower())
        if reader is None:
            raise EconLangError(
                "E107",
                f"EconLang cannot read a {path.suffix!r} file yet.",
                location=program.data.location,
                available=sorted(READERS),
            )

        options = dict(program.data.options)
        kwargs: Dict[str, Any] = {}
        if "sheet" in options:
            kwargs["sheet_name"] = options.pop("sheet")
        if "missing" in options:
            values = options.pop("missing")
            kwargs["na_values"] = values if isinstance(values, list) else [values]
        if "header" in options:
            kwargs["header"] = 0 if options.pop("header") else None

        try:
            frame = pd.DataFrame(reader(path, **kwargs))
        except Exception as exc:
            raise EconLangError(
                "E104",
                f"{path.name} could not be read: {exc}",
                location=program.data.location,
                raw=exc,
            ) from exc

        result.say(f"data: {path.name} — {len(frame):,} rows, {len(frame.columns)} columns")
        if program.time is not None:
            self._check_time(program.time, frame, result)
        return frame

    def _check_time(self, structure: TimeStructure, frame: pd.DataFrame, result: RunResult) -> None:
        """The checks section 12 asks for: duplicates, gaps, ordering."""
        variable = structure.variable
        if variable not in frame.columns:
            raise variable_not_found(variable, list(frame.columns), structure.location)

        column = frame[variable]
        if column.duplicated().any():
            repeated = column[column.duplicated()].unique()[:5]
            raise EconLangError(
                "E103",
                f"{variable!r} repeats: {', '.join(str(v) for v in repeated)}",
                location=structure.location,
                cause="A time index has to identify an observation uniquely. If this "
                "is panel data, declare it as a panel instead.",
                example="set panel:\n    id = country\n    time = year",
            )
        if not column.is_monotonic_increasing:
            result.diagnostics.warn(
                "W109",
                f"{variable!r} is not sorted; observations will be used in file order",
                location=structure.location,
                fix=f"sort the file by {variable}, or EconEnv will not reorder it for you",
            )
        numeric = pd.to_numeric(column, errors="coerce")
        if numeric.notna().all():
            steps = numeric.diff().dropna().unique()
            if len(steps) > 1:
                result.diagnostics.warn(
                    "W108",
                    f"{variable!r} has gaps or an uneven step ({len(steps)} different gaps)",
                    location=structure.location,
                )

    # ------------------------------------------------------------------ #
    # models
    # ------------------------------------------------------------------ #
    def _check_against_data(
        self, plan: ModelPlan, data: Optional[pd.DataFrame], result: RunResult
    ) -> None:
        if data is None:
            return
        columns = list(data.columns)
        if plan.spec.depvar not in columns:
            raise variable_not_found(plan.spec.depvar, columns, plan.where("y"))
        for name in plan.spec.exog:
            if name not in columns:
                raise variable_not_found(name, columns, plan.where("x"))
        for option, extra in (("cluster", plan.spec.cluster), ("weights", plan.spec.weights)):
            if extra and extra not in columns:
                raise variable_not_found(extra, columns, plan.where(option))

        used = data[[plan.spec.depvar, *plan.spec.exog]].dropna()
        parameters = len(plan.spec.exog) + (1 if plan.spec.constant else 0)
        if len(used) <= parameters * _MIN_PER_PARAMETER:
            raise EconLangError(
                "E401",
                f"{len(used)} usable observations for {parameters} parameters.",
                location=plan.location,
                cause="After dropping rows with missing values there is not enough "
                "data to identify the model.",
            )
        dropped = len(data) - len(used)
        if dropped:
            result.diagnostics.warn(
                "W105",
                f"{plan.name}: {dropped} row(s) dropped for missing values ({len(used)} used)",
                location=plan.location,
            )

    def _engine_for(self, plan: ModelPlan, result: RunResult) -> str:
        """Which backend runs this model, refusing to substitute silently."""
        wanted = plan.engine.lower()
        if wanted == "auto":
            return self._auto(plan, result)

        try:
            engine = engine_registry.get(wanted)
        except Exception:
            raise EconLangError(
                "E501",
                f"{wanted!r} is not an engine EconEnv knows.",
                location=plan.where("engine"),
                did_you_mean=suggest(wanted, engine_registry.names()),
                available=engine_registry.names(),
            ) from None

        if not engine.available:
            raise EconLangError(
                "E501",
                f"{engine.display_name} is not available on this machine.",
                location=plan.where("engine"),
                cause=getattr(engine, "_detect_error", None),
                fix="Run `%econ doctor` to see what is missing, or choose another "
                "engine:  engine = python",
            )
        return wanted

    def _auto(self, plan: ModelPlan, result: RunResult) -> str:
        """Pick an available engine, and say why (section 12 of the layer spec).

        The order is stated rather than clever. Python first because it is
        always present and needs no licence; the rest follow so the choice is
        reproducible on another machine.
        """
        order = ["python", "r", "stata", "matlab", "eviews", "gauss"]
        for name in order:
            try:
                engine = engine_registry.get(name)
            except Exception:
                continue
            if engine.available:
                others = [other for other in order if other != name and _is_available(other)]
                result.say(
                    f"engine: {name} (auto)\n"
                    f"  chosen because it is first in the stated preference order "
                    f"and is available here.\n"
                    f"  also available: {', '.join(others) if others else 'none'}"
                )
                return name
        raise EconLangError(
            "E501",
            "No engine is available on this machine.",
            location=plan.location,
        )

    def _estimate(self, plan: ModelPlan, data: pd.DataFrame, result: RunResult) -> ModelResult:
        engine_name = self._engine_for(plan, result)
        engine = engine_registry.get(engine_name)
        try:
            model = engine._fit_ols(plan.spec, data)
        except EconLangError:
            raise
        except Exception as exc:
            raise EconLangError(
                "E602",
                f"{engine.display_name} could not estimate {plan.name!r}: {exc}",
                location=plan.location,
                raw=exc,
            ) from exc
        return model

    # ------------------------------------------------------------------ #
    # actions
    # ------------------------------------------------------------------ #
    def _act(self, action: Action, program: ResearchProgram, result: RunResult) -> None:
        verb = action.verb
        if action.target is None:
            return
        target = action.target
        plan = program.models[target]

        if verb in ("show code", "showcode"):
            engine = self._engine_for(plan, result)
            result.say("")
            result.say(f"# {target} — generated {engine} code")
            result.say(result.code.get(target, compile_for(plan, engine)))
        elif verb == "translate":
            result.say("")
            result.say(f"# {target} — the same model in every backend")
            for engine, code in translate(plan).items():
                result.say("")
                result.say(f"## {engine}")
                result.say(code)
        elif verb == "explain":
            result.say("")
            result.say(self._explain(plan, result))
        elif verb in ("summary", "show"):
            model = result.models.get(target)
            result.say("")
            result.say(str(model) if model is not None else "(not estimated)")
        elif verb == "export":
            self._export(action, result)
        elif verb == "dryrun":
            result.say("")
            result.say(self._dry_run_report(plan, result))

    def _explain(self, plan: ModelPlan, result: RunResult) -> str:
        """What section 88 asks for: the model in words, not syntax."""
        lines = [f"# {plan.name}", ""]
        lines.append(f"  estimator   : {plan.estimator.upper()}")
        lines.append(f"  specification: {plan.described()}")
        lines.append(f"  dependent   : {plan.spec.depvar}")
        lines.append(f"  regressors  : {', '.join(plan.spec.exog) or '(none)'}")
        lines.append(f"  intercept   : {'yes' if plan.spec.constant else 'no'}")
        lines.append(f"  covariance  : {plan.spec.vcov or 'nonrobust'}")
        if plan.spec.cluster:
            lines.append(f"  clustered on: {plan.spec.cluster}")
        lines.append(f"  engine      : {plan.engine}")
        model = result.models.get(plan.name)
        if model is not None:
            lines.append(f"  observations: {model.nobs}")
        return "\n".join(lines)

    def _dry_run_report(self, plan: ModelPlan, result: RunResult) -> str:
        engine = self._engine_for(plan, result)
        lines = [f"# dry run — {plan.name}", "", "  nothing was estimated.", ""]
        lines.append(f"  interpretation : {plan.described()}")
        lines.append(f"  engine         : {engine}")
        lines.append("")
        lines.append(f"  generated {engine} code:")
        for line in compile_for(plan, engine).splitlines():
            lines.append(f"    {line}")
        return "\n".join(lines)

    def _export(self, action: Action, result: RunResult) -> None:
        model = result.models.get(action.target or "")
        if model is None:
            result.say(f"(nothing to export for {action.target!r})")
            return
        if not action.arguments:
            raise EconLangError(
                "E801",
                "`export` needs a destination.",
                location=action.location,
                example='export m1 "results/table1.tex"',
            )
        from ..export import export as _export

        written = _export(model, str(action.arguments[0]))
        result.say("")
        result.say(str(written))


def _is_available(name: str) -> bool:
    try:
        return engine_registry.get(name).available
    except Exception:
        return False
