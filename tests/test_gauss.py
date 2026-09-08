"""GAUSS: discovery, the CLI contract, transfer rules and the catalogue.

Everything here runs without GAUSS installed. The round trips against a real
installation are in ``test_integration.py`` and skip when it is absent.

The contract these tests encode was established by running GAUSS 26.1.1, not
read from documentation — two of the design assumptions were wrong, and these
tests are what stops them coming back.
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd
import pytest

from econenv.bridges import gauss_bridge
from econenv.engines import _gauss_cli, gauss_commands
from econenv.engines.gauss_engine import _version_key, find_gauss
from econenv.exceptions import DataTransferError


# --------------------------------------------------------------------------- #
# the command line contract
# --------------------------------------------------------------------------- #
class TestCliContract:
    """Verified against GAUSS 26.1.1: `tgauss -nb -nj -x -b program.gss`."""

    def test_the_executable_names_include_tgauss(self):
        """The design document said `engauss`; the installation ships `tgauss`."""
        assert _gauss_cli.CLI_NAMES[0] == "tgauss"
        assert "engauss" in _gauss_cli.CLI_NAMES, "older installations may still use it"

    @pytest.mark.parametrize(
        "code, stage",
        [(0, "ok"), (3, "translator"), (7, "compile"), (15, "runtime")],
    )
    def test_exit_codes_are_named(self, code, stage):
        assert _gauss_cli.EXIT_MEANING[code] == stage

    def test_a_compile_error_says_that_nothing_ran(self):
        """GAUSS compiles the whole program first, so a late typo voids it all.

        Without saying this, a user sees a cell that printed nothing and looks
        for the bug in the wrong place.
        """
        backend = object.__new__(_gauss_cli.GaussCliBackend)
        backend._carried = {}
        backend._offset = 0
        output = "error G0025 : Undefined symbol: 'nope'\n\tC:\\Temp\\econenv_cell.gss, line 2\n"
        _, error = backend._interpret(output, 7, "print 1;\nx = nope;")
        assert "compile error" in error
        assert "nothing in this cell ran" in error
        assert "G0025" in error

    def test_the_reported_line_is_the_users_line_not_the_wrappers(self):
        """The wrapper prepends `load` statements; GAUSS counts those too."""
        backend = object.__new__(_gauss_cli.GaussCliBackend)
        backend._carried = {}
        backend._offset = 4  # four lines of restored workspace
        output = "error G0520 : bad\n\tC:\\Temp\\cell.gss, line 6\n"
        _, error = backend._interpret(output, 15, "")
        assert "at line 2 of the cell" in error

    def test_the_temporary_path_never_reaches_the_user(self):
        backend = object.__new__(_gauss_cli.GaussCliBackend)
        backend._carried = {}
        backend._offset = 0
        output = "error G0025 : nope\n\tC:\\Temp\\econenv_cell.gss, line 1\n"
        text, error = backend._interpret(output, 7, "")
        assert "econenv_cell.gss" not in error
        assert "econenv_cell.gss" not in text

    def test_the_error_is_not_repeated_in_the_output(self):
        """It is reported once, as an error — not twice, once as output."""
        backend = object.__new__(_gauss_cli.GaussCliBackend)
        backend._carried = {}
        backend._offset = 0
        output = "printed first\nProgram execute failed\nerror G0520 : bad\n"
        text, error = backend._interpret(output, 15, "")
        assert text == "printed first"
        assert "G0520" in error

    def test_a_reserved_name_is_explained(self):
        backend = object.__new__(_gauss_cli.GaussCliBackend)
        backend._carried = {}
        backend._offset = 0
        output = "error G0276 : Illegal use of reserved word 'vec'\n"
        _, error = backend._interpret(output, 7, "")
        assert "'vec'" in error
        assert "built-in" in error


class TestAssignedNames:
    """Which names a cell should carry into the next one."""

    def test_top_level_assignments_are_carried(self):
        assert _gauss_cli._assigned_names("x = 5;\ny = rndn(3,1);") == ["x", "y"]

    def test_a_procedures_locals_are_not(self):
        """They exist only inside the proc; saving them fails to compile."""
        code = "proc (0) = f(a);\n    local nr;\n    nr = rows(a);\nendp;\nz = 1;"
        assert _gauss_cli._assigned_names(code) == ["z"]

    def test_comparisons_are_not_assignments(self):
        assert _gauss_cli._assigned_names("if x == 1;\n    y = 2;\nendif;") == ["y"]

    def test_duplicates_appear_once(self):
        assert _gauss_cli._assigned_names("x = 1;\nx = 2;") == ["x"]


# --------------------------------------------------------------------------- #
# discovery
# --------------------------------------------------------------------------- #
class TestDiscovery:
    @pytest.mark.parametrize(
        "name, expected",
        [("gauss26", (26, 0)), ("gauss24", (24, 0)), ("GAUSS 25", (25, 0)), ("gauss22.1", (22, 1))],
    )
    def test_the_version_is_read_from_the_directory_name(self, name, expected):
        assert _version_key(pathlib.Path(name)) == expected

    def test_newest_sorts_first(self):
        paths = [pathlib.Path("gauss24"), pathlib.Path("gauss26"), pathlib.Path("gauss25")]
        assert sorted(paths, key=_version_key, reverse=True)[0].name == "gauss26"

    def test_discovery_returns_a_list_without_raising(self):
        """It must be safe to call on a machine with no GAUSS at all."""
        assert isinstance(find_gauss(), list)


# --------------------------------------------------------------------------- #
# transfer rules
# --------------------------------------------------------------------------- #
class FakeBackend:
    def __init__(self, session):
        self.session = session
        self.programs = []
        self.remembered = {}

    def execute(self, code, timeout=600.0, carry=True):
        self.programs.append(code)
        return "", None

    def remember(self, name, kind):
        self.remembered[name] = kind


class FakeEngine:
    name = "gauss"

    def __init__(self, session):
        self._backend = FakeBackend(session)


class TestPushRules:
    def test_none_is_refused_with_the_alternative(self):
        engine = FakeEngine(pathlib.Path("."))
        with pytest.raises(DataTransferError) as caught:
            gauss_bridge.push_value(engine, "x", None)
        assert "no equivalent of None" in str(caught.value)
        assert "nan" in str(caught.value).lower()

    def test_a_gauss_builtin_name_is_refused_before_gauss_sees_it(self):
        """`vec` is a GAUSS function; assigning to it is a G0276 compile error."""
        engine = FakeEngine(pathlib.Path("."))
        with pytest.raises(DataTransferError) as caught:
            gauss_bridge.push_value(engine, "vec", 1.0)
        message = str(caught.value)
        assert "built-in" in message
        assert "another name" in message, "offer a way forward"

    def test_the_builtin_list_covers_the_names_a_researcher_reaches_for(self):
        for name in ("vec", "rows", "cols", "ones", "sumc", "meanc"):
            assert name in gauss_bridge.COMMON_BUILTINS

    def test_more_than_two_dimensions_is_refused(self):
        engine = FakeEngine(pathlib.Path("."))
        with pytest.raises(DataTransferError) as caught:
            gauss_bridge.push_value(engine, "a", np.zeros((2, 2, 2)))
        assert "3 dimensions" in str(caught.value)

    def test_nan_becomes_a_gauss_missing_value(self):
        assert gauss_bridge._literal(float("nan")) == "miss(0, 0)"

    def test_a_finite_number_is_written_exactly(self):
        assert float(gauss_bridge._literal(0.1)) == 0.1


class TestPathQuoting:
    def test_backslashes_become_forward_slashes(self):
        """A backslash is an escape inside a GAUSS string."""
        quoted = gauss_bridge._gauss_path(pathlib.PurePath(r"C:\Temp\x.csv"))
        assert "\\" not in quoted
        assert quoted.endswith("x.csv")


class TestReadingValues:
    @pytest.mark.parametrize(
        "cell, expected",
        [("1.5", 1.5), ("-2", -2.0), ("", float("nan")), (".", float("nan"))],
    )
    def test_a_missing_field_reads_as_nan(self, cell, expected):
        value = gauss_bridge._to_float(cell)
        if np.isnan(expected):
            assert np.isnan(value)
        else:
            assert value == expected


class TestFrameConversion:
    def test_text_columns_are_named_rather_than_dropped_silently(self):
        """A regression on a frame that lost a column without saying so is worse
        than one that refuses."""
        engine = FakeEngine(pathlib.Path("."))
        frame = pd.DataFrame({"x": [1.0, 2.0], "label": ["a", "b"]})
        report = gauss_bridge.push_frame(engine, "d", frame)
        text = " ".join(n.message for n in report.notes)
        assert "label" in text

    def test_a_frame_with_no_numeric_columns_is_refused(self):
        engine = FakeEngine(pathlib.Path("."))
        with pytest.raises(DataTransferError) as caught:
            gauss_bridge.push_frame(engine, "d", pd.DataFrame({"a": ["x", "y"]}))
        assert "only numbers" in str(caught.value)


# --------------------------------------------------------------------------- #
# the catalogue
# --------------------------------------------------------------------------- #
class TestGaussCatalogue:
    def test_every_command_has_a_category_that_exists(self):
        unknown = {c.category for c in gauss_commands.COMMANDS} - set(gauss_commands.CATEGORIES)
        assert not unknown

    def test_names_are_unique(self):
        names = [c.name for c in gauss_commands.COMMANDS]
        assert len(names) == len(set(names))

    def test_every_command_has_a_runnable_example(self):
        assert all(c.example.strip() for c in gauss_commands.COMMANDS)

    @pytest.mark.parametrize(
        "term, expected",
        [
            ("regression", "ols"),
            ("listwise", "packr"),
            ("cbind", "~"),
            ("missing", "miss"),
            ("loop", "do while"),
            ("pvalue", "cdftc"),
        ],
    )
    def test_search_finds_what_a_researcher_would_type(self, term, expected):
        assert expected in [c.name for c in gauss_commands.find(term)]

    def test_the_operators_are_catalogued_since_they_cannot_be_guessed(self):
        """`~` and `|` have no equivalent in the other engines' syntax."""
        for operator in ("~", "|", "/", ".*"):
            assert gauss_commands.get(operator) is not None

    def test_the_semicolon_rule_is_documented(self):
        entry = gauss_commands.get(";")
        assert entry is not None and "semicolon" in entry.does.lower()

    def test_nothing_matches_returns_empty(self):
        assert gauss_commands.find("zzzz") == []

    def test_library_requirements_are_stated(self):
        entry = gauss_commands.get("dfgls")
        assert entry is not None and entry.library != gauss_commands.BASE


class TestGeneratedDocs:
    def test_the_docs_page_matches_the_catalogue(self):
        """Regenerate with: python scripts/gen_gauss_docs.py"""
        import importlib.util

        root = pathlib.Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location(
            "gen_gauss_docs", root / "scripts" / "gen_gauss_docs.py"
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules["gen_gauss_docs"] = module
        spec.loader.exec_module(module)

        page = root / "docs" / "engines" / "gauss-commands.md"
        assert page.exists(), "the GAUSS command reference is missing"
        assert page.read_text(encoding="utf-8") == module.render(), (
            "docs/engines/gauss-commands.md is out of date — run: python scripts/gen_gauss_docs.py"
        )


class TestBridgeResource:
    def test_the_gauss_side_helper_ships_with_the_package(self):
        helper = gauss_bridge._helper()
        assert "proc (0) = econenv_write" in helper
        assert "17" in helper, "the precision the writer depends on"

    def test_it_writes_seventeen_digits_not_gauss_default(self):
        """csvWriteM writes ~15, which moves a double by ~3e-15 per round trip
        and would put GAUSS out of step with the other engines."""
        assert "%*.*e" in gauss_bridge._helper()


class TestGraphics:
    """Plot capture, and the two traps found by running it."""

    def test_a_struct_is_never_carried_between_cells(self):
        """GAUSS cannot `save` a struct — G0514, a compile error.

        A plotting cell declares `struct plotControl p;` then assigns to `p`,
        which looks exactly like an ordinary top-level assignment. Saving it
        made every plotting cell fail to run at all.
        """
        code = 'struct plotControl p;\np = plotGetDefaults("xy");\nplotXY(p, x, y);\nz = 1;'
        assert _gauss_cli._assigned_names(code) == ["z"]

    def test_several_structs_on_one_line_are_all_excluded(self):
        assert _gauss_cli._struct_names("struct myType a, b, c;") == {"a", "b", "c"}

    @pytest.mark.parametrize(
        "code, draws",
        [
            ("plotXY(p, x, y);", True),
            ("plotScatter(p, x, y);", True),
            ("plotHist(p, x, 20);", True),
            ("z = 1 + 1;", False),
            ('print "no plot";', False),
        ],
    )
    def test_only_a_plotting_cell_is_instrumented(self, code, draws):
        """Saving unconditionally would re-emit the last plot under every cell."""
        from econenv.engines.gauss_engine import _PLOT_CALL

        assert bool(_PLOT_CALL.search(code)) is draws

    def test_raster_and_vector_use_different_units(self):
        """plotSave takes pixels for png and inches for svg/pdf.

        Passing the vector numbers to a png produced a 12x9 pixel thumbnail,
        which is a confusing way to fail.
        """
        from econenv.engines.gauss_engine import _RASTER_PIXELS, _VECTOR_INCHES

        assert _VECTOR_INCHES[0] < 100, "inches"
        assert _RASTER_PIXELS[0] > 100, "pixels"

    def test_every_graphics_format_has_a_mime_type(self):
        from econenv.engines.gauss_engine import _GRAPHICS_MIME

        assert _GRAPHICS_MIME["svg"] == "image/svg+xml"
        assert _GRAPHICS_MIME["png"] == "image/png"
        assert _GRAPHICS_MIME["pdf"] == "application/pdf"


class TestConfiguration:
    def test_gauss_is_a_known_config_section(self):
        """`%econ config gauss.home` is documented, so it has to be settable."""
        from econenv import config

        assert "gauss" in config.DEFAULTS

    @pytest.mark.parametrize(
        "key", ["home", "backend", "graphics", "width", "height", "timeout", "vectors"]
    )
    def test_the_documented_options_exist(self, key):
        from econenv import config

        assert key in config.DEFAULTS["gauss"]


class TestNativeBackendReporting:
    """The native backend is blocked by a missing product, not unwritten code.

    A desktop GAUSS installation contains no `mteng` library and its `gauss.dll`
    exports no `GAUSS_*` symbols, so there is nothing to bind to. The two cases
    are worth telling apart: absent, or present and unsupported.
    """

    def test_the_library_search_is_safe_on_a_machine_without_it(self):
        from econenv.engines.gauss_engine import find_engine_library

        assert find_engine_library() is None or find_engine_library().exists()

    def test_asking_for_native_is_reported_not_silently_downgraded(self, monkeypatch):
        from econenv.engines import gauss_engine

        monkeypatch.setattr(gauss_engine._config, "get_option", lambda *a, **k: "native")
        monkeypatch.setattr(gauss_engine, "find_engine_library", lambda: None)
        engine = object.__new__(gauss_engine.GaussEngine)
        assert engine._requested_backend() == "native-absent"

    def test_a_present_engine_is_distinguished_from_an_absent_one(self, monkeypatch):
        from econenv.engines import gauss_engine

        monkeypatch.setattr(gauss_engine._config, "get_option", lambda *a, **k: "native")
        monkeypatch.setattr(gauss_engine, "find_engine_library", lambda: pathlib.Path("mteng.dll"))
        engine = object.__new__(gauss_engine.GaussEngine)
        assert engine._requested_backend() == "native-present"

    def test_auto_resolves_to_the_backend_that_exists(self, monkeypatch):
        from econenv.engines import gauss_engine

        monkeypatch.setattr(gauss_engine._config, "get_option", lambda *a, **k: "auto")
        engine = object.__new__(gauss_engine.GaussEngine)
        assert engine._requested_backend() == "cli"


class TestProceduresCarry:
    """A procedure written in one cell is callable in the next.

    The design forbids rebuilding a session by replaying earlier cells, and
    rightly — re-running `x = x + 1;` or a file write would change the answer.
    But a `proc ... endp;` definition is *pure*: declaring it computes nothing
    and touches nothing, so re-declaring it in a later cell is safe and
    idempotent. That is what makes carrying definitions legitimate where
    replaying statements is not.
    """

    def test_a_procedure_is_recognised(self):
        code = "proc (1) = sq(a);\n    retp(a .* a);\nendp;"
        assert set(_gauss_cli._procedures(code)) == {"sq"}

    def test_several_procedures_in_one_cell(self):
        code = (
            "proc (1) = sq(a);\n    retp(a .* a);\nendp;\n"
            "proc (2) = two(a, b);\n    retp(a, b);\nendp;"
        )
        assert set(_gauss_cli._procedures(code)) == {"sq", "two"}

    def test_the_form_without_a_return_count(self):
        assert set(_gauss_cli._procedures("proc show(a);\n    print a;\nendp;")) == {"show"}

    def test_ordinary_code_defines_nothing(self):
        assert _gauss_cli._procedures("x = 1;\nprint x;") == {}

    def test_a_cell_that_redefines_does_not_get_the_old_one_too(self):
        """GAUSS rejects two definitions of the same name in one program."""
        backend = object.__new__(_gauss_cli.GaussCliBackend)
        backend._procs = {"sq": "proc (1) = sq(a);\n    retp(a);\nendp;"}
        block = backend._procedure_block("proc (1) = sq(a);\n    retp(a + 1);\nendp;")
        assert block == "", "the stored definition must be left out"

    def test_a_stored_procedure_is_emitted_for_a_cell_that_does_not_redefine(self):
        backend = object.__new__(_gauss_cli.GaussCliBackend)
        stored = "proc (1) = sq(a);\n    retp(a);\nendp;"
        backend._procs = {"sq": stored}
        assert backend._procedure_block("print sq(2);") == stored

    def test_definitions_are_dropped_when_the_session_stops(self):
        backend = object.__new__(_gauss_cli.GaussCliBackend)
        backend._session = None
        backend._carried = {"x": "matrix"}
        backend._procs = {"sq": "..."}
        backend.stop()
        assert backend._procs == {} and backend._carried == {}


class TestExplicitPlotSave:
    """Reported with a screenshot: a cell calling plotSave showed a broken image.

    EconEnv was appending its own plotSave on top of the user's, so the figure
    was written twice and the notebook showed EconEnv's copy rather than the
    file the researcher had named.
    """

    @staticmethod
    def _engine(graphics="svg"):
        from econenv.engines import gauss_engine

        engine = object.__new__(gauss_engine.GaussEngine)
        engine._backend = type("B", (), {"session": pathlib.Path(".")})()
        engine._graphics_format = lambda: graphics
        return engine

    def test_an_explicit_save_is_not_duplicated(self):
        engine = self._engine()
        code = 'plotXY(x, y);\nplotSave("C:/Users/HP/Desktop/out.svg", 800 | 600, "px");'
        target, program = engine._with_graphics(code)
        assert program is code, "the cell must be sent unchanged"
        assert target == pathlib.Path("C:/Users/HP/Desktop/out.svg")

    def test_the_users_file_is_what_gets_displayed(self, tmp_path):
        """Not EconEnv's own copy of the same plot."""
        engine = self._engine()
        target = tmp_path / "mine.svg"
        target.write_bytes(b"<svg/>")
        figures = engine._read_figure(target, keep=True)
        assert figures[0].name == "mine"
        assert target.exists(), "a file the researcher named must survive"

    def test_econenvs_own_capture_is_cleaned_up(self, tmp_path):
        engine = self._engine()
        target = tmp_path / "econenv_plot_abc.svg"
        target.write_bytes(b"<svg/>")
        engine._read_figure(target, keep=False)
        assert not target.exists(), "a temporary capture must not be left behind"

    def test_a_multi_line_plotsave_is_recognised(self):
        """It was written across four lines in the report."""
        from econenv.engines.gauss_engine import _PLOT_SAVE

        code = 'plotSave(\n    "C:/Users/HP/Desktop/gauss_test.svg",\n    800 | 600,\n    "px"\n);'
        assert _PLOT_SAVE.search(code).group(1).endswith("gauss_test.svg")

    def test_a_cell_without_a_save_still_gets_one(self):
        engine = self._engine()
        target, program = engine._with_graphics("plotXY(x, y);")
        assert "plotSave" in program
        assert target is not None and "econenv_plot" in target.name

    @pytest.mark.parametrize(
        "extension, mimetype",
        [
            ("svg", "image/svg+xml"),
            ("png", "image/png"),
            ("jpg", "image/jpeg"),
            ("jpeg", "image/jpeg"),
            ("pdf", "application/pdf"),
        ],
    )
    def test_every_format_gauss_writes_can_be_shown(self, tmp_path, extension, mimetype):
        engine = self._engine()
        target = tmp_path / f"p.{extension}"
        target.write_bytes(b"data")
        assert engine._read_figure(target, keep=True)[0].mimetype == mimetype

    def test_a_format_gauss_refuses_is_named_before_it_fails(self):
        """GAUSS answers only "Program execute failed", which explains nothing."""
        from econenv.engines.gauss_engine import _GRAPHICS_MIME, _UNSUPPORTED_PLOT

        assert "eps" in _UNSUPPORTED_PLOT
        assert not _UNSUPPORTED_PLOT & set(_GRAPHICS_MIME), "no format in both sets"


class TestPlotSizeUnits:
    """Reported twice with screenshots: a plotting cell showed a broken icon.

    `plotSave(file, 12 | 9)` without a unit writes onto a canvas of raw units —
    measured at 4.2mm x 3.2mm against GAUSS 26.1.1. The file is full of valid
    path data, so it looks right by size and is microscopic on screen. The unit
    is therefore always stated.
    """

    @staticmethod
    def _engine(graphics):
        from econenv.engines import gauss_engine

        engine = object.__new__(gauss_engine.GaussEngine)
        engine._backend = type("B", (), {"session": pathlib.Path(".")})()
        engine._graphics_format = lambda: graphics
        return engine

    @pytest.mark.parametrize("fmt", ["svg", "pdf"])
    def test_vector_is_saved_in_inches(self, fmt):
        _, program = self._engine(fmt)._with_graphics("plotXY(x, y);")
        assert '"in"' in program, "a vector canvas is measured in inches"
        assert "12 | 9" in program

    @pytest.mark.parametrize("fmt", ["png", "jpg", "jpeg"])
    def test_raster_is_saved_in_pixels(self, fmt):
        _, program = self._engine(fmt)._with_graphics("plotXY(x, y);")
        assert '"px"' in program, "a raster canvas is measured in pixels"
        assert "1200 | 900" in program

    def test_the_unit_is_never_left_off(self):
        """Omitting it is what produced the four-millimetre figure."""
        for fmt in ("svg", "png", "pdf", "jpg"):
            _, program = self._engine(fmt)._with_graphics("plotXY(x, y);")
            call = next(line for line in program.splitlines() if "plotSave" in line)
            assert call.count(",") >= 2, f"{fmt}: plotSave needs a size and a unit"
