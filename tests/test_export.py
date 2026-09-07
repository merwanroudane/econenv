"""Export tests.

The LaTeX these produce was compiled with pdflatex during development, so the
escaping rules here are the ones that actually survive a real build rather than
the ones that look plausible.
"""

import numpy as np
import pandas as pd
import pytest

import econenv
from econenv.exceptions import EconEnvError
from econenv.export import export, export_table, full_table, journal_table, star_note
from econenv.export.figures import figure_extension, is_vector, save_figure, vector_advice
from econenv.export.tables import stars_for
from econenv.export.writers import latex_escape
from econenv.results import Figure, ModelResult


def _model(engine="python", coef=(1.5, 2.0), pvals=(0.0001, 0.03), nobs=120):
    return ModelResult.from_arrays(
        engine=engine,
        model="OLS",
        terms=["_cons", "x1"],
        coef=np.array(coef),
        std_err=np.array([0.035, 0.040]),
        stat=np.array([42.3, 48.9]),
        pvalue=np.array(pvals),
        depvar="y",
        nobs=nobs,
        r2=0.9597,
        r2_adj=0.9590,
    )


class TestStars:
    @pytest.mark.parametrize(
        "pvalue, expected",
        [(0.0001, "***"), (0.02, "**"), (0.08, "*"), (0.5, ""), (None, ""), (float("nan"), "")],
    )
    def test_conventional_thresholds(self, pvalue, expected):
        assert stars_for(pvalue) == expected

    def test_an_unknown_pvalue_gets_no_star_rather_than_a_guess(self):
        assert stars_for(None) == ""

    def test_the_note_matches_the_thresholds_used(self):
        note = star_note()
        assert "*** p < 0.01" in note and "* p < 0.1" in note
        assert "parentheses" in note


class TestJournalTable:
    """The layout a paper prints: estimate with stars, standard error beneath."""

    def test_standard_error_sits_under_its_coefficient(self):
        table = journal_table(_model())
        assert table.index[0] == "_cons"
        assert table.index[1] == ""  # the SE line carries no label
        assert table.iloc[0, 0].startswith("1.5000")
        assert table.iloc[1, 0] == "(0.0350)"

    def test_significance_stars_are_attached_to_the_estimate(self):
        table = journal_table(_model(pvals=(0.0001, 0.5)))
        assert table.iloc[0, 0].endswith("***")
        assert not table.iloc[2, 0].endswith("*")

    def test_several_engines_become_several_columns(self):
        table = journal_table([_model("python"), _model("r"), _model("stata")])
        assert list(table.columns) == ["Python", "R", "Stata"]

    def test_fit_statistics_appear_at_the_foot(self):
        table = journal_table(_model())
        assert "Observations" in table.index
        assert table.loc["Observations"].iloc[0] == "120"

    def test_a_statistic_the_engine_did_not_report_is_left_blank(self):
        """Never computed here under different assumptions."""
        bare = _model()
        bare.r2 = None
        bare.r2_adj = None
        table = journal_table(bare)
        assert "R²" not in table.index

    def test_a_non_model_is_refused_with_a_useful_message(self):
        with pytest.raises(TypeError, match="ModelResult"):
            journal_table("not a model")


class TestFullTable:
    def test_every_reported_statistic_is_kept(self):
        table = full_table(_model())
        for column in ("coef", "std_err", "stat", "pvalue"):
            assert column in table.columns

    def test_engine_is_a_column_so_models_stay_distinguishable(self):
        table = full_table([_model("r"), _model("stata")])
        assert set(table["engine"]) == {"r", "stata"}


class TestLatexEscaping:
    """These rules were checked by compiling the output with pdflatex."""

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("_cons", r"\_cons"),
            ("50%", r"50\%"),
            ("a&b", r"a\&b"),
            ("x#1", r"x\#1"),
            ("R²", r"R\textsuperscript{2}"),
        ],
    )
    def test_special_characters_are_escaped(self, raw, expected):
        assert latex_escape(raw) == expected

    def test_deliberate_maths_is_left_alone(self):
        assert latex_escape("$\beta_1$") == "$\beta_1$"


class TestExport:
    def test_one_call_writes_every_format(self, tmp_path):
        result = export(_model(), tmp_path / "t1", formats=["tex", "csv", "html", "md"])
        written = {p.suffix for p in result.tables}
        assert written == {".tex", ".csv", ".html", ".md"}
        assert all(p.exists() and p.stat().st_size > 0 for p in result.tables)

    def test_latex_uses_booktabs_and_carries_the_star_note(self, tmp_path):
        export(_model(), tmp_path / "t.tex", caption="A caption", label="tab:x")
        text = (tmp_path / "t.tex").read_text(encoding="utf-8")
        assert r"\toprule" in text and r"\bottomrule" in text
        assert r"\caption{A caption}" in text and r"\label{tab:x}" in text
        assert "Standard errors in parentheses" in text

    def test_a_suffix_selects_the_format_without_being_told(self, tmp_path):
        result = export(_model(), tmp_path / "only.csv")
        assert [p.suffix for p in result.tables] == [".csv"]

    def test_an_unknown_format_names_the_ones_that_exist(self, tmp_path):
        with pytest.raises(EconEnvError, match="Available"):
            export(_model(), tmp_path / "t", formats=["pptx"])

    def test_exporting_nothing_is_an_error_not_an_empty_file(self, tmp_path):
        with pytest.raises(EconEnvError, match="Nothing to export"):
            export([], tmp_path / "t")

    def test_style_full_gives_every_statistic(self, tmp_path):
        export(_model(), tmp_path / "f.csv", style="full")
        text = (tmp_path / "f.csv").read_text(encoding="utf-8")
        assert "std_err" in text and "pvalue" in text

    def test_a_dataframe_exports_as_itself(self, tmp_path):
        frame = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        result = export(frame, tmp_path / "d.csv")
        assert result.tables[0].exists()


class TestFigures:
    def test_extension_follows_the_content_not_the_filename(self, tmp_path):
        """Naming a PNG .pdf produces a file nothing can open."""
        figure = Figure(data=b"\x89PNG-data", mimetype="image/png", engine="r", name="p")
        written = save_figure(figure, tmp_path / "wrong.pdf")
        assert written.suffix == ".png"
        assert written.read_bytes() == b"\x89PNG-data"

    @pytest.mark.parametrize(
        "mimetype, extension, vector",
        [
            ("image/png", "png", False),
            ("image/svg+xml", "svg", True),
            ("application/pdf", "pdf", True),
        ],
    )
    def test_vector_and_raster_are_distinguished(self, mimetype, extension, vector):
        figure = Figure(data=b"x", mimetype=mimetype, engine="r")
        assert figure_extension(figure) == extension
        assert is_vector(figure) is vector

    def test_raster_figures_get_advice_naming_the_setting_to_change(self):
        figures = [Figure(data=b"x", mimetype="image/png", engine="eviews")]
        advice = vector_advice(figures, wanted="pdf")
        assert advice and "eviews.graphics pdf" in advice

    def test_vector_figures_produce_no_nagging(self):
        figures = [Figure(data=b"x", mimetype="application/pdf", engine="matlab")]
        assert vector_advice(figures, wanted="pdf") is None


class TestTablesOnly:
    def test_export_table_ignores_figures(self, tmp_path):
        figure = Figure(data=b"x", mimetype="image/png", engine="r")
        result = export_table([_model(), figure], tmp_path / "t.csv")
        assert result.figures == []
        assert len(result.tables) == 1


class TestJupyterDisplay:
    """A journal table should look like one in the notebook, not like a grid.

    The generic pandas rendering is readable but looks nothing like the thing
    you are about to paste into a paper, which makes a layout problem harder to
    catch early.
    """

    def test_it_is_still_a_dataframe(self):
        """Subclass, not wrapper — every pandas operation must keep working."""
        table = journal_table(_model())
        assert isinstance(table, pd.DataFrame)
        assert table.shape[0] > 0
        assert table.to_csv()
        assert isinstance(table.iloc[:2], pd.DataFrame)

    def test_it_renders_with_rules_rather_than_gridlines(self):
        html = journal_table(_model())._repr_html_()
        assert "border-top:1.5px solid #1b1b1b" in html
        assert "tbody tr:last-child td{border-bottom:1.5px" in html

    def test_standard_error_rows_are_marked_so_they_sit_tight(self):
        import re

        html = journal_table(_model())._repr_html_()
        body = re.search(r"<tbody>(.*?)</tbody>", html, re.S).group(1)
        rows = re.findall(r"(<tr[^>]*>.*?</tr>)", body, re.S)
        se_rows = [r for r in rows if "ee-se" in r.split(">")[0]]
        assert len(se_rows) == 2, "one unlabelled SE row under each coefficient"

    def test_the_star_note_travels_with_the_table(self):
        html = journal_table(_model())._repr_html_()
        assert "Standard errors in parentheses" in html
        assert "p &lt; 0.01" in html or "p < 0.01" in html

    def test_every_writer_still_accepts_it(self, tmp_path):
        """It must remain usable by the exporters, not just pretty."""
        result = export(_model(), tmp_path / "t", formats=["tex", "csv", "html"])
        assert len(result.tables) == 3
        assert all(p.stat().st_size > 0 for p in result.tables)


class TestMatrixAndPdfExport:
    """Gaps found while checking the export layer against the MATLAB brief."""

    def test_a_numpy_matrix_can_be_exported(self, tmp_path):
        """`%%matlab -o A` returns an ndarray, and it has to be exportable."""
        matrix = np.array([[10.0, 20.0], [30.0, 40.0]])
        result = econenv.export(matrix, tmp_path / "m.tex")
        text = result.paths[0].read_text(encoding="utf-8")
        assert "10.0" in text and "40.0" in text
        assert r"\toprule" in text

    def test_a_matrix_gets_no_significance_note(self, tmp_path):
        """Stars under a plain matrix would claim p-values that do not exist."""
        econenv.export(np.array([[1.0, 2.0]]), tmp_path / "m.tex")
        assert "Standard errors in parentheses" not in (tmp_path / "m.tex").read_text(
            encoding="utf-8"
        )

    def test_a_three_dimensional_array_is_refused(self, tmp_path):
        with pytest.raises(EconEnvError) as caught:
            econenv.export(np.zeros((2, 2, 2)), tmp_path / "m.tex")
        assert "3-dimensional" in str(caught.value)

    def test_an_unknown_extension_is_refused_not_silently_swapped(self, tmp_path):
        """Asking for .odt used to write .tex, .docx and .xlsx and say nothing."""
        with pytest.raises(EconEnvError) as caught:
            econenv.export(pd.DataFrame({"a": [1.0]}), tmp_path / "t.odt")
        message = str(caught.value)
        assert "odt" in message
        assert "csv" in message and "pdf" in message, "list what is available"

    def test_pdf_is_a_known_format(self):
        from econenv.export import TABLE_FORMATS

        assert "pdf" in TABLE_FORMATS

    def test_pdf_without_a_tex_engine_explains_itself(self, tmp_path, monkeypatch):
        from econenv.export import writers

        monkeypatch.setattr(writers.shutil, "which", lambda name: None)
        with pytest.raises(EconEnvError) as caught:
            writers.write_pdf(pd.DataFrame({"a": [1.0]}), tmp_path / "t.pdf")
        message = str(caught.value)
        assert "TeX engine" in message
        assert "pip" in message, "say that pip cannot fix it"
        assert ".tex" in message and "docx" in message, "offer the alternatives"


class TestReport:
    """A table, a figure and the versions that produced them, in one file."""

    @pytest.fixture
    def filled(self):
        frame = pd.DataFrame({"coefficient": [1.5, 2.5]}, index=["_cons", "x"])
        report = econenv.report("Test report", author="Dr Merwan Roudane")
        report.add_text("A paragraph.")
        report.add_table(frame, caption="Table 1. Estimates")
        report.add_snapshot({"econenv": "test", "python": "3.11"})
        return report

    @pytest.mark.parametrize("extension", ["html", "md", "tex"])
    def test_it_writes_each_text_format(self, filled, tmp_path, extension):
        path = filled.write(tmp_path / f"r.{extension}")
        text = path.read_text(encoding="utf-8")
        assert path.exists() and path.stat().st_size > 0
        assert "Test report" in text
        assert "Table 1. Estimates" in text
        assert "A paragraph." in text

    def test_the_reproducibility_block_is_included(self, filled, tmp_path):
        text = filled.write(tmp_path / "r.md").read_text(encoding="utf-8")
        assert "Reproducibility" in text
        assert "econenv: test" in text

    def test_a_snapshot_taken_live_never_breaks_the_report(self, tmp_path):
        """An engine that is missing is a fact, not a reason to lose the report."""
        report = econenv.report("Live").add_snapshot()
        assert report.write(tmp_path / "r.html").exists()

    def test_an_unknown_format_is_refused_by_name(self, tmp_path):
        with pytest.raises(EconEnvError) as caught:
            econenv.report("x").write(tmp_path / "r.odt")
        assert "odt" in str(caught.value)

    def test_the_author_appears_when_given(self, filled, tmp_path):
        assert "Merwan Roudane" in filled.write(tmp_path / "r.html").read_text(encoding="utf-8")

    def test_it_renders_in_a_notebook(self, filled):
        assert "<table" in filled._repr_html_()

    def test_str_says_what_is_in_it(self, filled):
        assert "1 text" in str(filled) and "1 table" in str(filled)
