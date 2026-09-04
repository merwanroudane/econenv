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
