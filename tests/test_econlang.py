"""EconLang: the lexer, the parser, lowering, the compilers and the errors.

None of these need an engine beyond Python, which is always present. The point
they defend is the architecture: source becomes an AST, the AST becomes a
neutral IR, and only then does a backend see anything — so a backend never
sees EconLang syntax and adding one is a lowering rather than a rewrite.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from econenv import lang
from econenv.lang import EconLangError, compilers, lower, parse
from econenv.lang.lexer import Kind, tokenize
from econenv.lang.nodes import DataLoad, Model, Project, TimeDecl


@pytest.fixture
def dataset(tmp_path):
    """A small, deterministic file the programs below can load."""
    rng = np.random.default_rng(0)
    n = 60
    frame = pd.DataFrame(
        {
            "year": range(1960, 1960 + n),
            "inflation": rng.normal(size=n),
            "unemployment": rng.normal(size=n),
        }
    )
    frame["gdp"] = 2.0 + 1.5 * frame.inflation - 0.5 * frame.unemployment
    frame["gdp"] += rng.normal(scale=0.3, size=n)
    path = tmp_path / "macro.csv"
    frame.to_csv(path, index=False)
    return path, frame


def program_for(path, body: str) -> str:
    return f'data "{path.as_posix()}"\n\n{body}'


# --------------------------------------------------------------------------- #
# lexer
# --------------------------------------------------------------------------- #
class TestLexer:
    def test_indentation_becomes_indent_and_dedent(self):
        kinds = [t.kind for t in tokenize("model ols m:\n    y = gdp\n")]
        assert Kind.INDENT in kinds
        assert Kind.DEDENT in kinds

    def test_a_blank_line_does_not_close_a_block(self):
        """Otherwise a stray empty line in the middle of a model ends it."""
        tokens = tokenize("model ols m:\n    y = gdp\n\n    x = a\n")
        assert sum(1 for t in tokens if t.kind is Kind.DEDENT) == 1

    def test_a_comment_line_does_not_close_a_block(self):
        tokens = tokenize("model ols m:\n    y = gdp\n# a note\n    x = a\n")
        assert sum(1 for t in tokens if t.kind is Kind.DEDENT) == 1

    def test_a_tab_is_refused_rather_than_guessed_at(self):
        """A tab means a different width in every editor."""
        with pytest.raises(EconLangError) as caught:
            parse("model ols m:\n\ty = gdp\n")
        assert caught.value.code == "E204"
        assert "tabs" in str(caught.value)

    def test_an_unterminated_string_is_caught(self):
        with pytest.raises(EconLangError) as caught:
            parse('data "macro.csv\n')
        assert caught.value.code == "E205"

    def test_a_trailing_comment_is_ignored(self):
        tokens = tokenize('data "x.csv"   # load it\n')
        assert [t.text for t in tokens if t.kind is Kind.STRING] == ["x.csv"]


# --------------------------------------------------------------------------- #
# parser
# --------------------------------------------------------------------------- #
class TestParser:
    def test_a_whole_program(self):
        program = parse(
            'project "study"\n'
            "\n"
            'data "macro.csv"\n'
            "\n"
            "set time:\n"
            "    variable = year\n"
            "    frequency = annual\n"
            "\n"
            "model ols baseline:\n"
            "    y = gdp\n"
            "    x = inflation, unemployment\n"
        )
        kinds = [type(node) for node in program.statements]
        assert kinds == [Project, DataLoad, TimeDecl, Model]

    def test_a_list_option_becomes_a_list(self):
        model = parse("model ols m:\n    y = gdp\n    x = a, b, c\n").statements[0]
        assert model.options["x"] == ["a", "b", "c"]

    def test_one_regressor_is_not_wrapped_in_a_list(self):
        model = parse("model ols m:\n    y = gdp\n    x = a\n").statements[0]
        assert model.options["x"] == "a"

    @pytest.mark.parametrize("word, expected", [("yes", True), ("no", False), ("on", True)])
    def test_yes_and_no_read_as_booleans(self, word, expected):
        """A researcher writes `intercept = yes`, not `intercept = True`."""
        model = parse(f"model ols m:\n    y = a\n    x = b\n    intercept = {word}\n").statements[0]
        assert model.options["intercept"] is expected

    def test_each_option_remembers_where_it_was_written(self):
        """So an error points at the option, not at the block header."""
        model = parse("model ols m:\n    y = gdp\n    x = a\n").statements[0]
        assert model.option_locations["y"].line == 2
        assert model.option_locations["x"].line == 3

    def test_an_empty_block_is_refused(self):
        with pytest.raises(EconLangError) as caught:
            parse("model ols m:\n")
        assert caught.value.code == "E203"

    def test_a_repeated_option_is_refused(self):
        with pytest.raises(EconLangError) as caught:
            parse("model ols m:\n    y = a\n    y = b\n")
        assert caught.value.code == "E302"


# --------------------------------------------------------------------------- #
# lowering: syntax to meaning
# --------------------------------------------------------------------------- #
class TestLowering:
    def test_a_model_becomes_a_modelspec(self):
        """The IR reuses the object compare_ols already gives every engine."""
        program = lower(parse("model ols m:\n    y = gdp\n    x = a, b\n"))
        spec = program.models["m"].spec
        assert spec.depvar == "gdp"
        assert spec.exog == ["a", "b"]
        assert spec.constant is True

    def test_intercept_no_drops_the_constant(self):
        program = lower(parse("model ols m:\n    y = y\n    x = a\n    intercept = no\n"))
        assert program.models["m"].spec.constant is False

    def test_robust_is_named_explicitly_rather_than_left_ambiguous(self):
        """statsmodels, Stata and R all mean HC1 by "robust" for OLS."""
        program = lower(parse("model ols m:\n    y = y\n    x = a\n    vcov = robust\n"))
        assert program.models["m"].spec.vcov == "hc1"

    def test_nonrobust_is_the_absence_of_a_covariance_choice(self):
        program = lower(parse("model ols m:\n    y = y\n    x = a\n    vcov = nonrobust\n"))
        assert program.models["m"].spec.vcov is None

    @pytest.mark.parametrize(
        "body, code",
        [
            ("model ols m:\n    y = y\n    x = y\n", "E407"),
            ("model ols m:\n    y = y\n    x = a, a\n", "E402"),
            ("model ols m:\n    x = a\n", "E304"),
            ("model ols m:\n    y = y\n    x = a\n    nope = 1\n", "E302"),
            ("model ols m:\n    y = y\n    x = a\n    vcov = weird\n", "E302"),
            ("model logit m:\n    y = y\n    x = a\n", "E701"),
            ("model ols m:\n    y = y\n    x = a\n\nmodel ols m:\n    y = y\n    x = b\n", "E303"),
            ("show code nope\n", "E301"),
        ],
    )
    def test_each_mistake_gets_its_own_code(self, body, code):
        with pytest.raises(EconLangError) as caught:
            lower(parse(body))
        assert caught.value.code == code

    def test_an_unimplemented_estimator_is_a_capability_error_not_a_syntax_one(self):
        """The word is fine; EconLang just does not implement it yet."""
        with pytest.raises(EconLangError) as caught:
            lower(parse("model garch m:\n    y = y\n    x = a\n"))
        assert caught.value.code == "E701"
        assert "ols" in caught.value.available

    def test_a_cluster_variable_without_cluster_covariance_warns(self):
        from econenv.lang.errors import Diagnostics

        diagnostics = Diagnostics()
        lower(
            parse("model ols m:\n    y = y\n    x = a\n    cluster = country\n"),
            diagnostics,
        )
        assert any("cluster" in w.message for w in diagnostics)


# --------------------------------------------------------------------------- #
# compilers: the generated code has to be the code that runs
# --------------------------------------------------------------------------- #
class TestCompilers:
    @pytest.fixture
    def plan(self):
        return lower(parse("model ols m:\n    y = gdp\n    x = a, b\n")).models["m"]

    def test_every_backend_generates_something(self, plan):
        code = compilers.translate(plan)
        assert set(code) == {"python", "r", "stata", "eviews", "matlab", "gauss"}
        assert all(text.strip() for text in code.values())

    def test_stata(self, plan):
        assert compilers.stata_code(plan) == "regress gdp a b"

    def test_r(self, plan):
        assert "lm(gdp ~ a + b, data = data)" in compilers.r_code(plan)

    def test_python(self, plan):
        assert 'smf.ols("gdp ~ a + b", data=data)' in compilers.python_code(plan)

    def test_eviews_writes_the_constant_as_c(self, plan):
        assert "gdp c a b" in compilers.eviews_code(plan)

    def test_no_constant_shows_in_every_backend(self):
        plan = lower(parse("model ols m:\n    y = gdp\n    x = a\n    intercept = no\n")).models[
            "m"
        ]
        assert "noconstant" in compilers.stata_code(plan)
        assert "- 1" in compilers.r_code(plan)
        assert " c " not in compilers.eviews_code(plan)

    def test_gauss_indexes_the_regressors_after_the_dependent_variable(self):
        """The design matrix must not reuse column 1 for y and the first x."""
        plan = lower(parse("model ols m:\n    y = gdp\n    x = a, b\n")).models["m"]
        code = compilers.gauss_code(plan)
        assert "y = data[.,1]" in code
        assert "data[.,2] ~ data[.,3]" in code
        assert "data[.,1] ~" not in code

    def test_eviews_says_when_its_robust_form_is_a_different_estimator(self):
        """cov=white is HC1; emitting it for HC3 would be a silent substitution."""
        plan = lower(parse("model ols m:\n    y = gdp\n    x = a\n    vcov = HC3\n")).models["m"]
        code = compilers.eviews_code(plan)
        assert "cov=white" in code
        assert "not the same estimator" in code

    def test_a_robust_request_reaches_statsmodels(self):
        plan = lower(parse("model ols m:\n    y = gdp\n    x = a\n    vcov = HC3\n")).models["m"]
        assert 'cov_type="HC3"' in compilers.python_code(plan)


# --------------------------------------------------------------------------- #
# running
# --------------------------------------------------------------------------- #
class TestRun:
    def test_a_program_estimates_and_matches_statsmodels(self, dataset):
        path, frame = dataset
        result = lang.run(
            program_for(path, "model ols m:\n    y = gdp\n    x = inflation, unemployment\n")
        )
        import statsmodels.api as sm

        reference = sm.OLS(
            frame["gdp"], sm.add_constant(frame[["inflation", "unemployment"]])
        ).fit()
        ours = result.models["m"].coefficients["coef"].to_numpy()
        np.testing.assert_allclose(ours, reference.params.to_numpy(), rtol=1e-12)

    def test_a_dry_run_touches_neither_data_nor_engine(self, tmp_path):
        """It must work even when the file does not exist."""
        result = lang.run(
            'data "nowhere.csv"\n\nmodel ols m:\n    y = gdp\n    x = a\n\ndryrun m\n',
            dry_run=True,
        )
        assert result.models == {}
        assert "regress" not in str(result)
        assert "smf.ols" in str(result)

    def test_show_code_prints_what_would_run(self, dataset):
        path, _ = dataset
        result = lang.run(
            program_for(path, "model ols m:\n    y = gdp\n    x = inflation\n\nshow code m\n")
        )
        assert 'smf.ols("gdp ~ inflation", data=data)' in str(result)

    def test_explain_describes_the_model_in_words(self, dataset):
        path, _ = dataset
        result = lang.run(
            program_for(path, "model ols m:\n    y = gdp\n    x = inflation\n\nexplain m\n")
        )
        text = str(result)
        assert "gdp ~ inflation" in text
        assert "estimator" in text

    def test_a_missing_variable_names_the_line_and_the_near_miss(self, dataset):
        path, _ = dataset
        with pytest.raises(EconLangError) as caught:
            lang.run(program_for(path, "model ols m:\n    y = GDP\n    x = inflation\n"))
        error = caught.value
        assert error.code == "E101"
        assert "gdp" in error.did_you_mean
        assert error.location.line == 4, "point at the option, not the block header"
        assert error.fix == "y = gdp"

    def test_a_duplicate_time_index_is_refused_and_suggests_a_panel(self, tmp_path):
        path = tmp_path / "d.csv"
        pd.DataFrame({"year": [2000, 2000, 2001], "y": [1.0, 2.0, 3.0]}).to_csv(path, index=False)
        with pytest.raises(EconLangError) as caught:
            lang.run(f'data "{path.as_posix()}"\n\nset time:\n    variable = year\n')
        assert caught.value.code == "E103"
        assert "panel" in str(caught.value)

    def test_too_few_observations_is_caught_before_the_engine(self, tmp_path):
        path = tmp_path / "tiny.csv"
        pd.DataFrame({"y": [1.0, 2.0], "a": [1.0, 2.0], "b": [3.0, 1.0]}).to_csv(path, index=False)
        with pytest.raises(EconLangError) as caught:
            lang.run(f'data "{path.as_posix()}"\n\nmodel ols m:\n    y = y\n    x = a, b\n')
        assert caught.value.code == "E401"

    def test_dropped_rows_are_reported_rather_than_passed_over(self, tmp_path):
        path = tmp_path / "gaps.csv"
        frame = pd.DataFrame({"y": [1.0, 2.0, None, 4.0] * 6, "a": range(24)})
        frame.to_csv(path, index=False)
        result = lang.run(f'data "{path.as_posix()}"\n\nmodel ols m:\n    y = y\n    x = a\n')
        assert any("dropped" in w.message for w in result.diagnostics)

    def test_a_file_that_is_not_there_suggests_a_near_name(self, tmp_path):
        (tmp_path / "macro.csv").write_text("y,a\n1,2\n", encoding="utf-8")
        with pytest.raises(EconLangError) as caught:
            lang.run(f'data "{(tmp_path / "macros.csv").as_posix()}"\n')
        assert caught.value.code == "E106"
        assert "macro.csv" in caught.value.did_you_mean

    def test_an_unknown_engine_is_refused_by_name(self, dataset):
        path, _ = dataset
        with pytest.raises(EconLangError) as caught:
            lang.run(
                program_for(
                    path, "model ols m:\n    y = gdp\n    x = inflation\n    engine = sas\n"
                )
            )
        assert caught.value.code == "E501"
        assert "python" in caught.value.available

    def test_check_returns_the_error_instead_of_raising(self):
        assert lang.check("model ols m:\n    y = a\n    x = b\n") is None
        assert lang.check("model nope m:\n    y = a\n    x = b\n").code == "E701"


class TestBackwardCompatibility:
    """Section 44: the language is additive and breaks nothing."""

    def test_the_native_magics_are_still_registered(self):
        """Loading the extension must still register every native magic."""
        import contextlib
        import io

        from IPython.testing.globalipapp import start_ipython

        shell = start_ipython()
        with contextlib.redirect_stdout(io.StringIO()):
            shell.run_line_magic("load_ext", "econenv")

        from econenv.magics import REGISTRATION

        for name in ("%econ", "%eviews / %%eviews", "%matlab / %%matlab", "%%econlang"):
            assert name in REGISTRATION, f"{name} is no longer registered"

    def test_the_language_reuses_modelspec_rather_than_a_parallel_schema(self):
        from econenv.models.spec import ModelSpec

        plan = lower(parse("model ols m:\n    y = y\n    x = a\n")).models["m"]
        assert isinstance(plan.spec, ModelSpec)

    def test_an_estimated_model_is_an_ordinary_modelresult(self, dataset):
        from econenv.results import ModelResult

        path, _ = dataset
        result = lang.run(program_for(path, "model ols m:\n    y = gdp\n    x = inflation\n"))
        assert isinstance(result.models["m"], ModelResult)
