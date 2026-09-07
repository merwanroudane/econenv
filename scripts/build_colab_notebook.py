"""Build the Google Colab quick-start notebook.

Colab is Linux, which decides what is possible before anything is installed:

* **Python** is the kernel, so it always works.
* **R** is present on the Colab image, so the R engine works.
* **Stata** would have to be installed and licensed on a machine that is
  destroyed when the session ends. Not practical, and a licence question.
* **EViews** cannot run at all — its automation interface is Windows COM.

So this notebook is deliberately a Python + R notebook. Promising six engines
on Colab would be a lie, and a user would spend an afternoon looking for a
configuration problem that has no solution.

    python scripts/build_colab_notebook.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import nbformat as nbf

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from econenv import __version__

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "examples" / "11_colab_quickstart.ipynb"

REPO = "https://github.com/merwanroudane/econenv"
COLAB = "https://colab.research.google.com/github/merwanroudane/econenv/blob/main/examples/11_colab_quickstart.ipynb"

md = nbf.v4.new_markdown_cell
code = nbf.v4.new_code_cell


def cells():
    yield md(
        f"# EconEnv on Google Colab\n"
        "\n"
        f"[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)]({COLAB})\n"
        "\n"
        "**Python and R in one Colab notebook**, sharing a dataset with no CSV in\n"
        "between.\n"
        "\n"
        "---\n"
        "\n"
        "**Developed by Dr Merwan Roudane**  \n"
        "GitHub: <https://github.com/merwanroudane>  \n"
        f"Package: <https://pypi.org/project/econenv/{__version__}/> (v{__version__})  \n"
        f"Repository: <{REPO}>\n"
        "\n"
        "---\n"
        "\n"
        "## What works on Colab, and what cannot\n"
        "\n"
        "Colab runs on Linux, and that decides this before anything is installed:\n"
        "\n"
        "| Engine | On Colab | Why |\n"
        "|---|---|---|\n"
        "| **Python** | works | it is the kernel |\n"
        "| **R** | works | R is already on the Colab image |\n"
        "| **Stata** | **possible** | Stata for Linux exists and pystata supports it - install it from Google Drive if you hold a Linux licence |\n"
        "| **EViews** | no | no Linux build, Wine cannot licence it, and EViews forbids remote access |\n"
        "| **MATLAB** | **possible** | MATLAB for Linux exists and the Engine API supports it - the same licence question as Stata |\n"
        "| **GAUSS** | **possible** | GAUSS for Linux exists - again a licence question, not a technical one |\n"
        "\n"
        "**Stata is possible here.** See the installation notes in the repository for the\n"
        "Drive-based recipe; EconEnv finds a Linux Stata with no configuration at all.\n"
        "\n"
        "**EViews is not, and cannot be.** There is no Linux build. Under Wine it cannot\n"
        "read a valid machine ID, so licence activation fails. And driving a Windows copy\n"
        "from here is ruled out by EViews itself, whose documentation states that *web\n"
        "server access to EViews via COM is not allowed*. That workaround is easy to\n"
        "build and contractually prohibited, so EconEnv does not ship it.\n"
        "\n"
        "For EViews, run the six-engine notebook on a local Windows machine.\n"
        "\n"
        "---\n"
        "\n"
        "## Want all six engines, and still Colab?\n"
        "\n"
        "You can. Colab already runs in a browser **on your own PC**, so point that\n"
        "interface at a Jupyter server on the same PC: the notebook UI stays Colab,\n"
        "while the kernel - and therefore Python, R, Stata, EViews, MATLAB **and\n"
        "GAUSS** - is\n"
        "your Windows machine.\n"
        "\n"
        "Nothing is exposed to the internet. Your browser talks to `localhost`,\n"
        "Google's servers never reach your machine, and EViews is driven by local COM\n"
        "exactly as in a local notebook.\n"
        "\n"
        "It needs the classic Jupyter stack, because the bridge package dates from\n"
        "2020 and does not load on notebook 7:\n"
        "\n"
        "```bash\n"
        "python -m venv colab-runtime\n"
        "colab-runtime/Scripts/pip install notebook==6.4.12 jupyter_http_over_ws econenv\n"
        "colab-runtime/Scripts/jupyter serverextension enable --py jupyter_http_over_ws\n"
        "colab-runtime/Scripts/jupyter notebook --no-browser --port=8888\n"
        "```\n"
        "\n"
        "Then in Colab: the **Connect** arrow, **Connect to a local runtime**, and paste\n"
        "the `http://localhost:8888/?token=...` URL it printed.\n"
        "\n"
        "Full instructions and the evidence for that version pin are in\n"
        "[the installation notes](https://github.com/merwanroudane/econenv/blob/main/docs/installation.md#google-colab).\n"
        "\n"
        "`%econ doctor` says all of this for you, on the machine you are actually on."
    )

    yield md(
        "## 1. Install\n"
        "\n"
        "One line. `%pip` installs into the kernel that is running, which is what\n"
        "you want inside a notebook."
    )
    yield code("%pip install -q econenv")

    yield md(
        "## 2. Load and check\n"
        "\n"
        "The status table shows what EconEnv found. On Colab you should see Python\n"
        "and R configured, and EViews reported as unavailable — which is correct,\n"
        "not a problem to solve."
    )
    yield code("%load_ext econenv")
    yield code("%econ status")
    yield md(
        "`%econ doctor` explains anything that is missing, and on Colab it says\n"
        "explicitly why Stata and EViews cannot be there."
    )
    yield code("%econ doctor")

    yield md(
        "## 3. Python — build a dataset\n"
        "\n"
        "Real US quarterly macroeconomic data, 1959Q1–2009Q3, shipped with\n"
        "statsmodels — so nothing is downloaded and nothing is private."
    )
    yield code(
        "import numpy as np\n"
        "import pandas as pd\n"
        "import statsmodels.api as sm\n"
        "import econenv\n"
        "\n"
        "raw = sm.datasets.macrodata.load_pandas().data\n"
        "idx = pd.PeriodIndex(\n"
        "    year=raw.year.astype(int), quarter=raw.quarter.astype(int), freq='Q'\n"
        ").to_timestamp()\n"
        "\n"
        "macro = pd.DataFrame(\n"
        "    {\n"
        "        'lrgdp': np.log(raw.realgdp.values),\n"
        "        'lrcons': np.log(raw.realcons.values),\n"
        "        'realint': raw.realint.values,\n"
        "    },\n"
        "    index=idx,\n"
        ")\n"
        "macro.index.name = 'date'\n"
        "print(len(macro), 'quarters')\n"
        "macro.head()"
    )

    yield md(
        "## 4. R — the same data, no file in between\n"
        "\n"
        "`-i macro` sends the DataFrame into R. It arrives as a real `data.frame`;\n"
        "the pandas index becomes a `date` column, because R has no separate notion\n"
        "of an index."
    )
    yield code("%%R -i macro\ncat('R received', nrow(macro), 'rows\\n')\nstr(macro)")
    yield code("%%R\nfit <- lm(lrcons ~ lrgdp + realint, data = macro)\nsummary(fit)")

    yield md("R's diagnostic plots render straight into the Colab output cell:")
    yield code("%%R\npar(mfrow = c(2, 2))\nplot(fit)")

    yield md("### Bring results back to Python\n\n`-o` returns an R object to the Python side.")
    yield code("%%R -o coefs\ncoefs <- as.data.frame(summary(fit)$coefficients)")
    yield code("coefs")

    yield md(
        "## 5. Compare Python and R on the same model\n"
        "\n"
        "`compare_ols` runs the specification in every engine available. On Colab\n"
        "that is Python and R; on a Windows machine with all six installed, the\n"
        "same line returns six columns."
    )
    yield code("cmp = econenv.compare_ols(macro, 'lrcons ~ lrgdp + realint')\ncmp")
    yield code("cmp.coefficients()")
    yield md(
        "The coefficients agree to machine precision. Any information criteria\n"
        "that differ are reported with the reason — statsmodels uses $-2\\ell + 2k$\n"
        "while R counts $\\sigma^2$ as a parameter — rather than being quietly\n"
        "reconciled."
    )

    yield md(
        "## 6. Record what produced this\n"
        "\n"
        "Colab runtimes are disposable, which makes a snapshot more useful here\n"
        "than anywhere else: it pins the versions that generated these numbers."
    )
    yield code("econenv.snapshot()")

    yield md(
        "---\n"
        "\n"
        "## Next\n"
        "\n"
        f"- [The full six-engine notebook]({REPO}/blob/main/examples/10_real_data_all_engines.ipynb) — "
        "Python, R, Stata, EViews, MATLAB **and** GAUSS, for a local Windows machine\n"
        "- [Documentation site](https://merwanroudane.github.io/econenv/)\n"
        f"- [Installation & User Guide (PDF)]({REPO}/blob/main/docs/guide/econenv-guide.pdf)\n"
        f"- [EViews commands for GUI users]({REPO}/blob/main/docs/engines/eviews-commands.md)\n"
        "\n"
        "*EconEnv — Dr Merwan Roudane — "
        f"<{REPO}>*"
    )


def main() -> int:
    nb = nbf.v4.new_notebook(cells=list(cells()))
    nb.metadata.update(
        {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": sys.version.split()[0]},
            "colab": {"provenance": [], "toc_visible": True},
            "econenv": {"generated_by": "scripts/build_colab_notebook.py"},
        }
    )
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    nbf.write(nb, TARGET)
    print(f"wrote {TARGET.relative_to(ROOT)}  ({len(nb.cells)} cells)")
    print(f"  Colab link: {COLAB}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
