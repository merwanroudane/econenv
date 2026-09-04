"""Tests for engine logic that must pass with **no** Stata or EViews installed.

Brief §40: unit tests must not need the commercial engines. The parts of the
adapters that are pure logic — command splitting, name sanitising, error
translation, the VARIANT trap guard, frequency mapping — are tested here against
fakes, so a Linux CI runner exercises them even though it can never run EViews.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from econenv.bridges import eviews_bridge, r_bridge, stata_bridge
from econenv.engines.eviews_engine import _split_commands, parse_frequency
from econenv.exceptions import DataTransferError, com_message
from econenv.schema import ConversionReport


# --------------------------------------------------------------------------- #
# EViews command parsing
# --------------------------------------------------------------------------- #
def test_blank_lines_and_comments_are_dropped():
    assert _split_commands("create u 10\n\n' a comment\nseries x = 1") == [
        "create u 10",
        "series x = 1",
    ]


def test_underscore_continuation_is_joined():
    assert _split_commands("equation eq1.ls y c _\n  x1 x2") == ["equation eq1.ls y c x1 x2"]


def test_trailing_continuation_still_emits_the_command():
    assert _split_commands("series x = 1 _") == ["series x = 1"]


@pytest.mark.parametrize(
    ("page_freq", "expected"),
    [("Q", "QS"), ("M", "MS"), ("A", "YS"), ("D", "D"), ("U", None), (None, None)],
)
def test_frequency_mapping(page_freq, expected):
    assert parse_frequency(page_freq) == expected


# --------------------------------------------------------------------------- #
# COM error translation
# --------------------------------------------------------------------------- #
def test_com_message_extracts_the_readable_description():
    """The real shape of a comtypes COMError, from the Phase 0 audit."""
    error = Exception(
        -2147024809,
        "Parameter incorrect",
        (
            'X is not defined or is an illegal command in "X".',
            "EViews.Application.13.Run",
            None,
            0,
            None,
        ),
    )
    assert com_message(error) == 'X is not defined or is an illegal command in "X".'


def test_com_message_returns_none_for_ordinary_exceptions():
    assert com_message(ValueError("nope")) is None


# --------------------------------------------------------------------------- #
# name sanitising
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("raw", "expected"),
    [("GDP growth", "GDP_growth"), ("2020", "v_2020"), ("x.y", "x_y")],
)
def test_eviews_names_are_made_legal(raw, expected):
    assert eviews_bridge.sanitise_name(raw) == expected


def test_eviews_reserved_words_are_escaped():
    assert eviews_bridge.sanitise_name("resid") == "resid_"
    assert eviews_bridge.sanitise_name("c") == "c_"


def test_eviews_names_are_truncated_to_24_characters():
    assert len(eviews_bridge.sanitise_name("a" * 40)) == 24


def test_eviews_collisions_are_disambiguated():
    taken: set = set()
    first = eviews_bridge.sanitise_name("GDP growth", taken)
    second = eviews_bridge.sanitise_name("GDP.growth", taken)
    assert first != second


def test_stata_reserved_words_and_length():
    assert stata_bridge.sanitise_name("_cons") == "_cons_"
    assert len(stata_bridge.sanitise_name("v" * 50)) == 32
    assert stata_bridge.sanitise_name("1st var") == "v_1st_var"


def test_r_names_avoid_leading_digits_and_keywords():
    assert r_bridge.sanitise_name("2x") == "X2x"
    assert r_bridge.sanitise_name("if") == "if."
    assert r_bridge.sanitise_name("a b") == "a.b"


# --------------------------------------------------------------------------- #
# Stata preparation (no Stata needed)
# --------------------------------------------------------------------------- #
def test_stata_prepare_reports_every_rename():
    report = ConversionReport(engine="stata", direction="push")
    frame = pd.DataFrame({"GDP growth": [1.0], "_cons": [2.0]})
    prepared = stata_bridge.prepare(frame, report)
    assert list(prepared.columns) == ["GDP_growth", "_cons_"]
    assert len(report.warnings) == 2


def test_stata_prepare_moves_the_index_into_a_column(quarterly_frame):
    report = ConversionReport(engine="stata", direction="push")
    prepared = stata_bridge.prepare(quarterly_frame, report)
    assert isinstance(prepared.index, pd.RangeIndex)
    assert any("index" in str(note) for note in report.notes)


def test_stata_prepare_warns_about_categoricals(typed_frame):
    report = ConversionReport(engine="stata", direction="push")
    stata_bridge.prepare(typed_frame, report)
    assert any("value labels" in note.message for note in report.warnings)


def test_stata_prepare_warns_about_datetimes(typed_frame):
    report = ConversionReport(engine="stata", direction="push")
    stata_bridge.prepare(typed_frame, report)
    assert any("%tc" in note.message for note in report.warnings)


def test_stata_prepare_refuses_an_untranslatable_dtype():
    report = ConversionReport(engine="stata", direction="push")
    frame = pd.DataFrame({"weird": [{"a": 1}, {"b": 2}]})
    with pytest.raises(DataTransferError):
        stata_bridge.prepare(frame, report)


# --------------------------------------------------------------------------- #
# the PutSeries trap (brief §11, Phase 0 audit §5.5)
# --------------------------------------------------------------------------- #
class _FakeCOMApp:
    """Reproduces the measured EViews behaviour, including the silent trap.

    ``PutSeries`` with a plain Python list stores NA for every observation and
    reports success. Only a VARIANT is honoured.
    """

    def __init__(self):
        self.series = {}
        self.commands = []

    def Run(self, command):
        self.commands.append(command)

    def Get(self, expression):
        return {"=@wfname": "UNTITLED", "=@pagename": "Untitled", "=@obsrange": 4.0}.get(expression)

    def PutSeries(self, name, values):
        # comtypes names the VARIANT struct `tagVARIANT`; anything that is not
        # one takes the trap branch, exactly as the real EViews server does.
        if hasattr(values, "vt") and hasattr(values, "value"):
            self.series[name] = list(values.value)
        else:
            self.series[name] = [None] * len(list(values))  # the trap

    def GetSeries(self, name):
        return tuple(self.series[name])

    def Show(self):
        pass

    def Hide(self):
        pass


@pytest.mark.windows
def test_variant_marshalling_is_what_makes_putseries_work():
    """Guards the single most dangerous behaviour EconEnv works around."""
    app = _FakeCOMApp()
    values = [1.0, 2.0, 3.0]

    app.PutSeries("plain", values)
    assert app.GetSeries("plain") == (None, None, None), "the fake must reproduce the trap"

    app.PutSeries("wrapped", eviews_bridge._variant(values))
    assert app.GetSeries("wrapped") == (1.0, 2.0, 3.0)


@pytest.mark.windows
def test_variant_maps_nan_to_none():
    variant = eviews_bridge._variant([1.0, float("nan"), 3.0])
    assert variant.value[1] is None


@pytest.mark.windows
def test_verification_catches_an_all_na_write():
    """If marshalling ever regresses, the push must fail loudly, not silently."""

    class _Engine:
        name = "eviews"

        def __init__(self):
            self._app = _FakeCOMApp()

    engine = _Engine()
    frame = pd.DataFrame({"y": [1.0, 2.0, 3.0, 4.0]})
    engine._app.PutSeries("y", [1.0, 2.0, 3.0, 4.0])  # written via the broken path
    report = ConversionReport(engine="eviews", direction="push")
    with pytest.raises(DataTransferError) as excinfo:
        eviews_bridge._verify(engine, frame, {"y": "y"}, report)
    assert "NA for every observation" in str(excinfo.value)


def test_page_spec_uses_the_frequency_of_a_dated_index(quarterly_frame):
    assert eviews_bridge._page_spec(quarterly_frame.index, len(quarterly_frame)).startswith("Q ")


def test_page_spec_falls_back_to_undated():
    frame = pd.DataFrame({"y": [1.0, 2.0]})
    assert eviews_bridge._page_spec(frame.index, 2) == "u 2"


# --------------------------------------------------------------------------- #
# R transport helpers (no R needed)
# --------------------------------------------------------------------------- #
def test_r_schema_payload_records_factor_levels(typed_frame):
    payload = {entry["name"]: entry for entry in r_bridge._schema_payload(typed_frame)}
    assert payload["grp"]["type"] == "categorical"
    assert payload["grp"]["levels"] == ["lo", "hi"]
    assert payload["grp"]["ordered"] is True


def test_r_schema_is_reapplied_on_the_way_back():
    raw = pd.DataFrame(
        {"a": ["1", "2"], "b": ["TRUE", "FALSE"], "c": ["lo", "hi"], "d": ["1.5", "2.5"]}
    )
    schema = [
        {"name": "a", "type": "integer"},
        {"name": "b", "type": "boolean"},
        {"name": "c", "type": "categorical", "levels": ["lo", "hi"], "ordered": False},
        {"name": "d", "type": "float"},
    ]
    out = r_bridge._apply_schema(raw, schema)
    assert str(out["a"].dtype) == "Int64"
    assert str(out["b"].dtype) == "boolean"
    assert isinstance(out["c"].dtype, pd.CategoricalDtype)
    assert out["d"].dtype == np.float64


def test_r_literal_rendering():
    assert r_bridge is not None
    from econenv.engines.r_engine import _r_literal

    assert _r_literal(True) == "TRUE"
    assert _r_literal(3) == "3L"
    assert _r_literal(None) == "NULL"
    assert _r_literal('say "hi"') == '"say \\"hi\\""'
    assert _r_literal([1, 2]) == "c(1L, 2L)"


def test_r_plot_stub_is_not_rendered(tmp_path):
    """An opened-but-unused device leaves a header-only file; it must be skipped."""
    from econenv.engines.r_engine import _read_plot

    stub = tmp_path / "econenv-001.svg"
    stub.write_bytes(b"<svg></svg>")
    assert _read_plot(stub, "r") is None

    real = tmp_path / "econenv-002.svg"
    real.write_bytes(b"<svg>" + b"<path d='M0 0'/>" * 60 + b"</svg>")
    assert _read_plot(real, "r") is not None
