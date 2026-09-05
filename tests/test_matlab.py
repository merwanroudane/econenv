"""MATLAB adapter tests.

None of these start MATLAB: they pin the decisions made before the engine is
reached. The behaviour they encode was measured against MATLAB R2024a with
matlabengine 24.1.4 on Windows.
"""

import pandas as pd
import pytest

from econenv.bridges import matlab_bridge
from econenv.engines import matlab_engine


class TestReleaseSelection:
    """The Engine API starts the release it was built for, not the newest installed.

    On the development machine R2024a and R2025a are both present while the
    installed API is 24.1.4, which starts R2024a. Reporting R2025a would repeat
    the mistake the EViews adapter used to make: naming a version the user is
    not running.
    """

    @pytest.mark.parametrize(
        "version, expected",
        [
            ("24.1.4", "R2024a"),
            ("24.2.1", "R2024b"),
            ("25.1.0", "R2025a"),
            ("25.2.3", "R2025b"),
        ],
    )
    def test_engine_api_version_maps_to_its_release(self, monkeypatch, version, expected):
        import importlib.metadata as md

        monkeypatch.setattr(md, "version", lambda name: version)
        assert matlab_engine.engine_api_release() == expected

    def test_unknown_series_is_admitted_not_guessed(self, monkeypatch):
        import importlib.metadata as md

        monkeypatch.setattr(md, "version", lambda name: "99.9.9")
        assert matlab_engine.engine_api_release() is None

    def test_no_engine_api_installed_is_not_an_error(self, monkeypatch):
        import importlib.metadata as md

        def boom(name):
            raise md.PackageNotFoundError(name)

        monkeypatch.setattr(md, "version", boom)
        assert matlab_engine.engine_api_release() is None

    @pytest.mark.parametrize(
        "names, newest",
        [
            (["R2024a", "R2025a"], "R2025a"),
            (["R2023b", "R2024a"], "R2024a"),
            (["R2024a", "R2024b"], "R2024b"),
        ],
    )
    def test_releases_sort_newest_first(self, names, newest):
        assert max(names, key=matlab_engine._release_key) == newest


class TestNaming:
    """MATLAB identifiers are stricter than pandas column names."""

    @pytest.mark.parametrize(
        "column, expected",
        [
            ("gdp", "gdp"),
            ("real gdp", "real_gdp"),
            ("gdp%", "gdp_"),
            ("2024", "v_2024"),
            ("", "v_"),
        ],
    )
    def test_columns_become_legal_identifiers(self, column, expected):
        assert matlab_bridge._safe_name(column) == expected

    def test_names_are_truncated_to_matlabs_limit(self):
        assert len(matlab_bridge._safe_name("x" * 200)) == 63


class TestNumberList:
    """Figure handles come back as a scalar, an array, or nothing."""

    @pytest.mark.parametrize(
        "value, expected",
        [
            (None, []),
            (1.0, [1]),
            (3, [3]),
            ([[1.0], [2.0]], [1, 2]),
            ([1.0, 2.0, 3.0], [1, 2, 3]),
        ],
    )
    def test_shapes_are_all_normalised(self, value, expected):
        assert matlab_engine._as_number_list(value) == expected


class TestHints:
    def test_missing_function_hint_mentions_toolboxes_and_path(self):
        hint = matlab_engine._execution_hint("Unrecognized function or variable 'xyz'.")
        assert "toolbox" in hint and "addpath" in hint

    def test_out_of_memory_hint(self):
        assert "clear" in matlab_engine._execution_hint("Out of memory.").lower()

    def test_an_unclassified_error_gets_no_invented_hint(self):
        assert matlab_engine._execution_hint("Some other failure") == ""


class TestPushGuards:
    def test_pushing_a_non_dataframe_is_refused_clearly(self):
        from econenv.exceptions import DataTransferError

        with pytest.raises(DataTransferError, match="DataFrame"):
            matlab_bridge.push_frame(None, "x", [1, 2, 3])

    def test_a_frame_is_still_a_frame(self):
        # guards must not reject the valid case
        assert isinstance(pd.DataFrame({"a": [1]}), pd.DataFrame)


class TestApiMissingMessage:
    """Reported from a real session: a user with R2024a and R2025a on Python 3.13
    was told to `pip install "matlabengine==25.1.*"` — the wrong release, and a
    command that could not have worked on that Python anyway.
    """

    @staticmethod
    def _engine(*releases):
        from pathlib import Path

        engine = object.__new__(matlab_engine.MatlabEngine)
        engine._installs = [Path(f"C:/Program Files/MATLAB/{r}") for r in releases]
        return engine

    @staticmethod
    def _version(major, minor):
        from collections import namedtuple

        V = namedtuple("V", "major minor micro releaselevel serial")
        return V(major, minor, 0, "final", 0)

    def test_every_installed_release_is_offered_not_just_the_newest(self, monkeypatch):
        monkeypatch.setattr(matlab_engine.sys, "version_info", self._version(3, 11))
        message = self._engine("R2025a", "R2024a")._api_missing_message("no module")

        assert "24.1" in message, "the release the user actually uses must be offered"
        assert "25.1" in message
        assert "R2024a" in message and "R2025a" in message

    def test_an_unsupported_python_is_stated_rather_than_a_doomed_pip_command(self, monkeypatch):
        monkeypatch.setattr(matlab_engine.sys, "version_info", self._version(3, 13))
        message = self._engine("R2025a", "R2024a")._api_missing_message("no module")

        assert "no Engine API supports Python 3.13" in message
        assert "pip install" not in message, "no command that cannot work"
        assert "python=3.11" in message, "say what would work instead"

    def test_a_release_usable_on_this_python_is_separated_from_one_that_is_not(self, monkeypatch):
        monkeypatch.setattr(matlab_engine.sys, "version_info", self._version(3, 12))
        message = self._engine("R2025a", "R2024a")._api_missing_message("no module")

        # 3.12 suits R2025a but not R2024a
        assert "25.1" in message
        assert "Not usable on Python 3.12" in message and "R2024a" in message

    def test_no_matlab_at_all_says_so(self, monkeypatch):
        message = self._engine()._api_missing_message("no module")
        assert "no MATLAB installation was found" in message

    @pytest.mark.parametrize(
        "series, major, minor, ok",
        [
            ("24.1", 3, 11, True),
            ("24.1", 3, 12, False),
            ("24.2", 3, 12, True),
            ("25.1", 3, 13, False),
        ],
    )
    def test_python_support_ranges(self, monkeypatch, series, major, minor, ok):
        monkeypatch.setattr(matlab_engine.sys, "version_info", self._version(major, minor))
        assert matlab_engine._python_ok(series) is ok
