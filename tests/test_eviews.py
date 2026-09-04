"""EViews adapter regressions.

None of these need EViews installed: they pin the pure-Python decisions the
adapter makes *before* it talks to COM. The COM behaviour they encode was
measured against EViews 13 on Windows.
"""

import os

import pytest

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
