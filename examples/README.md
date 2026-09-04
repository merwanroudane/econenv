# Examples

Nine progressive notebooks. Every one generates its own data — none depends on a
file you do not have (brief §44).

| Notebook | Needs |
|---|---|
| [01_quick_start.ipynb](01_quick_start.ipynb) | anything you have |
| [02_python_and_r.ipynb](02_python_and_r.ipynb) | R |
| [03_python_and_stata.ipynb](03_python_and_stata.ipynb) | Stata 17+ |
| [04_python_and_eviews.ipynb](04_python_and_eviews.ipynb) | EViews, Windows |
| [05_all_four_engines.ipynb](05_all_four_engines.ipynb) | all four — the MVP acceptance test |
| [06_same_ols_four_engines.ipynb](06_same_ols_four_engines.ipynb) | runs with whatever is present |
| [07_data_transfer.ipynb](07_data_transfer.ipynb) | R and Stata |
| [08_time_series.ipynb](08_time_series.ipynb) | R, Stata, EViews |
| [09_panel_data.ipynb](09_panel_data.ipynb) | R, Stata |
| [11_colab_quickstart.ipynb](11_colab_quickstart.ipynb) | Python, R — **runs on Google Colab**, no local install |
| **[10_real_data_four_engines.ipynb](10_real_data_four_engines.ipynb)** | **all four** — a complete worked analysis on real US macro data, with every output executed |

Notebook 5 is the acceptance test from the project brief: a Python cell, an R
cell, a Stata cell and an EViews cell, in sequence, in **one** Python kernel.
[`_mvp_acceptance.py`](_mvp_acceptance.py) is the same test as a plain script,
runnable without opening Jupyter:

```bash
python examples/_mvp_acceptance.py
```

Notebook 6 is the one worth reading if you only read one — the same OLS in four
engines, agreeing to machine precision on the coefficients and disagreeing on
the information criteria, with the reason named.

## Running them

```bash
pip install -e ".[all]"
jupyter lab examples/
```

Each starts with `%load_ext econenv`. Nothing is started until you use it, so a
notebook for an engine you do not have will fail on that cell and leave the rest
of your kernel intact — the error will say what is missing and what to do.

## The one to start with

[`10_real_data_four_engines.ipynb`](10_real_data_four_engines.ipynb) is the fullest example: **real US quarterly macroeconomic data, 1959Q1–2009Q3**, shipped with statsmodels so it needs no download and no private file.

It uses each program for what it is actually best at — pandas to build the data, R to plot and diagnose, Stata's `newey` for HAC standard errors, EViews for unit roots, cointegration, stability and forecasting — then compares the same regression across all four.

Every output in it was produced by executing it against real installations of R 4.5.2, StataNow 19.5 MP and EViews 13. It is regenerated with:

```bash
python scripts/build_example_notebook.py --run
```

so it cannot quietly stop being true.
