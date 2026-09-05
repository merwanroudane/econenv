"""Build the four-engine example notebook.

Written as a script rather than by hand so the notebook can be regenerated and
re-executed against a real installation — an example whose outputs were pasted
in by hand is an example that quietly stops being true.

    python scripts/build_example_notebook.py          # build
    python scripts/build_example_notebook.py --run    # build and execute

Executing needs R, Stata and EViews actually installed; without them the
notebook still builds, and the cells that need a missing engine will error when
run, which is the honest outcome.
"""

from __future__ import annotations

import sys
from pathlib import Path

import nbformat as nbf

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from econenv import __version__

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "examples" / "10_real_data_all_engines.ipynb"

md = nbf.v4.new_markdown_cell
code = nbf.v4.new_code_cell


def cells():
    yield md(
        "# Four engines, one notebook — with real data\n"
        "\n"
        "**Python · R · Stata · EViews · MATLAB**, on a single Python kernel.\n"
        "\n"
        "This notebook works through a small applied exercise on **real US "
        "quarterly macroeconomic data, 1959Q1–2009Q3**, using each program for "
        "what it is genuinely best at:\n"
        "\n"
        "| Step | Engine | Why that one |\n"
        "|---|---|---|\n"
        "| Load and transform the data | **Python** | pandas is the best tool for this |\n"
        "| Describe and plot | **R** | `ggplot2`, and R's diagnostic vocabulary |\n"
        "| Regression with HAC standard errors | **Stata** | `newey` is the reference implementation |\n"
        "| Unit roots, cointegration, forecast | **EViews** | this is what EViews is for |\n"
        "| Compare all four | **EconEnv** | same specification, four engines, one table |\n"
        "\n"
        "The dataset moves between the programs **once**, in memory. No CSV is "
        "written at any point.\n"
        "\n"
        "> **Requirements.** Python and the `econenv` package are enough to open "
        "this notebook. Each engine section additionally needs that program "
        "installed and licensed. Cells for an engine you do not have will fail "
        "with a clear message; the rest still run. See the *Installation Guide* "
        "PDF in `docs/` for setting each one up from zero."
        "\n"
        "---\n"
        "\n"
        "**Developed by Dr Merwan Roudane**  \n"
        "GitHub: <https://github.com/merwanroudane>  \n"
        f"Package: <https://pypi.org/project/econenv/{__version__}/> (v{__version__})  \n"
        "Repository: <https://github.com/merwanroudane/econenv>\n"
    )

    yield md(
        "## Installation\n"
        "\n"
        "EconEnv is on PyPI. If it is not already in the Python that runs this\n"
        "notebook:\n"
        "\n"
        "```bash\n"
        "pip install econenv\n"
        "```\n"
        "\n"
        "Or, from inside a notebook cell, which installs into **the kernel actually\n"
        "running** rather than whichever Python happens to be first on your PATH:\n"
        "\n"
        "```python\n"
        "%pip install econenv\n"
        "```\n"
        "\n"
        "Optional extras, only if you need them:\n"
        "\n"
        "```bash\n"
        'pip install "econenv[eviews]"   # comtypes, for EViews on Windows\n'
        'pip install "econenv[arrow]"    # faster transfer to R\n'
        'pip install "econenv[all]"\n'
        "```\n"
        "\n"
        "The core install pulls in only pandas, numpy, IPython and statsmodels.\n"
        "Nothing commercial is downloaded or bundled: R, Stata and EViews must be\n"
        "installed and licensed by you. The *Installation and User Guide* PDF in\n"
        "`docs/guide/` walks through all of them from zero.\n"
    )
    yield code("# Uncomment if econenv is not installed in this kernel:\n# %pip install econenv")
    yield md("## 0. Load the extension and check what is available")
    yield code("%load_ext econenv")
    yield code("%econ status")
    yield md(
        "`%econ doctor` checks every layer and tells you how to fix whatever is "
        "missing. Run it if an engine below does not start."
    )
    yield code("%econ doctor")

    yield md(
        "## 1. Python — the data\n"
        "\n"
        "`statsmodels` ships the US macro dataset used in Greene and in many "
        "textbooks, so this notebook needs no download and no private file.\n"
        "\n"
        "We build a proper quarterly `DatetimeIndex`, because that is what lets "
        "EViews create a *dated* workfile page — without it, EViews treats the "
        "observations as unordered and the time-series tests below are meaningless."
    )
    yield code(
        "import numpy as np\n"
        "import pandas as pd\n"
        "import statsmodels.api as sm\n"
        "import econenv\n"
        "\n"
        "raw = sm.datasets.macrodata.load_pandas().data\n"
        "\n"
        "idx = pd.PeriodIndex(\n"
        "    year=raw.year.astype(int), quarter=raw.quarter.astype(int), freq='Q'\n"
        ").to_timestamp()\n"
        "\n"
        "macro = pd.DataFrame(\n"
        "    {\n"
        "        'lrgdp': np.log(raw.realgdp.values),      # log real GDP\n"
        "        'lrcons': np.log(raw.realcons.values),    # log real consumption\n"
        "        'lrinv': np.log(raw.realinv.values),      # log real investment\n"
        "        'unemp': raw.unemp.values,                # unemployment rate\n"
        "        'infl': raw.infl.values,                  # inflation\n"
        "        'tbill': raw.tbilrate.values,             # 3-month T-bill\n"
        "        'realint': raw.realint.values,            # real interest rate\n"
        "    },\n"
        "    index=idx,\n"
        ")\n"
        "macro.index.name = 'date'\n"
        "span = lambda t: str(t.year) + 'Q' + str(t.quarter)\n"
        "print(len(macro), 'quarters,', span(macro.index[0]), 'to', span(macro.index[-1]))\n"
        "macro.head()"
    )
    yield code("macro.describe().round(3)")

    yield md(
        "### The question\n"
        "\n"
        "A textbook consumption function:\n"
        "\n"
        "$$\\log C_t = \\beta_0 + \\beta_1 \\log Y_t + \\beta_2 r_t + \\varepsilon_t$$\n"
        "\n"
        "with $C$ real consumption, $Y$ real GDP and $r$ the real interest rate. "
        "$\\beta_1$ is the long-run elasticity of consumption with respect to "
        "income, and should be close to 1.\n"
        "\n"
        "Both series are strongly trending, so the interesting econometric "
        "questions — are they non-stationary, are they cointegrated, are the "
        "standard errors trustworthy — are exactly the ones each program answers "
        "differently."
    )

    yield md(
        "## 2. R — describe and plot\n"
        "\n"
        "`-i macro` sends the DataFrame into R. It arrives as a real "
        "`data.frame`, with the dates preserved."
    )
    yield code(
        "%%R -i macro\n"
        "cat('R received', nrow(macro), 'rows and', ncol(macro), 'columns\\n')\n"
        "str(macro[, 1:4])"
    )
    yield code("%%R\nfit_r <- lm(lrcons ~ lrgdp + realint, data = macro)\nsummary(fit_r)")
    yield md(
        "R's own diagnostic plots — the four-panel view every R user knows. These "
        "render straight into the notebook."
    )
    yield code("%%R\npar(mfrow = c(2, 2))\nplot(fit_r)")
    yield code(
        "%%R\n"
        "plot(macro$date, macro$lrcons, type = 'l', lwd = 2,\n"
        "     xlab = '', ylab = 'log real consumption',\n"
        "     main = 'US real consumption, 1959-2009')\n"
        "grid()"
    )

    yield md(
        "## 3. Stata — standard errors that survive serial correlation\n"
        "\n"
        "The residuals above are strongly autocorrelated, so ordinary standard "
        "errors are too small. `newey` is Stata's reference implementation of "
        "Newey–West HAC standard errors.\n"
        "\n"
        "`%%stata` is **StataCorp's own magic**, loaded rather than reimplemented, "
        "so it takes Stata's options and not EconEnv's. Data moves with `%econ`."
    )
    yield code("%econ push stata macro")
    yield code("%%stata\ndescribe\nsummarize lrcons lrgdp realint")
    yield code("%%stata\nregress lrcons lrgdp realint")
    yield md("Now the same regression with HAC standard errors at four lags:")
    yield code("%%stata\ntsset, clear\ngen t = _n\ntsset t\nnewey lrcons lrgdp realint, lag(4)")
    yield md(
        "Compare the standard errors: the coefficient is unchanged, but the "
        "uncertainty around it is considerably larger once serial correlation is "
        "acknowledged. That is the whole reason to go to Stata for this step."
    )

    yield md(
        "## 4. EViews — unit roots, cointegration, forecasting\n"
        "\n"
        "`-i macro` creates a **dated quarterly workfile** from the DataFrame's "
        "index, which is what makes the time-series machinery below valid.\n"
        "\n"
        "The DataFrame becomes a page of **series**, one per column — there is no "
        "object called `macro` in EViews, so refer to the series by name.\n"
        "\n"
        "If you have only ever used EViews by clicking, run `%econ eviews` to look "
        "commands up without leaving the notebook."
    )
    yield code("%%eviews -i macro\nlrcons.stats")
    yield md(
        "### 4.1 Are the series stationary?\n\nGUI path: *Series → View → Unit Root Test → ADF*."
    )
    yield code("%%eviews\nlrgdp.uroot(adf)")
    yield code("%%eviews\nlrcons.uroot(adf)")
    yield md(
        "Both fail to reject a unit root in levels. The standard next step is to "
        "test the first differences:"
    )
    yield code("%%eviews\nlrgdp.uroot(adf, dif=1)")
    yield md(
        "### 4.2 Are they cointegrated?\n"
        "\n"
        "If both series are I(1) but a linear combination is stationary, a "
        "regression in levels is meaningful rather than spurious.\n"
        "\n"
        "GUI path: *Group → View → Cointegration Test → Johansen*."
    )
    yield code("%%eviews\ngroup gci lrcons lrgdp\ngci.coint(e)")
    yield md("### 4.3 The equation, and what EViews shows after estimating it")
    yield code("%%eviews\nequation eq_ev.ls lrcons c lrgdp realint\neq_ev.output")
    yield md("Actual, fitted and residual — the first thing to look at:")
    yield code("%%eviews\neq_ev.resids")
    yield md("Parameter stability — the CUSUM test (`rls(q)`) and CUSUM of squares (`rls(v)`):")
    yield code("%%eviews\neq_ev.rls(q)")
    yield code("%%eviews\neq_ev.rls(v)")
    yield md(
        "### 4.4 A forecast\n"
        "\n"
        "Estimate on a shorter sample, then forecast over the rest — the standard "
        "out-of-sample exercise."
    )
    yield code(
        "%%eviews\n"
        "smpl 1959Q1 1999Q4\n"
        "equation eq_fc.ls lrcons c lrgdp realint\n"
        "smpl 1959Q1 2009Q3\n"
        "eq_fc.forecast(g) lrcons_f"
    )
    yield md(
        "EViews draws its forecast graph in a window that belongs to no object and "
        "cannot be exported, so EconEnv rebuilds the same picture — forecast ± 2 "
        "standard errors — and labels it so you know it was reconstructed."
    )
    yield md("Time-series plots, three equivalent ways to write the same thing:")
    yield code("%%eviews\nsmpl @all\nline lrcons")
    yield code("%%eviews\ngroup gplot lrcons lrgdp\ngplot.line")

    yield md(
        "## 5. MATLAB - the same data again\n"
        "\n"
        "MATLAB arrives as a real `table`, so `fitlm` works on it directly. The\n"
        "pandas index becomes a `date` column of MATLAB's own datetime type.\n"
        "\n"
        "> **MATLAB takes about a minute to start.** The first cell pays for the\n"
        "> whole session; every later one is fast.\n"
    )
    yield code("%%matlab -i macro\ndisp(size(macro))\ndisp(class(macro.date))\n")
    yield code("%%matlab\nmdl = fitlm(macro, 'lrcons ~ lrgdp + realint');\ndisp(mdl)\n")
    yield md("MATLAB's own plot, captured into the notebook:")
    yield code(
        "%%matlab\n"
        "figure; plot(macro.lrgdp, macro.lrcons, 'o'); \n"
        "xlabel('log real GDP'); ylabel('log real consumption');\n"
        "title('US consumption against income, 1959-2009');\n"
    )
    yield md(
        "## 6. Bring results back to Python\n"
        "\n"
        "Everything above stays available. Pull the forecast series back and work "
        "with it in pandas."
    )
    yield code("back = econenv.pull('eviews')\nprint(type(back).__name__, back.shape)\nback.tail()")

    yield md(
        "## 7. The same model in every engine\n"
        "\n"
        "This is the part that is hard to do any other way: one specification, "
        "four programs, one table — and an honest account of where they differ."
    )
    yield code("cmp = econenv.compare_ols(macro, 'lrcons ~ lrgdp + realint')\ncmp")
    yield code("cmp.coefficients()")
    yield md(
        "The coefficients agree to machine precision. The information criteria do "
        "**not**, and EconEnv says why rather than silently picking one "
        "normalisation:\n"
        "\n"
        "- `statsmodels`: $-2\\ell + 2k$\n"
        "- R: counts $\\sigma^2$ as a parameter, so $k+1$\n"
        "- EViews: divides by $n$\n"
        "- Stata: needs `estat ic`, and uses $k = e(\\text{rank}) + 1$\n"
        "\n"
        "None of them is wrong. They are answering slightly different questions, "
        "and a comparison that hid that would be worse than useless."
    )

    yield md(
        "## 8. Export it for the paper\n"
        "\n"
        "One call writes the same table in every format a journal might ask for.\n"
        "The numbers come from the result object, so the file and the estimation\n"
        "cannot drift apart - which is what happens when a table is retyped into a\n"
        "manuscript.\n"
    )
    yield code(
        "paper = econenv.export(cmp, 'paper/table1',\n"
        "                       formats=['tex', 'docx', 'xlsx'],\n"
        "                       caption='Consumption function, five engines',\n"
        "                       label='tab:consumption')\n"
        "paper\n"
    )
    yield md(
        "The LaTeX is `booktabs`, with significance stars and the standard error beneath each coefficient - ready to `\\input` into a manuscript:"
    )
    yield code("print(open('paper/table1.tex', encoding='utf-8').read())\n")
    yield md("`style='full'` gives every statistic instead, for your own checking:")
    yield code(
        "econenv.export(cmp, 'paper/table1_full.csv', style='full')\n"
        "import pandas as pd\n"
        "pd.read_csv('paper/table1_full.csv').head()\n"
    )
    yield md(
        "## 9. Reproducibility\n"
        "\n"
        "Record exactly what produced these numbers — every engine, every version."
    )
    yield code("snap = econenv.snapshot()\nsnap")

    yield md(
        "---\n"
        "\n"
        "## What this notebook demonstrated\n"
        "\n"
        "1. One dataset, built once in Python, used by three other programs with "
        "**no file written**.\n"
        "2. Each program used for its own strength, in its own language, in one "
        "kernel.\n"
        "3. Plots from R and EViews rendered inline alongside Python's.\n"
        "4. The same model estimated in all four and compared, with the "
        "differences explained rather than hidden.\n"
        "5. A reproducibility snapshot recording every version involved.\n"
        "\n"
        "### Where to go next\n"
        "\n"
        "- `%econ eviews` — look up EViews commands from a cell\n"
        "- `%econ doctor` — diagnose any engine that will not start\n"
        "- [`docs/`](../docs/) — engine notes, data exchange, troubleshooting\n"
        "- The *Installation Guide* PDF — setting up all four programs from zero\n"
        "\n"
        "*EconEnv — Dr Merwan Roudane — "
        "<https://github.com/merwanroudane/econenv>*"
    )


def build() -> nbf.NotebookNode:
    nb = nbf.v4.new_notebook(cells=list(cells()))
    nb.metadata.update(
        {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "version": sys.version.split()[0]},
            "econenv": {"generated_by": "scripts/build_example_notebook.py"},
        }
    )
    return nb


def main() -> int:
    nb = build()
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    nbf.write(nb, TARGET)
    n_code = sum(1 for c in nb.cells if c.cell_type == "code")
    print(f"wrote {TARGET.relative_to(ROOT)}  ({len(nb.cells)} cells, {n_code} code)")

    if "--run" in sys.argv:
        from nbclient import NotebookClient

        print("executing against the real engines ...")
        kernel = "python3"
        for arg in sys.argv:
            if arg.startswith("--kernel="):
                kernel = arg.split("=", 1)[1]
        client = NotebookClient(
            nb, timeout=900, kernel_name=kernel, resources={"metadata": {"path": str(ROOT)}}
        )
        client.execute()
        nbf.write(nb, TARGET)
        outputs = sum(len(c.get("outputs", [])) for c in nb.cells if c.cell_type == "code")
        images = sum(
            1
            for c in nb.cells
            if c.cell_type == "code"
            for o in c.get("outputs", [])
            for k in o.get("data", {})
            if k.startswith("image/")
        )
        print(f"executed: {outputs} outputs, {images} figures embedded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
