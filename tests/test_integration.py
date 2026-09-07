"""Integration tests. Each needs a real, licensed engine and is skipped without it.

Run everything that needs no licence with::

    pytest -m "not stata and not eviews"

Run the full suite on a machine that has all three::

    pytest
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import econenv
from econenv.models.spec import ModelSpec

RTOL = 1e-9


# --------------------------------------------------------------------------- #
# R
# --------------------------------------------------------------------------- #
@pytest.mark.r
class TestR:
    def test_executes_and_captures_output(self, r_engine):
        assert "hello" in r_engine.execute('cat("hello")').stdout

    def test_session_is_persistent(self, r_engine):
        r_engine.execute("econenv_marker <- 123")
        assert "123" in r_engine.execute("cat(econenv_marker)").stdout

    def test_warnings_are_reported_separately(self, r_engine):
        result = r_engine.execute('warning("mind out"); cat("body")')
        assert result.warnings == ["mind out"]
        assert result.stdout.strip() == "body"

    def test_errors_raise_with_r_s_own_message(self, r_engine):
        from econenv.exceptions import EngineExecutionError

        with pytest.raises(EngineExecutionError, match="deliberate"):
            r_engine.execute('stop("deliberate")')

    def test_session_survives_an_error(self, r_engine):
        from econenv.exceptions import EngineExecutionError

        r_engine.execute("survivor <- 1")
        with pytest.raises(EngineExecutionError):
            r_engine.execute('stop("boom")')
        assert "1" in r_engine.execute("cat(survivor)").stdout

    def test_type_fidelity_round_trip(self, r_engine, typed_frame):
        r_engine.push("fidelity", typed_frame)
        back = r_engine.pull("fidelity")

        assert list(back.columns) == list(typed_frame.columns)
        np.testing.assert_allclose(
            back["num"].to_numpy(dtype=float), typed_frame["num"].to_numpy(dtype=float)
        )
        assert str(back["whole"].dtype) == "Int64"
        assert isinstance(back["grp"].dtype, pd.CategoricalDtype)
        assert list(back["grp"].cat.categories) == ["lo", "hi"]
        assert back["grp"].cat.ordered is True
        assert str(back["flag"].dtype) == "boolean"

    def test_empty_string_stays_distinct_from_missing(self, r_engine, typed_frame):
        """The reason the CSV transport uses an explicit NA sentinel."""
        r_engine.push("fidelity", typed_frame)
        back = r_engine.pull("fidelity")
        assert back["txt"].iloc[2] == ""
        assert pd.isna(back["txt"].iloc[3])

    def test_rownames_that_carry_meaning_survive(self, r_engine, sample_frame):
        r_engine.push("d", sample_frame)
        r_engine.execute("f <- lm(y ~ x1, data=d); ct <- as.data.frame(coef(summary(f)))")
        table = r_engine.pull("ct")
        assert "(Intercept)" in table.index

    def test_plots_are_captured(self, r_engine):
        result = r_engine.execute("plot(1:10, main='t')")
        assert len(result.figures) == 1
        assert result.figures[0].mimetype in {"image/svg+xml", "image/png"}
        assert len(result.figures[0].data) > 512

    def test_non_plotting_cells_produce_no_figure(self, r_engine):
        assert r_engine.execute("x <- 1").figures == []

    def test_restart_clears_the_session(self, r_engine):
        from econenv.exceptions import EngineExecutionError

        r_engine.execute("temporary <- 1")
        r_engine.restart()
        with pytest.raises(EngineExecutionError):
            r_engine.execute("cat(temporary)")


# --------------------------------------------------------------------------- #
# Stata
# --------------------------------------------------------------------------- #
@pytest.mark.stata
class TestStata:
    def test_reports_version_and_edition(self, stata_engine):
        assert stata_engine.version()
        assert stata_engine.info().edition in {"be", "se", "mp"}

    def test_executes_and_captures_output(self, stata_engine):
        assert "econenv" in stata_engine.execute('display "econenv"').stdout

    def test_errors_translate_the_return_code(self, stata_engine):
        from econenv.exceptions import EngineExecutionError

        with pytest.raises(EngineExecutionError) as excinfo:
            stata_engine.execute("regress nosuchvar")
        assert "r(" in str(excinfo.value)

    def test_frame_round_trip(self, stata_engine, sample_frame):
        stata_engine.push("default", sample_frame)
        back = stata_engine.pull()
        assert len(back) == len(sample_frame)
        np.testing.assert_allclose(back["y"].to_numpy(), sample_frame["y"].to_numpy(), rtol=1e-12)

    def test_scalars_keep_full_precision(self, stata_engine, sample_frame):
        """`display` rounds to ~9 digits; the Function Interface does not."""
        stata_engine.push("default", sample_frame)
        stata_engine.execute("regress y x1", quietly=True)
        r2 = stata_engine.pull_scalar("e(r2)")
        assert isinstance(r2, float)
        assert len(repr(r2).split(".")[-1]) > 9

    def test_matrices_come_back_as_arrays(self, stata_engine, sample_frame):
        stata_engine.push("default", sample_frame)
        stata_engine.execute("regress y x1 x2", quietly=True)
        table = stata_engine.pull_matrix("r(table)")
        assert table.shape[0] >= 6
        assert table.shape[1] == 3


# --------------------------------------------------------------------------- #
# EViews
# --------------------------------------------------------------------------- #
@pytest.mark.eviews
@pytest.mark.windows
class TestEViews:
    def test_reports_the_connected_version_not_the_newest_on_disk(self, eviews_engine):
        """Audit §5.1: the generic ProgID may not bind to the newest install."""
        assert eviews_engine.version()
        assert eviews_engine._connected_progid

    def test_executes_commands(self, eviews_engine):
        eviews_engine.execute("create u 10\nseries z = @trend")
        assert eviews_engine.pull_scalar("@obsrange") == 10.0

    def test_errors_carry_the_eviews_message_and_the_failing_line(self, eviews_engine):
        from econenv.exceptions import EngineExecutionError

        with pytest.raises(EngineExecutionError) as excinfo:
            eviews_engine.execute("create u 5\nnot_a_command")
        message = str(excinfo.value)
        assert "not_a_command" in message.lower()
        assert "1 of 2" in message

    def test_dated_frame_creates_a_dated_workfile(self, eviews_engine, quarterly_frame):
        eviews_engine.push("wf", quarterly_frame)
        assert eviews_engine.pull_scalar("@pagefreq") == "Q"

    def test_values_survive_the_com_round_trip(self, eviews_engine, quarterly_frame):
        """The regression guard for the silent all-NA PutSeries trap."""
        eviews_engine.push("wf", quarterly_frame)
        back = eviews_engine.pull()
        np.testing.assert_allclose(
            np.sort(back["Y"].to_numpy()), np.sort(quarterly_frame["y"].to_numpy()), rtol=1e-12
        )
        assert not back["Y"].isna().any()

    def test_the_date_index_is_rebuilt(self, eviews_engine, quarterly_frame):
        eviews_engine.push("wf", quarterly_frame)
        back = eviews_engine.pull()
        assert isinstance(back.index, pd.DatetimeIndex)
        assert back.index[0] == quarterly_frame.index[0]

    def test_missing_values_map_to_nan(self, eviews_engine):
        eviews_engine.execute("create u 5\nseries m = 1\nm(3) = NA")
        back = eviews_engine.pull("M")
        assert back["M"].isna().sum() == 1


# --------------------------------------------------------------------------- #
# cross-engine comparison (brief §22, §26, §48)
# --------------------------------------------------------------------------- #
class TestComparison:
    def test_runs_in_whatever_is_available(self, sample_frame):
        comparison = econenv.compare_ols(sample_frame, "y ~ x1 + x2")
        assert "python" in comparison.results
        assert comparison.agree

    def test_a_missing_engine_does_not_abort_the_others(self, sample_frame):
        comparison = econenv.compare_ols(
            sample_frame, "y ~ x1", engines=["python", "definitely_not_an_engine"]
        )
        assert "python" in comparison.results
        assert "definitely_not_an_engine" in comparison.failures

    def test_unknown_columns_are_reported_before_anything_runs(self, sample_frame):
        from econenv.exceptions import EconEnvError

        with pytest.raises(EconEnvError, match="not in the data"):
            econenv.compare_ols(sample_frame, "y ~ nope")

    @pytest.mark.r
    @pytest.mark.stata
    @pytest.mark.eviews
    @pytest.mark.matlab
    def test_all_five_engines_agree_to_machine_precision(self, sample_frame):
        """Brief §48. The point of the whole project."""
        comparison = econenv.compare_ols(sample_frame, "y ~ x1 + x2")
        assert set(comparison.results) == {"python", "r", "stata", "eviews", "matlab"}, (
            comparison.failures
        )

        table = comparison.coefficients()
        reference = table["python"]
        for engine in table.columns:
            np.testing.assert_allclose(
                table[engine].to_numpy(), reference.to_numpy(), rtol=1e-12, atol=1e-12
            )

        summary = comparison.summary()
        np.testing.assert_allclose(
            summary["r2"].to_numpy(dtype=float), summary["r2"].iloc[0], rtol=1e-10
        )
        assert comparison.agree

    @pytest.mark.r
    @pytest.mark.stata
    def test_information_criteria_differences_are_explained_not_hidden(self, sample_frame):
        """Brief §59: differences in defaults must surface, not be smoothed over."""
        comparison = econenv.compare_ols(sample_frame, "y ~ x1 + x2", engines=["python", "r"])
        summary = comparison.summary()
        assert summary.loc["r", "aic"] != summary.loc["python", "aic"]
        assert any("AIC" in note or "aic" in note for note in comparison.explain())

    def test_spec_is_validated_before_any_engine_starts(self, sample_frame):
        from econenv.exceptions import ModelSpecificationError

        with pytest.raises(ModelSpecificationError):
            ModelSpec(depvar="y", exog=["y"])


@pytest.mark.matlab
@pytest.mark.slow
class TestMatlabRoundTrip:
    """Every documented type, against a real MATLAB.

    The unit tests fake the engine, which proves the conversion rules but not
    that MATLAB agrees with them. These run the values through an actual
    session, which is where `y = 10` returning a ValueError from pandas was
    found in the first place.
    """

    @pytest.fixture(scope="class")
    def engine(self):
        from econenv.engines import registry

        eng = registry.get("matlab")
        eng.ensure_started()
        return eng

    @pytest.mark.parametrize(
        "code, check",
        [
            ("y = 10;", lambda v: v == 10.0 and isinstance(v, float)),
            ("y = true;", lambda v: v is True),
            ("y = int32(7);", lambda v: v == 7 and isinstance(v, int)),
            ("y = 'hello';", lambda v: v == "hello"),
            ('y = "hello";', lambda v: v == "hello"),
            ("y = 3 + 4i;", lambda v: v == 3 + 4j),
            ("y = [1 2 3];", lambda v: v.shape == (3,)),
            ("y = [1;2;3];", lambda v: v.shape == (3,)),
            ("y = [10 20; 30 40];", lambda v: v.shape == (2, 2)),
        ],
    )
    def test_pull_value_gives_the_documented_type(self, engine, code, check):
        engine.execute(code, capture_graphs=False)
        assert check(engine.pull_value("y"))

    def test_a_table_still_comes_back_as_a_dataframe(self, engine):
        engine.execute("y = table([1;2], [3;4], 'VariableNames', {'a','b'});", capture_graphs=False)
        frame = engine.pull_value("y")
        assert isinstance(frame, pd.DataFrame)
        assert list(frame.columns) == ["a", "b"]

    @pytest.mark.parametrize(
        "value, expected_class",
        [
            (5.0, "double"),
            (True, "logical"),
            ("text", "char"),
            ([1.0, 2.0, 3.0], "double"),
            ((1.0, 2.0), "double"),
            (np.arange(1, 6, dtype=float), "double"),
            (np.arange(6, dtype=float).reshape(2, 3), "double"),
        ],
    )
    def test_push_value_lands_as_the_documented_class(self, engine, value, expected_class):
        engine.push("x_rt", value)
        assert engine.pull_scalar("class(x_rt)") == expected_class

    def test_a_numpy_vector_survives_the_round_trip_unchanged(self, engine):
        original = np.array([1.5, -2.0, 3.25])
        engine.push("v_rt", original)
        np.testing.assert_allclose(engine.pull_value("v_rt"), original)

    def test_a_matrix_survives_the_round_trip_with_its_shape(self, engine):
        original = np.arange(6, dtype=float).reshape(2, 3)
        engine.push("m_rt", original)
        np.testing.assert_allclose(engine.pull_value("m_rt"), original)

    def test_pull_still_refuses_a_scalar_but_says_where_to_go(self, engine):
        """`pull` keeps its frame contract; the error names the typed path."""
        from econenv.exceptions import DataTransferError

        engine.execute("s_rt = 42;", capture_graphs=False)
        with pytest.raises(DataTransferError) as caught:
            engine.pull("s_rt")
        assert "pull_value" in str(caught.value)
