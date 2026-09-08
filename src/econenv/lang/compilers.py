"""Lowering the IR into each backend's own language.

Two rules from the specification shape this module.

**Native code must stay visible** (Unified Layer section 8, EconLang section 87).
``show code m1`` prints what will actually run, so these functions are the
single source of that text — the same call produces the code that is shown and
the code that is executed. A separate "pretty" version for display would be a
lie waiting to happen.

**No direct language-to-language translation** (section 2). Each compiler reads
the IR and nothing else; none of them knows another backend exists.

For Python and MATLAB the generated line is what EconEnv's engine layer already
runs under the hood, so the text is a faithful description rather than a
reconstruction. Where a backend needs several statements — EViews needs a
workfile and an equation object — all of them are shown.
"""

from __future__ import annotations

from typing import Dict, List

from .ir import ModelPlan

#: statsmodels' name for each covariance, so the shown code is runnable.
_SM_COV = {
    "hc0": "HC0",
    "hc1": "HC1",
    "hc2": "HC2",
    "hc3": "HC3",
}


def compile_for(plan: ModelPlan, engine: str) -> str:
    """The native code *engine* would run for *plan*."""
    try:
        compiler = COMPILERS[engine]
    except KeyError:  # pragma: no cover - guarded by the planner
        raise KeyError(f"no compiler for engine {engine!r}") from None
    return compiler(plan)


def _formula(plan: ModelPlan) -> str:
    right = " + ".join(plan.spec.exog) if plan.spec.exog else "1"
    if not plan.spec.constant:
        right += " - 1"
    return f"{plan.spec.depvar} ~ {right}"


def python_code(plan: ModelPlan) -> str:
    """statsmodels, written as the formula API a reader can run."""
    lines = ["import statsmodels.formula.api as smf", ""]
    call = f'model = smf.ols("{_formula(plan)}", data=data)'
    lines.append(call)

    fit_args: List[str] = []
    vcov = (plan.spec.vcov or "").lower()
    if vcov in _SM_COV:
        fit_args.append(f'cov_type="{_SM_COV[vcov]}"')
    elif vcov == "cluster":
        fit_args.append('cov_type="cluster"')
        fit_args.append(f'cov_kwds={{"groups": data["{plan.spec.cluster}"]}}')
    lines.append(f"result = model.fit({', '.join(fit_args)})")
    lines.append("print(result.summary())")
    return "\n".join(lines)


def r_code(plan: ModelPlan) -> str:
    """R's own lm, with sandwich only when a robust covariance was asked for."""
    lines = [f"fit <- lm({_formula(plan)}, data = data)"]
    vcov = (plan.spec.vcov or "").lower()
    if vcov in _SM_COV:
        lines = [
            "library(sandwich)",
            "library(lmtest)",
            "",
            lines[0],
            f'coeftest(fit, vcov = vcovHC(fit, type = "{_SM_COV[vcov]}"))',
        ]
    elif vcov == "cluster":
        lines = [
            "library(sandwich)",
            "library(lmtest)",
            "",
            lines[0],
            f"coeftest(fit, vcov = vcovCL(fit, cluster = data${plan.spec.cluster}))",
        ]
    else:
        lines.append("summary(fit)")
    return "\n".join(lines)


def stata_code(plan: ModelPlan) -> str:
    """Stata's regress. `noconstant` and `vce()` are options, not new commands."""
    parts = ["regress", plan.spec.depvar, *plan.spec.exog]
    options: List[str] = []
    if not plan.spec.constant:
        options.append("noconstant")

    vcov = (plan.spec.vcov or "").lower()
    if vcov in ("hc1", "hc0", "hc2", "hc3"):
        # Stata's vce(robust) is HC1 for OLS; the others are named directly.
        options.append("vce(robust)" if vcov == "hc1" else f"vce(hc{vcov[-1]})")
    elif vcov == "cluster":
        options.append(f"vce(cluster {plan.spec.cluster})")

    line = " ".join(parts)
    if options:
        line += ", " + " ".join(options)
    return line


def eviews_code(plan: ModelPlan) -> str:
    """EViews needs an equation object, and `c` is how a constant is written.

    EViews' ``cov=white`` is the HC1 form. Emitting it for a requested HC2 or
    HC3 would be a silent estimator substitution, which the specification
    forbids outright, so the difference is stated in the generated code rather
    than hidden inside it.
    """
    regressors = " ".join(plan.spec.exog)
    constant = "c " if plan.spec.constant else ""
    vcov = (plan.spec.vcov or "").lower()

    options = ""
    note = ""
    if vcov in ("hc0", "hc1"):
        options = "(cov=white)"
    elif vcov in ("hc2", "hc3"):
        options = "(cov=white)"
        note = (
            f"' note: {vcov.upper()} was requested. EViews' cov=white is the HC1 "
            "form,\n'       so these standard errors are not the same estimator.\n"
        )
    elif vcov == "cluster":
        options = f"(cov=cluster, clustervar={plan.spec.cluster})"

    return (
        f"{note}"
        f"equation {plan.name}.ls{options} {plan.spec.depvar} {constant}{regressors}\n"
        f"{plan.name}.output"
    )


def matlab_code(plan: ModelPlan) -> str:
    """fitlm takes the same formula, so the text stays close to the IR."""
    line = f"mdl = fitlm(data, '{_formula(plan)}');"
    if (plan.spec.vcov or "").lower() in _SM_COV:
        # fitlm has no robust covariance option; hac/CoefficientCovariance is a
        # separate step, and saying so is better than emitting code that ignores
        # what was asked for.
        return (
            line
            + "\ndisp(mdl)\n"
            + f"% note: {(plan.spec.vcov or '').upper()} is not an option on fitlm; "
            + "EconEnv applies it to the\n%       coefficient covariance after "
            + "the fit."
        )
    return line + "\ndisp(mdl)"


def gauss_code(plan: ModelPlan) -> str:
    """GAUSS builds the design matrix explicitly; `~` joins columns.

    A GAUSS matrix carries no column names, so the code refers to positions.
    EconEnv pushes exactly the model's columns, dependent variable first, which
    is what makes those positions predictable — the regressors therefore start
    at column 2, not column 1.
    """
    columns = " ~ ".join(f"data[.,{index + 2}]" for index in range(len(plan.spec.exog)))
    design = f"ones(rows(data),1) ~ {columns}" if plan.spec.constant else columns
    names = ", ".join(plan.spec.exog)
    lines = [
        "__output = 0;",
        "_olsres = 1;",
        f"y = data[.,1];                    /* {plan.spec.depvar} */",
        f"X = {design};" + f"    /* {names} */",
        '{ vnam, m, b, stb, vc, se, sig, cx, rsq, resid, dw } = ols("", y, X);',
        "print b';",
    ]
    if (plan.spec.vcov or "").lower() not in ("", "nonrobust"):
        lines.insert(
            0,
            f"/* note: GAUSS's ols reports classical standard errors; "
            f"{plan.spec.vcov} is not applied here. */",
        )
    return "\n".join(lines)


COMPILERS = {
    "python": python_code,
    "r": r_code,
    "stata": stata_code,
    "eviews": eviews_code,
    "matlab": matlab_code,
    "gauss": gauss_code,
}


def translate(plan: ModelPlan) -> Dict[str, str]:
    """The same model in every backend, from the same compilers.

    Section 24 is explicit that the translation view must not be a separate
    system: what it shows has to be what would run.
    """
    return {engine: compiler(plan) for engine, compiler in COMPILERS.items()}
