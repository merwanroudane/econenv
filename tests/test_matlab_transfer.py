"""MATLAB transfer, namespace resolution and the command catalogue.

The conversion tests use a fake engine that records what the bridge asked
MATLAB to do, so the type rules are checked without a MATLAB licence and
without a minute of start-up per test. The round trips against a real MATLAB
live in ``test_integration.py`` and are skipped when it is absent.
"""

from __future__ import annotations

import sys
import types

import numpy as np
import pytest

from econenv.bridges import matlab_bridge
from econenv.engines import matlab_commands
from econenv.exceptions import DataTransferError
from econenv.magics._common import resolve_python_name


# --------------------------------------------------------------------------- #
# a MATLAB engine that only remembers what it was told
# --------------------------------------------------------------------------- #
class FakeWorkspace(dict):
    pass


class FakeMatlab:
    """Enough of ``matlab.engine`` to record a conversion."""

    def __init__(self, classes=None, values=None, scalar=None):
        self.workspace = FakeWorkspace()
        self.evaluated = []
        self._classes = classes or {}
        self._values = values or {}
        self._scalar = scalar or {}

    def eval(self, code, nargout=0):
        self.evaluated.append(code)
        for pattern, answer in self._scalar.items():
            if pattern in code:
                return answer
        if code.startswith("class("):
            name = code[len("class(") : -1]
            return self._classes.get(name, "double")
        if code.startswith("exist("):
            return 1.0
        if code.startswith("isscalar("):
            name = code[len("isscalar(") : -1]
            return np.ndim(self._values.get(name, 0)) == 0
        if code.startswith("isreal(") and "== 0" in code:
            name = code[len("isreal(") : code.index(")")]
            return np.iscomplexobj(self._values.get(name, 0.0))
        if code.startswith("iscellstr("):
            return True
        return 0.0


class FakeEngine:
    """The bit of MatlabEngine the bridge touches."""

    name = "matlab"

    def __init__(self, **kwargs):
        self._eng = FakeMatlab(**kwargs)


@pytest.fixture(autouse=True)
def fake_matlab_module(monkeypatch):
    """``import matlab`` inside the bridge, without MATLAB installed."""
    module = types.ModuleType("matlab")
    module.double = lambda rows, is_complex=False: ("double", rows, is_complex)
    module.logical = lambda rows: ("logical", rows)
    monkeypatch.setitem(sys.modules, "matlab", module)
    return module


# --------------------------------------------------------------------------- #
# Python -> MATLAB
# --------------------------------------------------------------------------- #
class TestPushValue:
    """Reported: `%%matlab -i x` raised TypeError for a list or any ndarray.

    ``_push_scalar`` called ``float(value)`` on everything that was not a
    DataFrame, so ``float([1.0, 2.0])`` and ``float(np.arange(5))`` both failed
    in the float constructor rather than being converted.
    """

    @pytest.mark.parametrize(
        "value, expected",
        [
            (5.0, 5.0),
            (7, 7.0),
            (np.float64(2.5), 2.5),
            (np.int64(3), 3.0),
        ],
    )
    def test_numbers_become_a_double_scalar(self, value, expected):
        engine = FakeEngine()
        matlab_bridge.push_value(engine, "x", value)
        assert engine._eng.workspace["x"] == expected

    def test_bool_becomes_logical_not_double(self):
        """A bool is a subclass of int, so order of isinstance checks matters."""
        engine = FakeEngine()
        matlab_bridge.push_value(engine, "flag", True)
        assert engine._eng.workspace["flag"][0] == "logical"

    def test_str_becomes_char_with_quotes_escaped(self):
        engine = FakeEngine()
        matlab_bridge.push_value(engine, "s", "it's fine")
        assert "s = 'it''s fine';" in engine._eng.evaluated

    def test_complex_survives(self):
        engine = FakeEngine()
        matlab_bridge.push_value(engine, "z", 3 + 4j)
        assert engine._eng.workspace["z"] == 3 + 4j

    @pytest.mark.parametrize(
        "value",
        [[1.0, 2.0, 3.0], (1.0, 2.0, 3.0), np.arange(1, 4, dtype=float)],
    )
    def test_a_sequence_becomes_a_column_vector(self, value):
        engine = FakeEngine()
        matlab_bridge.push_value(engine, "v", value)
        kind, rows, _ = engine._eng.workspace["v"]
        assert kind == "double"
        assert rows == [[1.0], [2.0], [3.0]], "each element on its own row"

    def test_orientation_row_transposes(self):
        engine = FakeEngine()
        matlab_bridge.push_value(engine, "v", [1.0, 2.0], orientation="row")
        assert "v = v.';" in engine._eng.evaluated

    def test_two_dimensional_shape_is_preserved(self):
        engine = FakeEngine()
        matlab_bridge.push_value(engine, "A", np.arange(6, dtype=float).reshape(2, 3))
        _, rows, _ = engine._eng.workspace["A"]
        assert rows == [[0.0, 1.0, 2.0], [3.0, 4.0, 5.0]]
        assert "A = A.';" not in engine._eng.evaluated, "a matrix must not be transposed"

    def test_three_dimensions_is_refused_with_a_reason(self):
        engine = FakeEngine()
        with pytest.raises(DataTransferError) as caught:
            matlab_bridge.push_value(engine, "A", np.zeros((2, 2, 2)))
        assert "3 dimensions" in str(caught.value)

    def test_none_is_refused_rather_than_becoming_nan_silently(self):
        engine = FakeEngine()
        with pytest.raises(DataTransferError) as caught:
            matlab_bridge.push_value(engine, "x", None)
        assert "no equivalent of None" in str(caught.value)
        assert "nan" in str(caught.value).lower(), "say what to use instead"

    def test_an_unsupported_object_names_its_type(self):
        engine = FakeEngine()
        with pytest.raises(DataTransferError) as caught:
            matlab_bridge.push_value(engine, "x", {1, 2})
        assert "set" in str(caught.value)

    def test_list_of_strings_becomes_a_string_array(self):
        engine = FakeEngine()
        matlab_bridge.push_value(engine, "names", ["a", "b"])
        assert engine._eng.workspace["names"] == ["a", "b"]
        assert any("string(names" in code for code in engine._eng.evaluated)


# --------------------------------------------------------------------------- #
# MATLAB -> Python
# --------------------------------------------------------------------------- #
class TestPullValue:
    """Reported: `%%matlab -o y` with `y = 10` raised

        ValueError: Must pass 2-d input. shape=()

    from inside pandas, because every pull went through ``pd.DataFrame``.
    """

    def _engine(self, kind, value):
        return FakeEngine(classes={"y": kind}, values={"y": value})

    def test_numeric_scalar_is_a_float(self):
        engine = self._engine("double", 10.0)
        engine._eng.workspace["y"] = 10.0
        assert matlab_bridge.pull_value(engine, "y") == 10.0
        assert isinstance(matlab_bridge.pull_value(engine, "y"), float)

    def test_integer_class_stays_an_int(self):
        engine = self._engine("int32", 7)
        engine._eng.workspace["y"] = 7
        value = matlab_bridge.pull_value(engine, "y")
        assert value == 7 and isinstance(value, int)

    def test_logical_scalar_is_a_bool(self):
        engine = self._engine("logical", True)
        engine._eng.workspace["y"] = True
        value = matlab_bridge.pull_value(engine, "y")
        assert value is True and isinstance(value, bool)

    def test_char_is_a_str(self):
        engine = self._engine("char", "hello")
        engine._eng.workspace["y"] = "hello"
        assert matlab_bridge.pull_value(engine, "y") == "hello"

    @pytest.mark.parametrize("stored", [[[1.0, 2.0, 3.0]], [[1.0], [2.0], [3.0]]])
    def test_a_vector_comes_back_flat_whichever_way_it_was_oriented(self, stored):
        """MATLAB has no 1-D array; a (1, 3) result would be a surprise."""
        engine = self._engine("double", stored)
        engine._eng.workspace["y"] = stored
        value = matlab_bridge.pull_value(engine, "y")
        assert isinstance(value, np.ndarray)
        assert value.shape == (3,)
        assert list(value) == [1.0, 2.0, 3.0]

    def test_a_matrix_keeps_its_shape(self):
        stored = [[10.0, 20.0], [30.0, 40.0]]
        engine = self._engine("double", stored)
        engine._eng.workspace["y"] = stored
        value = matlab_bridge.pull_value(engine, "y")
        assert value.shape == (2, 2)

    def test_complex_scalar_is_complex(self):
        engine = self._engine("double", 3 + 4j)
        engine._eng.workspace["y"] = 3 + 4j
        assert matlab_bridge.pull_value(engine, "y") == 3 + 4j

    def test_a_struct_is_refused_by_name_with_a_way_forward(self):
        engine = self._engine("struct", None)
        with pytest.raises(DataTransferError) as caught:
            matlab_bridge.pull_value(engine, "y")
        message = str(caught.value)
        assert "struct" in message
        assert "struct2table" in message, "name the conversion that would work"

    def test_a_name_that_does_not_exist_says_so(self):
        engine = FakeEngine()
        engine._eng._scalar = {"exist(": 0.0}
        with pytest.raises(DataTransferError) as caught:
            matlab_bridge.pull_value(engine, "nope")
        assert "not in the MATLAB workspace" in str(caught.value)


# --------------------------------------------------------------------------- #
# the namespace bug behind the Colab failure
# --------------------------------------------------------------------------- #
class TestResolvePythonName:
    """Reported from Colab's local runtime: a variable assigned in one cell was
    absent from ``shell.user_ns``, so ``%%matlab -i x`` raised NameError until
    the user wrote ``get_ipython().user_ns["x"] = x`` by hand.
    """

    class Shell:
        def __init__(self, user_ns=None, user_global_ns=None):
            self.user_ns = user_ns if user_ns is not None else {}
            if user_global_ns is not None:
                self.user_global_ns = user_global_ns

    def test_found_in_the_local_scope(self):
        assert resolve_python_name("x", {"x": 5}, self.Shell()) == 5

    def test_found_in_user_ns(self):
        assert resolve_python_name("x", {}, self.Shell({"x": 7})) == 7

    def test_found_in_user_global_ns_when_that_is_where_it_lives(self):
        """The Colab case: not in local_ns, not in user_ns, but reachable."""
        shell = self.Shell(user_ns={}, user_global_ns={"x": 9})
        assert resolve_python_name("x", {}, shell) == 9

    def test_a_variable_assigned_none_is_defined(self):
        """`if obj is None: raise NameError` conflated absent with None."""
        assert resolve_python_name("x", {"x": None}, self.Shell()) is None

    def test_a_missing_name_still_raises_name_error(self):
        with pytest.raises(NameError) as caught:
            resolve_python_name("x", {}, self.Shell())
        assert "not defined in Python" in str(caught.value)

    def test_a_case_difference_is_pointed_out(self):
        with pytest.raises(NameError) as caught:
            resolve_python_name("DF", {"df": 1}, self.Shell())
        assert "df" in str(caught.value)

    def test_local_scope_wins_over_the_shell(self):
        assert resolve_python_name("x", {"x": "local"}, self.Shell({"x": "global"})) == "local"

    def test_a_shell_without_namespaces_does_not_crash(self):
        with pytest.raises(NameError):
            resolve_python_name("x", None, object())


# --------------------------------------------------------------------------- #
# the catalogue
# --------------------------------------------------------------------------- #
class TestMatlabCatalogue:
    def test_every_command_has_a_category_that_exists(self):
        unknown = {c.category for c in matlab_commands.COMMANDS} - set(matlab_commands.CATEGORIES)
        assert not unknown

    def test_every_command_has_an_example(self):
        assert all(c.example.strip() for c in matlab_commands.COMMANDS)

    def test_names_are_unique(self):
        names = [c.name for c in matlab_commands.COMMANDS]
        assert len(names) == len(set(names))

    @pytest.mark.parametrize(
        "term, expected",
        [
            ("cointegration", "jcitest"),
            ("unit root", "adftest"),
            ("wavelet", "cwt"),
            ("regression", "fitlm"),
            ("groupby", "groupsummary"),
            ("subplot", "tiledlayout"),
        ],
    )
    def test_search_finds_what_a_researcher_would_type(self, term, expected):
        assert expected in [c.name for c in matlab_commands.find(term)]

    def test_a_category_name_lists_that_category_only(self):
        found = matlab_commands.find("wavelet")
        assert {c.category for c in found} == {"wavelet"}

    def test_an_exact_name_ranks_first(self):
        assert matlab_commands.find("corr")[0].name == "corr"

    def test_nothing_matches_returns_empty_rather_than_raising(self):
        assert matlab_commands.find("zzzz") == []

    def test_toolbox_requirements_are_stated_for_non_base_commands(self):
        econ = matlab_commands.get("jcitest")
        assert econ is not None and "Econometrics" in econ.toolbox

    def test_quantile_is_not_claimed_for_the_statistics_toolbox(self):
        """which() put it in toolbox/matlab/datafun — it is base MATLAB now."""
        command = matlab_commands.get("quantile")
        assert command is not None
        assert command.toolbox == matlab_commands.BASE

    def test_rendering_indents_a_multi_line_example(self):
        text = str(matlab_commands.get("autocorr"))
        assert "\n         autocorr(y, 24);" in text


class TestGeneratedDocs:
    def test_the_docs_page_matches_the_catalogue(self):
        """Generated, not hand-written, so it cannot describe a command wrongly.

        Regenerate with: python scripts/gen_matlab_docs.py
        """
        import importlib.util
        import pathlib

        root = pathlib.Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location(
            "gen_matlab_docs", root / "scripts" / "gen_matlab_docs.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        page = root / "docs" / "engines" / "matlab-commands.md"
        assert page.exists(), "the MATLAB command reference is missing"
        assert page.read_text(encoding="utf-8") == module.render(), (
            "docs/engines/matlab-commands.md is out of date — "
            "run: python scripts/gen_matlab_docs.py"
        )
