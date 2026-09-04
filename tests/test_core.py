"""Unit tests that need no third-party engine at all (brief §40)."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

import econenv
from econenv import config, schema, transfer
from econenv.engines import registry
from econenv.engines.base import BaseEngine, Capability, EngineState
from econenv.exceptions import (
    ConfigurationError,
    EconEnvError,
    EngineNotFoundError,
    ModelSpecificationError,
)
from econenv.models.spec import ModelSpec, parse_spec
from econenv.results import ExecutionResult, ModelResult


# --------------------------------------------------------------------------- #
# package surface
# --------------------------------------------------------------------------- #
def test_version_is_exposed():
    assert econenv.__version__.count(".") == 2


def test_all_four_engines_are_registered():
    assert set(registry.names()) == {"python", "r", "stata", "eviews"}


def test_python_is_listed_first():
    assert registry.names()[0] == "python"


def test_unknown_engine_names_the_alternatives():
    with pytest.raises(EngineNotFoundError) as excinfo:
        registry.get("gretl")
    assert "python" in str(excinfo.value)


def test_engine_info_is_json_serialisable():
    for info in registry.info():
        json.dumps(info.to_dict())


# --------------------------------------------------------------------------- #
# config
# --------------------------------------------------------------------------- #
def test_config_defaults_resolve():
    assert config.get_option("core", "timeout") == 300.0
    assert config.get_option("r", "backend") == "auto"


def test_runtime_override_wins():
    config.set_option("core", "timeout", 42.0)
    try:
        assert config.get_option("core", "timeout") == 42.0
    finally:
        config.reset("core")
    assert config.get_option("core", "timeout") == 300.0


def test_unknown_option_is_rejected_not_stored():
    with pytest.raises(ConfigurationError):
        config.set_option("r", "hoem", "typo")
    with pytest.raises(ConfigurationError):
        config.set_option("julia", "home", "x")


def test_string_values_are_coerced_to_the_default_type():
    config.set_option("core", "timeout", "12.5")
    try:
        assert config.get_option("core", "timeout") == 12.5
    finally:
        config.reset("core")


def test_env_layer_is_read(monkeypatch):
    monkeypatch.setenv("ECONENV_CORE_TIMEOUT", "77")
    assert config.get_option("core", "timeout") == 77.0


# --------------------------------------------------------------------------- #
# schema / types
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([1, 2, 3], schema.LogicalType.INTEGER),
        ([1.0, 2.0], schema.LogicalType.FLOAT),
        (["a", "b"], schema.LogicalType.STRING),
        ([True, False], schema.LogicalType.BOOLEAN),
    ],
)
def test_logical_type_inference(values, expected):
    assert schema.logical_type_of(pd.Series(values)) is expected


def test_categorical_and_datetime_are_recognised(typed_frame):
    meta = schema.describe_frame(typed_frame, name="t")
    assert meta.column("grp").logical_type is schema.LogicalType.CATEGORICAL
    assert meta.column("grp").categories == ["lo", "hi"]
    assert meta.column("grp").ordered is True
    assert meta.column("when").logical_type is schema.LogicalType.DATETIME


def test_datetime_index_becomes_the_time_variable(quarterly_frame):
    meta = schema.describe_frame(quarterly_frame)
    assert meta.time_var is not None
    assert meta.frequency is not None


def test_multiindex_is_read_as_panel_then_time():
    index = pd.MultiIndex.from_product(
        [["a", "b"], pd.date_range("2020-01-01", periods=3, freq="YS")], names=["id", "year"]
    )
    frame = pd.DataFrame({"y": range(6)}, index=index)
    meta = schema.describe_frame(frame)
    assert meta.panel_var == "id"
    assert meta.time_var == "year"


def test_conversion_report_tracks_severity():
    report = schema.ConversionReport(engine="r", direction="push")
    assert not report.lossy
    report.add(schema.Severity.INFO, "fine")
    assert not report.lossy
    report.add(schema.Severity.WARNING, "renamed", column="x")
    assert report.lossy
    assert len(report.warnings) == 1
    assert "x" in str(report)


# --------------------------------------------------------------------------- #
# results
# --------------------------------------------------------------------------- #
def test_execution_result_round_trips_to_dict():
    result = ExecutionResult(engine="r", code="1+1", stdout="2", scalars={"a": np.float64(1.0)})
    payload = result.to_dict()
    json.dumps(payload)
    assert payload["engine"] == "r"
    assert payload["scalars"]["a"] == 1.0


def test_execution_result_renders_both_mimetypes():
    bundle = ExecutionResult(engine="r", code="x", stdout="hi")._repr_mimebundle_()
    assert "text/plain" in bundle
    assert "hi" in bundle["text/html"]


def test_model_result_from_arrays_pads_missing_columns():
    result = ModelResult.from_arrays("python", "OLS", ["x", "_cons"], [1.0, 2.0])
    assert list(result.coefficients.columns) == list(ModelResult.COEF_COLUMNS)
    assert np.isnan(result.coefficients["std_err"]).all()
    assert result.coefficients.loc["x", "coef"] == 1.0


def test_model_result_summary_row_keeps_missing_as_none():
    result = ModelResult(engine="stata", model="OLS", r2=0.5)
    row = result.summary_row()
    assert row["r2"] == 0.5
    assert row["aic"] is None


# --------------------------------------------------------------------------- #
# model specification
# --------------------------------------------------------------------------- #
def test_formula_parsing():
    spec = ModelSpec.from_formula("y ~ x1 + x2")
    assert spec.depvar == "y"
    assert spec.exog == ["x1", "x2"]
    assert spec.constant is True


def test_formula_without_constant():
    assert ModelSpec.from_formula("y ~ x - 1").constant is False
    assert ModelSpec.from_formula("y ~ x + 0").constant is False


def test_positional_spec_parsing():
    spec = parse_spec("y x1 x2")
    assert (spec.depvar, spec.exog) == ("y", ["x1", "x2"])


@pytest.mark.parametrize("formula", ["y ~ x1*x2", "y ~ log(x)", "y ~ factor(id)", "y ~ x1:x2"])
def test_unsupported_formula_terms_are_refused_clearly(formula):
    """Half-supporting interactions across four dialects would be worse than refusing."""
    with pytest.raises(ModelSpecificationError) as excinfo:
        ModelSpec.from_formula(formula)
    assert "additive" in str(excinfo.value)


def test_depvar_on_both_sides_is_rejected():
    with pytest.raises(ModelSpecificationError):
        ModelSpec(depvar="y", exog=["y", "x"])


def test_duplicate_regressors_are_rejected():
    with pytest.raises(ModelSpecificationError):
        ModelSpec(depvar="y", exog=["x", "x"])


def test_unknown_vcov_is_rejected():
    with pytest.raises(ModelSpecificationError):
        ModelSpec(depvar="y", exog=["x"], vcov="sandwich")


def test_spec_round_trips_through_dict():
    spec = ModelSpec.from_formula("y ~ x1 + x2", vcov="hc1")
    assert ModelSpec(**dict(spec.to_dict())).formula == spec.formula


# --------------------------------------------------------------------------- #
# python engine
# --------------------------------------------------------------------------- #
def test_python_engine_executes_and_keeps_state():
    engine = registry.get("python")
    engine.start()
    engine.execute("value = 6 * 7")
    assert engine.pull_scalar("value") == 42


def test_python_engine_captures_stdout():
    engine = registry.get("python")
    engine.start()
    assert "hello" in engine.execute("print('hello')").stdout


def test_python_engine_reports_errors_with_the_code():
    from econenv.exceptions import EngineExecutionError

    engine = registry.get("python")
    engine.start()
    with pytest.raises(EngineExecutionError) as excinfo:
        engine.execute("1 / 0")
    assert excinfo.value.code == "1 / 0"


def test_python_ols_matches_statsmodels(sample_frame):
    import statsmodels.api as sm

    engine = registry.get("python")
    engine.start()
    result = engine._fit_ols(ModelSpec.from_formula("y ~ x1 + x2"), sample_frame)

    X = sm.add_constant(sample_frame[["x1", "x2"]])
    expected = sm.OLS(sample_frame["y"], X).fit()
    assert result.nobs == int(expected.nobs)
    np.testing.assert_allclose(result.r2, expected.rsquared)
    np.testing.assert_allclose(
        result.coefficients.loc["x1", "coef"], expected.params["x1"], rtol=1e-12
    )


def test_intercept_is_named_cons_everywhere(sample_frame):
    engine = registry.get("python")
    engine.start()
    result = engine._fit_ols(ModelSpec.from_formula("y ~ x1"), sample_frame)
    assert "_cons" in result.coefficients.index


# --------------------------------------------------------------------------- #
# registry extensibility (brief §5)
# --------------------------------------------------------------------------- #
class _FakeEngine(BaseEngine):
    name = "fake"
    display_name = "Fake"
    declared_capabilities = (Capability.EXECUTE,)

    def _detect(self):
        self._backend = "test"
        return True

    def _start(self):
        self._state = EngineState.RUNNING

    def _stop(self):
        pass

    def _execute(self, code, **kwargs):
        return ExecutionResult(engine=self.name, code=code, stdout=code.upper())


def test_third_party_engine_can_be_registered_and_removed():
    registry.register(_FakeEngine)
    try:
        assert "fake" in registry.names()
        engine = registry.get("fake")
        assert engine.execute("hi").stdout == "HI"
        assert not engine.has(Capability.PUSH_FRAME)
    finally:
        registry.unregister("fake")
    assert "fake" not in registry.names()


def test_registering_a_duplicate_name_is_refused():
    registry.register(_FakeEngine)
    try:

        class Other(_FakeEngine):
            pass

        with pytest.raises(EconEnvError):
            registry.register(Other)
    finally:
        registry.unregister("fake")


def test_capability_error_names_the_missing_capability():
    from econenv.exceptions import CapabilityError

    registry.register(_FakeEngine)
    try:
        engine = registry.get("fake")
        engine.start()
        with pytest.raises(CapabilityError) as excinfo:
            engine.push("x", pd.DataFrame({"a": [1]}))
        assert "push_frame" in str(excinfo.value)
    finally:
        registry.unregister("fake")


# --------------------------------------------------------------------------- #
# provenance
# --------------------------------------------------------------------------- #
def test_frame_hash_is_stable_and_sensitive(sample_frame):
    first = transfer.hash_frame(sample_frame)
    assert first == transfer.hash_frame(sample_frame.copy())
    changed = sample_frame.copy()
    changed.iloc[0, 0] += 1.0
    assert transfer.hash_frame(changed) != first


def test_frame_hash_notices_a_dtype_change(sample_frame):
    as_float32 = sample_frame.astype("float32")
    assert transfer.hash_frame(as_float32) != transfer.hash_frame(sample_frame)


def test_snapshot_is_serialisable():
    payload = transfer.snapshot(include_packages=False)
    json.dumps(payload, default=str)
    assert set(payload["engines"]) == {"python", "r", "stata", "eviews"}


def test_provenance_record_has_the_required_fields():
    record = transfer.provenance(engine="python", code="1+1")
    assert record["engine"] == "python"
    assert len(record["code_sha256_16"]) == 16
    assert record["timestamp"].endswith("+00:00")


def test_annotate_attaches_metadata(sample_frame):
    frame = transfer.annotate(sample_frame.copy(), name="d", time_var="x1")
    assert transfer.metadata(frame).time_var == "x1"


# --------------------------------------------------------------------------- #
# diagnostics
# --------------------------------------------------------------------------- #
def test_doctor_runs_and_reports_host_checks():
    report = econenv.doctor()
    groups = report.by_group()
    assert "host" in groups
    assert any(c.name == "Python" for c in groups["host"])
    json.dumps(report.to_dict())


def test_doctor_findings_carry_a_fix():
    """A warning without a suggested action is only half a diagnostic."""
    report = econenv.doctor()
    for check in report.warnings + report.errors:
        assert check.fix, f"{check.name} has no suggested fix"


def test_doctor_for_an_unknown_engine_is_an_error_not_a_crash():
    assert econenv.doctor("julia").errors


def test_doctor_does_not_error_on_a_working_install_without_optional_extras():
    """`doctor` exits 1 on any ERROR.

    A Python + R + Stata machine that never asked for EViews must not fail a CI
    gate because `comtypes` is absent. ERROR is reserved for "you configured
    this and it is broken".
    """
    report = econenv.doctor()
    for check in report.errors:
        assert "comtypes" not in check.name, (
            "a missing optional extra must not be an ERROR: " + check.detail
        )


def test_statsmodels_is_a_core_dependency():
    """`compare_ols` is the headline feature and Python is one of its engines.

    Without statsmodels a fresh `pip install econenv` silently produces a
    comparison table with the Python column missing.
    """
    import importlib.util

    assert importlib.util.find_spec("statsmodels") is not None


def test_printing_a_result_shows_what_the_notebook_shows():
    """`str()` and the rich display must not disagree about what an object is.

    Every result class defined `_repr_mimebundle_` but no `__str__`, so a
    notebook showed the full table while `print(result)` in a script or the CLI
    showed only `<ComparisonResult ...>`. The text was already being built —
    it just was not reachable outside a notebook.
    """
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(3)
    n = 40
    frame = pd.DataFrame({"x": rng.normal(size=n)})
    frame["y"] = 1 + 2 * frame.x + rng.normal(scale=0.3, size=n)

    comparison = econenv.compare_ols(frame, "y ~ x", engines=["python"])

    rendered = str(comparison)
    assert rendered == comparison._repr_mimebundle_()["text/plain"]
    assert "Coefficients" in rendered
    assert not rendered.startswith("<"), "str() must not fall back to the repr"
    assert repr(comparison).startswith("<"), "repr() stays terse for debugging"


def test_printing_a_figure_describes_it_rather_than_dumping_bytes():
    from econenv.results import Figure

    figure = Figure(
        data=b"\x89PNG" + b"0" * 5000, mimetype="image/png", engine="eviews", name="x.line"
    )

    rendered = str(figure)
    assert "PNG" in rendered and "eviews" in rendered and "x.line" in rendered
    assert "5,004" in rendered, "say how big it is"
    assert "\x89" not in rendered, "never print raw image bytes to a terminal"


def test_pulling_from_r_without_a_name_never_returns_an_empty_frame():
    """R has no "current dataset" the way Stata and EViews do.

    The default was R's `.Last.value` — the last top-level expression — which
    after a plot or a model fit is not a data frame, so `pull("r")` silently
    returned an empty frame instead of the data. Failing loudly with the names
    R actually holds is the only safe behaviour.
    """
    from econenv.engines.r_engine import REngine
    from econenv.exceptions import DataTransferError

    engine = object.__new__(REngine)
    engine._last_frame = None
    engine.name = "r"
    engine._frames_hint = lambda: "Data frames in R: cars"

    with pytest.raises(DataTransferError) as caught:
        engine._pull_frame(None)

    assert "needs a name" in str(caught.value)
    assert ".Last.value" not in str(caught.value)


def test_r_remembers_the_frame_econenv_last_transferred():
    from econenv.engines.r_engine import REngine

    engine = object.__new__(REngine)
    engine._last_frame = None
    engine.name = "r"
    pulled = {}
    engine._pull_frame_impl = None

    import econenv.bridges.r_bridge as bridge

    original = bridge.pull_frame
    bridge.pull_frame = lambda eng, name, **kw: pulled.setdefault("name", name)
    try:
        engine._push_frame_called = True
        engine._last_frame = "macro"  # what a push would have recorded
        engine._pull_frame(None)
    finally:
        bridge.pull_frame = original

    assert pulled["name"] == "macro", "the default must be the frame we transferred"


class TestColab:
    """Colab is Linux, so what is possible there is decided before install.

    Saying "EViews not configured" on a machine where EViews *cannot exist*
    sends someone hunting for a fix that does not exist.
    """

    def test_colab_is_detected_from_its_environment(self, monkeypatch):
        from econenv import discovery

        monkeypatch.setenv("COLAB_RELEASE_TAG", "release-colab_2026")
        assert discovery.is_colab() is True

    def test_not_colab_on_an_ordinary_machine(self, monkeypatch):
        import sys as _sys

        from econenv import discovery

        monkeypatch.delenv("COLAB_RELEASE_TAG", raising=False)
        monkeypatch.delenv("COLAB_GPU", raising=False)
        monkeypatch.setitem(_sys.modules, "google.colab", None)
        monkeypatch.delitem(_sys.modules, "google.colab")
        monkeypatch.setattr(
            discovery.importlib.util
            if hasattr(discovery, "importlib")
            else __import__("importlib.util", fromlist=["util"]),
            "find_spec",
            lambda name: None,
            raising=False,
        )
        assert discovery.is_colab() is False

    def test_doctor_explains_colab_rather_than_reporting_a_fault(self, monkeypatch):
        from econenv import diagnostics, discovery

        monkeypatch.setattr(discovery, "is_colab", lambda: True)

        checks = diagnostics.check_host()
        colab = [c for c in checks if c.name == "Google Colab"]

        assert colab, "doctor must say when it is running on Colab"
        assert colab[0].status is diagnostics.Status.PASS
        assert "R" in colab[0].detail
        # Stata for Linux exists and pystata supports it, so Colab must not be
        # told Stata is impossible — only EViews is.
        assert "Stata for Linux" in colab[0].fix
        assert "EViews cannot" in colab[0].fix

    def test_eviews_on_colab_is_skipped_never_an_error(self, monkeypatch):
        from econenv import diagnostics, discovery

        monkeypatch.setattr(diagnostics.platform, "system", lambda: "Linux")
        monkeypatch.setattr(discovery, "is_colab", lambda: True)

        checks = diagnostics.check_eviews()

        assert len(checks) == 1
        assert checks[0].status is diagnostics.Status.SKIP
        # The reason must be the real one, not a guess: no Linux build, Wine
        # cannot licence, and EViews itself forbids reaching it over a network.
        fix = checks[0].fix
        assert "no Linux build" in fix
        assert "Wine" in fix
        assert "web server access to EViews via COM is not allowed" in fix
