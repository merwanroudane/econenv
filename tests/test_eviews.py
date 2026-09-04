"""EViews adapter regressions.

None of these need EViews installed: they pin the pure-Python decisions the
adapter makes *before* it talks to COM. The COM behaviour they encode was
measured against EViews 13 on Windows.
"""

import os
import re

import pytest

from econenv import discovery
from econenv.engines import eviews_engine


# --------------------------------------------------------------------------- #
# 0.1.1 regressions — every one of these shipped broken in 0.1.0
# --------------------------------------------------------------------------- #
class TestViewCapture:
    """`%%eviews eq1.output` came back empty because Run returns no text."""

    @pytest.mark.parametrize(
        "line, expected",
        [
            ("eq1.output", "eq1.output"),
            ("x.stats", "x.stats"),
            ("eq1.resids", "eq1.resids"),
            ("show eq1", "eq1"),
            ("SHOW eq1.output", "eq1.output"),
            ("eq1.output(p)", "eq1.output(p)"),
        ],
    )
    def test_display_views_are_recognised(self, line, expected):
        assert eviews_engine._view_expression(line) == expected

    @pytest.mark.parametrize(
        "line",
        [
            "equation eq1.ls y c x",  # an action: arguments follow the view name
            "series x = nrnd",
            "wfcreate u 100",
            "eq1.makeresids r1",
            "delete tab1",
        ],
    )
    def test_actions_are_not_mistaken_for_views(self, line):
        """Freezing an action would silently skip it — the dangerous failure."""
        assert eviews_engine._view_expression(line) is None

    def test_grid_renders_like_eviews_prints_it(self):
        grid = [
            ["Dependent Variable: Y", "", "", ""],
            ["", "", "", ""],
            ["Variable", "Coefficient", "Std. Error", "Prob."],
            ["C", "5.044621", "0.105875", "0.0000"],
        ]
        lines = eviews_engine._render_grid(grid).splitlines()
        assert lines[0] == "Dependent Variable: Y"  # no trailing padding
        assert lines[1] == ""
        assert lines[3].startswith("C ")
        assert "5.044621" in lines[3]
        # columns line up between the header and the data row
        assert lines[2].index("Coefficient") == lines[3].index("5.044621")


class TestGraphPath:
    def test_graph_export_uses_native_separators(self, tmp_path):
        r"""EViews reads "C:/Users/..." as the drive-relative path "C:Users\..."

        It then writes nowhere and reports success, so every captured figure
        came back None. Verified against EViews 13: backslashes work, forward
        slashes do not.
        """
        rendered = eviews_engine._native(tmp_path / "g.png")
        if os.name == "nt":
            assert "/" not in rendered
        assert rendered.endswith("g.png")


class TestProgID:
    """EViews registers `EViews.Manager.14`, never `EViews14.Manager`.

    EconEnv looked for the second form, found nothing, and therefore told users
    to pin a ProgID that exists on no machine — in the doctor hint, the start
    error, the README and three doc pages.
    """

    def test_versioned_candidates_use_the_registered_form(self, monkeypatch):
        tried = []
        monkeypatch.setattr(discovery, "IS_WINDOWS", True)
        monkeypatch.setattr(discovery, "_read_registry", lambda *a, **k: None)
        monkeypatch.setattr(discovery, "_clsid_for", lambda progid: tried.append(progid) or None)

        discovery.eviews_progids()

        assert "EViews.Manager" in tried
        assert "EViews.Manager.14" in tried
        assert not [p for p in tried if re.fullmatch(r"EViews\d+\.Manager", p)]

    def test_progid_target_is_silent_off_windows(self, monkeypatch):
        monkeypatch.setattr(discovery, "IS_WINDOWS", False)
        assert discovery.eviews_progid_target() is None

    def test_progid_target_is_none_when_unregistered(self, monkeypatch):
        monkeypatch.setattr(discovery, "IS_WINDOWS", True)
        monkeypatch.setattr(discovery, "_clsid_for", lambda progid: None)
        assert discovery.eviews_progid_target("EViews.Manager.99") is None
