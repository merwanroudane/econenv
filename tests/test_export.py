"""Export tests.

The LaTeX these produce was compiled with pdflatex during development, so the
escaping rules here are the ones that actually survive a real build rather than
the ones that look plausible.
"""

import numpy as np
import pandas as pd
import pytest

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
