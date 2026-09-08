"""AST to Econometric IR, with the semantic checks that belong on the way.

Two kinds of checking happen here and they are worth telling apart:

* **semantic** — is the program well formed? Is a model named twice, is a
  command aimed at a model that does not exist, is an option a word this
  estimator understands? These need no data.
* **econometric** — do the variables exist, are there enough observations, is a
  regressor also the dependent variable? These need the data, so they run in
  the runtime once it is loaded.

Splitting them means `dryrun` can report everything checkable without touching
a file, which is what makes it useful for teaching.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..models.spec import ModelSpec
from .errors import Diagnostics, EconLangError, suggest
from .ir import Action, DataSource, ModelPlan, PanelStructure, ResearchProgram, TimeStructure
from .nodes import Command, DataLoad, Model, PanelDecl, Program, Project, Setting, TimeDecl

#: Options `model ols` understands, and what each means in the IR.
OLS_OPTIONS = {
    "y": "the dependent variable",
    "x": "the regressors, comma separated",
    "intercept": "yes or no; yes by default",
    "vcov": "nonrobust, HC0, HC1, HC2, HC3, or cluster",
    "cluster": "a variable to cluster standard errors on",
    "weights": "a variable of observation weights",
    "missing": "listwise (the default)",
    "engine": "which backend estimates this model",
    "sample": "a subset expression, applied before estimation",
}

#: Estimators the language accepts today. Anything else is a capability error
#: naming these, rather than a syntax error, because the word itself is fine.
ESTIMATORS = {"ols"}

#: Covariance names accepted, lowercase-insensitively.
VCOV = {"nonrobust", "hc0", "hc1", "hc2", "hc3", "cluster", "robust"}

#: Settings a project may carry at the top level.
SETTINGS = {"backend", "engine", "seed", "theme", "language", "strict", "verbosity"}


def lower(program: Program, diagnostics: Optional[Diagnostics] = None) -> ResearchProgram:
    """Lower a parsed program into the IR, checking what can be checked."""
    diagnostics = diagnostics if diagnostics is not None else Diagnostics()
    out = ResearchProgram(source=program.source)

    for node in program.statements:
        if isinstance(node, Project):
            out.project = node.name
        elif isinstance(node, Setting):
            _setting(node, out, diagnostics)
        elif isinstance(node, DataLoad):
            _data(node, out, diagnostics)
        elif isinstance(node, TimeDecl):
            out.time = TimeStructure(node.variable, node.frequency, node.location)
        elif isinstance(node, PanelDecl):
            out.panel = PanelStructure(node.entity, node.time, node.location)
        elif isinstance(node, Model):
            _model(node, out, diagnostics)
        elif isinstance(node, Command):
            out.actions.append(Action(node.verb, node.target, list(node.arguments), node.location))

    _check_actions(out)
    return out


def _setting(node: Setting, out: ResearchProgram, diagnostics: Diagnostics) -> None:
    key = node.key.lower()
    if key not in SETTINGS:
        near = suggest(key, sorted(SETTINGS))
        raise EconLangError(
            "E302",
            f"{node.key!r} is not a project setting.",
            location=node.location,
            did_you_mean=near,
            available=sorted(SETTINGS),
        )
    # `engine` and `backend` are the same idea; accept both and store one.
    out.settings["backend" if key == "engine" else key] = node.value


def _data(node: DataLoad, out: ResearchProgram, diagnostics: Diagnostics) -> None:
    if out.data is not None:
        diagnostics.warn(
            "W101",
            f"a second dataset replaces {out.data.path!r}",
            location=node.location,
        )
    out.data = DataSource(node.path, dict(node.options), node.location)


def _at(node: Model, option: str):
    """Where *option* was written, falling back to the model header."""
    return node.option_locations.get(option, node.location)


def _model(node: Model, out: ResearchProgram, diagnostics: Diagnostics) -> None:
    if node.name in out.models:
        raise EconLangError(
            "E303",
            f"A model named {node.name!r} is already defined.",
            location=node.location,
            fix=f"Give this one a different name, for example {node.name}_2.",
        )

    if node.estimator not in ESTIMATORS:
        raise EconLangError(
            "E701",
            f"{node.estimator!r} is not an estimator EconLang implements yet.",
            location=node.location,
            available=sorted(ESTIMATORS),
            cause="The language is being built one estimator at a time, starting "
            "with OLS, so that the architecture is proven before it spreads.",
            fix=f"model ols {node.name}:",
        )

    unknown = [key for key in node.options if key not in OLS_OPTIONS]
    if unknown:
        first = unknown[0]
        raise EconLangError(
            "E302",
            f"{first!r} is not an option for `model ols`.",
            location=_at(node, first),
            did_you_mean=suggest(first, sorted(OLS_OPTIONS)),
            available=[f"{name} — {what}" for name, what in sorted(OLS_OPTIONS.items())],
        )

    for required in ("y", "x"):
        if required not in node.options:
            raise EconLangError(
                "E304",
                f"`model ols` needs `{required}`.",
                location=node.location,
                example="model ols m1:\n    y = gdp\n    x = inflation, unemployment",
            )

    depvar = _one_name(node.options["y"], "y", node)
    exog = _name_list(node.options["x"], "x", node)

    if depvar in exog:
        raise EconLangError(
            "E407",
            f"{depvar!r} is both the dependent variable and a regressor.",
            location=_at(node, "x"),
            cause="Regressing a variable on itself gives a perfect fit that means nothing.",
            fix=f"Remove {depvar} from the x list.",
        )

    duplicates = sorted({name for name in exog if exog.count(name) > 1})
    if duplicates:
        raise EconLangError(
            "E402",
            f"{duplicates[0]!r} appears twice in the regressor list.",
            location=_at(node, "x"),
            cause="Two identical columns are perfectly collinear, so the model "
            "cannot be estimated.",
        )

    vcov = node.options.get("vcov")
    if vcov is not None and str(vcov).lower() not in VCOV:
        raise EconLangError(
            "E302",
            f"{vcov!r} is not a covariance estimator EconLang knows.",
            location=_at(node, "vcov"),
            did_you_mean=suggest(str(vcov), sorted(VCOV)),
            available=sorted(VCOV),
        )

    cluster = node.options.get("cluster")
    if str(vcov).lower() == "cluster" and not cluster:
        raise EconLangError(
            "E304",
            "`vcov = cluster` needs a `cluster` variable.",
            location=_at(node, "vcov"),
            example="model ols m1:\n    y = gdp\n    x = inflation\n"
            "    vcov = cluster\n    cluster = country",
        )
    if cluster and str(vcov).lower() != "cluster":
        diagnostics.warn(
            "W302",
            f"`cluster = {cluster}` is ignored unless `vcov = cluster` is also set",
            location=node.location,
            fix="add:  vcov = cluster",
        )

    spec = ModelSpec(
        depvar=depvar,
        exog=exog,
        constant=bool(node.options.get("intercept", True)),
        vcov=_vcov_for_spec(vcov),
        weights=_optional_name(node.options.get("weights")),
        cluster=_optional_name(cluster),
    )
    out.models[node.name] = ModelPlan(
        name=node.name,
        estimator=node.estimator,
        spec=spec,
        option_locations=dict(node.option_locations),
        engine=str(node.options.get("engine", out.default_engine)),
        options=dict(node.options),
        location=node.location,
    )


def _check_actions(out: ResearchProgram) -> None:
    """Every command must name a model that exists."""
    for action in out.actions:
        if action.verb in ("doctor", "summary") and action.target is None:
            continue
        if action.target is None:
            raise EconLangError(
                "E301",
                f"`{action.verb}` needs to say which model.",
                location=action.location,
                available=sorted(out.models),
            )
        if action.target not in out.models:
            raise EconLangError(
                "E301",
                f"No model named {action.target!r} has been defined.",
                location=action.location,
                did_you_mean=suggest(action.target, sorted(out.models)),
                available=sorted(out.models),
            )


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def _one_name(value: Any, option: str, node: Model) -> str:
    if isinstance(value, list):
        raise EconLangError(
            "E302",
            f"`{option}` takes one variable, not a list.",
            location=node.location,
            fix=f"{option} = {value[0]}",
        )
    return str(value)


def _name_list(value: Any, option: str, node: Model) -> List[str]:
    items = value if isinstance(value, list) else [value]
    return [str(item) for item in items]


def _optional_name(value: Any) -> Optional[str]:
    return None if value in (None, "", False) else str(value)


def _vcov_for_spec(vcov: Any) -> Optional[str]:
    """The covariance name in the form the engines already expect."""
    if vcov is None:
        return None
    text = str(vcov).lower()
    if text == "nonrobust":
        return None
    if text == "robust":
        # statsmodels, Stata and R all mean HC1 by "robust" for OLS, so naming
        # it explicitly avoids three engines quietly meaning three things.
        return "hc1"
    return text


def describe_options() -> Dict[str, str]:
    """The option table, for help output."""
    return dict(OLS_OPTIONS)
