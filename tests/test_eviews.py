"""EViews adapter regressions.

None of these need EViews installed: they pin the pure-Python decisions the
adapter makes *before* it talks to COM. The COM behaviour they encode was
measured against EViews 13 on Windows.
"""

import logging
import os
import pathlib
import re

import pytest

from econenv import discovery
from econenv.engines import eviews_engine
from econenv.results import Figure


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

        # A numeric column is right-aligned, so the header and the value share a
        # right edge rather than a left one — that is what makes decimal points
        # line up down the column, and it is how EViews prints the table itself.
        header_end = lines[2].index("Coefficient") + len("Coefficient")
        value_end = lines[3].index("5.044621") + len("5.044621")
        assert header_end == value_end

    def test_numbers_in_a_column_line_up_on_the_decimal_point(self):
        """Reported: the OLS output table looked ragged.

        The renderer left-aligned every cell, so a negative coefficient pushed
        its digits one place across and the column read as crooked.
        """
        grid = [
            ["Variable", "Coefficient", "t-Statistic"],
            ["C", "1.546745", "41.31799"],
            ["X1", "-0.518894", "-15.07583"],
        ]
        lines = eviews_engine._render_grid(grid).splitlines()
        ends = [line.index(".") for line in lines[1:]]
        assert len(set(ends)) == 1, f"decimal points at differing columns: {lines}"

    def test_each_block_is_sized_on_its_own_columns(self):
        """A regression output is several tables stacked, not one.

        The coefficient block has five columns; the summary block below has
        four, and its labels are long. Sizing them together padded the
        coefficients to fit "Mean dependent var".
        """
        grid = [
            ["Variable", "Coefficient", "Std. Error"],
            ["C", "1.546745", "0.037435"],
            ["", "", ""],
            ["R-squared", "0.984702", "Mean dependent var"],
        ]
        lines = eviews_engine._render_grid(grid).splitlines()
        # the coefficient row must not be padded out to the width of the
        # summary block's long label
        assert len(lines[1]) < len(lines[3])


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


class TestGraphViews:
    """Plots made the EViews way produced nothing at all.

    `x.line` is a *view*: it freezes into a graph, not a table, and leaves no
    named graph object behind — so the end-of-cell sweep over
    `@wlookup("*","graph")` never saw it and the figure was discarded.
    """

    @staticmethod
    def _engine(names):
        engine = object.__new__(eviews_engine.EViewsEngine)
        engine._emitted_graphs = set()
        engine.graph_names = lambda: list(names)
        engine.capture_graph = lambda name: Figure(
            data=b"PNG", mimetype="image/png", engine="eviews", name=name
        )
        return engine

    def test_a_graph_is_shown_once_not_under_every_later_cell(self):
        engine = self._engine(["G1"])

        first = engine._collect_new_graphs()
        second = engine._collect_new_graphs()

        assert [f.name for f in first] == ["G1"]
        assert second == [], "an existing graph must not reappear below the next cell"

    def test_an_explicit_request_always_exports(self):
        engine = self._engine(["G1"])
        engine._collect_new_graphs()

        again = engine._collect_new_graphs(["G1"])

        assert [f.name for f in again] == ["G1"]

    @pytest.mark.parametrize("line", ["x.line", "x.hist", "eq1.resids"])
    def test_plotting_views_reach_the_capture_path(self, line):
        """They must be recognised as views, or they are simply run and lost."""
        assert eviews_engine._view_expression(line) == line


class TestGraphCommands:
    """`line x` is a command, not a view and not an object.

    EViews rejects `freeze(t) line x` with "LINE is not a view", and a bare
    `line x` leaves nothing in the workfile — verified against EViews 13, where
    the graph listing was identical before and after. So it is rewritten to the
    object form, which can be exported.
    """

    @pytest.mark.parametrize(
        "line, expected",
        [
            ("line x", ".line x"),
            ("scat x y", ".scat x y"),
            ("bar(l) x", ".bar(l) x"),
            ("  xyline a b  ", ".xyline a b"),
            ("LINE X", ".LINE X"),
            ("boxplot x", ".boxplot x"),
        ],
    )
    def test_graph_commands_become_object_form(self, line, expected):
        assert eviews_engine._graph_command(line) == expected

    @pytest.mark.parametrize(
        "line",
        [
            "series x = nrnd",
            "wfcreate u 100",
            "equation eq1.ls y c x",
            "delete x",
            "linear x",  # starts with "line" but is not the line command
            "line",  # no series to plot
        ],
    )
    def test_ordinary_commands_are_left_alone(self, line):
        assert eviews_engine._graph_command(line) is None


class TestViewObjectTypes:
    """A view freezes into a table, a graph, a text object or a spool.

    Only the first two were handled, so `eq1.representations` (text) and
    `g2.coint(e)` (spool — the Johansen test) produced nothing at all. Verified
    against EViews 13 with `@wlookup`.
    """

    @staticmethod
    def _engine(object_type, text=None, table=None):
        engine = object.__new__(eviews_engine.EViewsEngine)
        engine._emitted_graphs = set()
        engine.log = logging.getLogger("test")
        engine._run_command = lambda line: None
        engine._object_type = lambda name: object_type
        engine._read_table = lambda name: table
        engine._read_text_object = lambda name: text
        engine.capture_graph = lambda name: None
        return engine

    def test_a_text_view_is_read_not_dropped(self):
        engine = self._engine("text", text="Estimation Command:\nLS Y C X")

        captured = engine._capture_view("eq1.representations")

        assert captured is not None, "a text view must not vanish"
        assert captured[0] == "text"
        assert "LS Y C X" in captured[1]

    def test_a_spool_view_is_read(self):
        engine = self._engine("spool", text="Johansen Cointegration Test")

        captured = engine._capture_view("g2.coint(e)")

        assert captured[0] == "text"
        assert "Johansen" in captured[1]

    def test_an_unreadable_view_returns_none_rather_than_pretending(self):
        engine = self._engine(None)
        assert engine._capture_view("eq1.mystery") is None


class TestCommandCatalogue:
    """The catalogue exists because GUI users cannot guess commands.

    It is also the source of the documentation page, so the two cannot drift.
    """

    def test_every_entry_is_complete(self):
        from econenv.engines import eviews_commands as catalogue

        for command in catalogue.COMMANDS:
            assert command.command.strip(), "a command needs a name"
            assert command.gui.strip(), f"{command.command}: no GUI path"
            assert command.does.strip(), f"{command.command}: no description"
            assert command.example.strip(), f"{command.command}: no example"
            assert command.category in catalogue.CATEGORIES, (
                f"{command.command}: unknown category {command.category!r}"
            )

    def test_every_category_has_commands(self):
        from econenv.engines import eviews_commands as catalogue

        empty = [name for name in catalogue.CATEGORIES if not catalogue.by_category(name)]
        assert not empty, f"categories documented but empty: {empty}"

    @pytest.mark.parametrize(
        "term, expected",
        [
            ("cointegration", "coint"),
            ("garch", "arch"),
            ("unit root", "uroot"),
            ("scatter", "scat"),
            ("fixed effects", "cx=f"),
            ("forecast", "forecast"),
        ],
    )
    def test_a_researcher_can_find_it_by_the_word_they_would_use(self, term, expected):
        """The search has to work on the vocabulary of the field, not of EViews."""
        from econenv.engines import eviews_commands as catalogue

        matches = catalogue.search(term)
        assert matches, f"nothing found for {term!r}"
        blob = " ".join(m.command + m.example for m in matches)
        assert expected in blob

    def test_search_ranks_the_command_name_above_the_prose(self):
        from econenv.engines import eviews_commands as catalogue

        matches = catalogue.search("uroot")
        assert "uroot" in matches[0].command

    def test_the_docs_page_matches_the_catalogue(self):
        """Generated, not hand-written — so it cannot describe a command wrongly.

        Regenerate with: python scripts/gen_eviews_docs.py
        """
        import importlib.util

        root = pathlib.Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location(
            "gen_eviews_docs", root / "scripts" / "gen_eviews_docs.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        page = root / "docs" / "engines" / "eviews-commands.md"
        assert page.exists(), "the command reference is missing"
        assert page.read_text(encoding="utf-8") == module.render(), (
            "docs/engines/eviews-commands.md is out of date — "
            "run: python scripts/gen_eviews_docs.py"
        )


class TestRpy2Reporting:
    """Installed, importable and usable are three states, not two.

    A `find_spec` check reported PASS for an rpy2 that raises on import — which
    on a real machine told the user to install what they already had, while the
    load banner in the same session said it was missing.
    """

    def test_broken_rpy2_is_reported_as_broken_not_missing(self, monkeypatch):
        from econenv import diagnostics
        from econenv.engines import r_engine

        monkeypatch.setattr(r_engine, "_RPY2_IMPORTABLE", False)
        monkeypatch.setattr(
            r_engine,
            "_RPY2_ERROR",
            "ImportError: cannot import name 'SexpVectorCCompatibleAbstract'",
        )
        monkeypatch.setattr(
            r_engine.importlib.util
            if hasattr(r_engine, "importlib")
            else diagnostics.importlib.util,
            "find_spec",
            lambda name: object() if name == "rpy2" else None,
        )

        checks = [c for c in diagnostics.check_r() if c.name == "rpy2"]
        assert checks, "doctor must report on rpy2"
        check = checks[0]
        assert check.status is diagnostics.Status.WARN
        assert "installed but cannot be imported" in check.detail
        assert "SexpVectorCCompatibleAbstract" in check.detail
        assert "conda" in check.fix, "the fix must say how to actually repair it"

    def test_absent_rpy2_is_skipped_not_an_error(self, monkeypatch):
        from econenv import diagnostics
        from econenv.engines import r_engine

        monkeypatch.setattr(r_engine, "_RPY2_IMPORTABLE", False)
        monkeypatch.setattr(r_engine, "_RPY2_ERROR", None)
        monkeypatch.setattr(diagnostics.importlib.util, "find_spec", lambda name: None)

        check = next(c for c in diagnostics.check_r() if c.name == "rpy2")
        assert check.status is diagnostics.Status.SKIP
        assert "subprocess backend" in check.detail


class TestViewsWithSpaceArguments:
    """A whole family of hypothesis tests was silently producing nothing.

    `_VIEW_RE` anchors at the end of the parenthesised options, so
    `eq1.wald c(2)=0` did not look like a view. It was run as a bare command,
    which displays in EViews' own window and returns nothing here — and silence
    is the one outcome this adapter is not allowed to have.
    """

    @pytest.mark.parametrize(
        "line",
        [
            "eq1.wald c(2)=0",
            "eq1.testadd x3",
            "eq1.testdrop x2",
            "eq1.chow 60",
        ],
    )
    def test_a_test_view_with_arguments_is_recognised(self, line):
        assert eviews_engine._view_expression(line) == line

    @pytest.mark.parametrize(
        "line",
        [
            "eq1.ls y c x1 x2",  # a proc: re-estimates, must not be frozen
            "equation eq1.ls y c x",
            "series x = nrnd",
            "wfcreate u 100",
            "eq1.forecast yf",  # a proc that creates a series
        ],
    )
    def test_a_proc_is_not_mistaken_for_a_view(self, line):
        """Freezing a proc would give a display command a side effect."""
        assert eviews_engine._view_expression(line) is None

    def test_the_plain_forms_still_work(self):
        assert eviews_engine._view_expression("eq1.output") == "eq1.output"
        assert eviews_engine._view_expression("x1.uroot(adf)") == "x1.uroot(adf)"

    def test_the_allow_list_is_used_rather_than_a_loose_pattern(self):
        """An unknown name with arguments stays a command, not a view."""
        assert eviews_engine._view_expression("eq1.notaview something") is None
