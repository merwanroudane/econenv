# Exporting results for publication

Getting a table out of a notebook and into a paper is where reproducibility
usually breaks. Numbers get retyped, a coefficient is rounded twice, a
regression is re-run and the manuscript is not. EconEnv exports from the result
object itself, so the file and the estimation cannot drift apart.

## One call

```python
econenv.export(cmp, "paper/table1", formats=["tex", "docx", "xlsx"])
```

writes `table1.tex`, `table1.docx` and `table1.xlsx` from the same object. From
a cell, without importing anything:

```python
%econ export cmp paper/table1 --formats tex,docx --caption "Table 1"
```

`cmp` can be a `ModelResult`, a `ComparisonResult` across five engines, a
`DataFrame`, a **NumPy array** — which is what `%%matlab -o A` gives you for a
matrix — a `Figure`, or a list mixing them.

A file extension EconEnv cannot write is refused by name. It used to fall
back to the journal bundle, so asking for `table.pdf` wrote `table.tex`,
`table.docx` and `table.xlsx` and said nothing.

## In the notebook

`journal_table` returns a `JournalTable` — a DataFrame that *renders* like a
journal table: rules instead of gridlines, the standard-error rows tight under
their estimates and unlabelled, and the significance note underneath.

```python
from econenv.export import journal_table

journal_table(cmp)      # displays as a journal table
```

It is still a DataFrame, so slicing, `.to_csv()` and every other pandas
operation work unchanged, and the exporters take it directly.

### What displays automatically

| | In Jupyter |
|---|---|
| Plots from R, EViews, MATLAB, Python | inline images |
| `ExecutionResult`, `ModelResult`, `ComparisonResult` | rich HTML |
| `journal_table(...)` | journal-styled HTML |
| MATLAB `disp(table)` | monospace text, as MATLAB printed it |
| A MATLAB table pulled back with `-o` | a real Jupyter table |

For a MATLAB table as a proper table rather than text, name it on the way out:

```python
%%matlab -o coefs
mdl = fitlm(df, 'y ~ x');
coefs = mdl.Coefficients;
```

```python
coefs      # a DataFrame, rendered as a table
```

## Two layouts

### `style="journal"` — the default

What a paper prints: one column per model, the coefficient with significance
stars, the standard error beneath it in parentheses, and a foot of sample size
and fit statistics.

```python
econenv.export(cmp, "table1.tex", caption="Consumption function", label="tab:cons")
```

```latex
\begin{table}[htbp]
\centering
\caption{Consumption function}
\label{tab:cons}
\begin{tabular}{lccccc}
\toprule
 & Python & EViews & MATLAB & R & Stata \\
\midrule
\_cons & 1.4805*** & 1.4805*** & 1.4805*** & 1.4805*** & 1.4805*** \\
 & (0.0350) & (0.0350) & (0.0350) & (0.0350) & (0.0350) \\
x1 & 1.9331*** & 1.9331*** & 1.9331*** & 1.9331*** & 1.9331*** \\
 & (0.0395) & (0.0395) & (0.0395) & (0.0395) & (0.0395) \\
Observations & 120 & 120 & 120 & 120 & 120 \\
R\textsuperscript{2} & 0.9597 & 0.9597 & 0.9597 & 0.9597 & 0.9597 \\
\bottomrule
\end{tabular}
\end{table}
```

That output was compiled with `pdflatex` during development, which is also how
the escaping rules were settled — a raw `²` is written as
`\textsuperscript{2}` rather than trusting the document's `inputenc`.

### `style="full"` — every statistic

One row per term per engine, with coefficient, standard error, test statistic,
p-value and confidence interval as separate columns. For your own checking
rather than for a paper.

```python
econenv.export(cmp, "check.xlsx", style="full")
```

## Formats

| Format | Extension | Needs | Notes |
|---|---|---|---|
| LaTeX | `.tex` | — | `booktabs` rules, ready to `\input` |
| Word | `.docx` | `econenv[export]` | a real editable table, not a picture |
| Excel | `.xlsx` | `econenv[export]` | one sheet per table, full precision |
| CSV | `.csv` | — | |
| HTML | `.html` | — | self-contained, styled like a journal table |
| Markdown | `.md` | `econenv[export]` | |
| RTF | `.rtf` | — | for submission systems that still want it |
| PDF | `.pdf` | a TeX engine | typeset from the same LaTeX, so they cannot disagree |

```bash
pip install "econenv[export]"
```

Give a filename with a suffix and the format is inferred; give a stem and you
get the journal bundle (`tex`, `docx`, `xlsx`):

```python
econenv.export(cmp, "paper/table1")          # three files
econenv.export(cmp, "paper/table1.tex")      # just LaTeX
```

## Significance stars

The economics convention is the default — `*** p<0.01`, `** p<0.05`,
`* p<0.1` — and the matching note is written under the table automatically.
Journals that use different thresholds:

```python
econenv.export(cmp, "t.tex", stars=((0.001, "***"), (0.01, "**"), (0.05, "*")))
```

## Figures

Figures are written in whatever the engine actually produced, and **the
extension follows the content, not the filename** — naming a PNG `.pdf` makes a
file nothing can open, so EconEnv corrects it.

```python
result = econenv.export_figures(execution_result, "paper/figures")
```

### Vector, for print

Most economics journals want vector figures: a PDF or EPS stays sharp at any
size, a PNG does not. Ask the engine for vector output *before* running the
cell, because a bitmap cannot be converted into one afterwards:

```python
%econ config matlab.graphics pdf
%econ config r.graphics pdf
%econ config eviews.graphics svg
```

If you export raster figures when vector was wanted, the result says so and
names the setting to change rather than wrapping a bitmap in a PDF container:

```
Captured as raster. For vector figures, set the engine to produce them
before re-running:
  %econ config eviews.graphics pdf
```

## Tables and figures together

```python
result = econenv.export([cmp, *execution.figures], "paper/", formats=["tex"])
print(result)
```

```
Tables (1):
  paper/table.tex
Figures (3):
  paper/figure01_eviews_line_x.png
  paper/figure02_matlab_figure_1.png
  paper/figure03_r_plot.svg
```

## A short research report

A table and a figure without the versions that produced them are the thing a
referee cannot check, so the report layer keeps all three together:

```python
report = econenv.report("Consumption function", author="Dr Merwan Roudane")
report.add_text("Quarterly US data, 1959Q1-2009Q3.")
report.add_table(cmp, caption="Table 1. Baseline estimates")
report.add_figures(result.figures, caption="Figure 1. Residual diagnostics")
report.add_snapshot()

report.write("paper/report.docx")
```

`html`, `md`, `tex`, `docx` and `pdf`. Figures are written beside the report and
referenced from it, so the folder moves as one thing.

`add_snapshot()` records EconEnv, Python and every engine's version. It never
raises for an engine that is not installed — that is a fact about the machine,
not a reason to lose the report.

This is deliberately **not** a manuscript system. It answers one question — *put
the table, the chart and the versions into one file I can send someone* — and
stops. Anything more belongs in a real authoring tool.

### PDF needs a TeX engine

`pdf`, for both tables and reports, typesets the LaTeX with `pdflatex`,
`xelatex`, `lualatex` or `tectonic`. That is not a Python package and pip cannot
install it, so when none is on `PATH` the error says which to install for your
platform and offers `.tex` and `.docx` instead of failing inside a subprocess.

## What it will not do

- **Invent a statistic.** A number the engine did not report is left blank, not
  computed here under different assumptions. A table that quietly mixes two
  engines' conventions is worse than one with a gap in it.
- **Fake vector output.** A raster figure is never re-wrapped as a "vector" PDF.
- **Round twice.** The journal layout formats once, from the full-precision
  value; the Excel export keeps the unrounded number.

---

> **A note on importing.** `econenv.export` is both a function and a
> subpackage, and the function wins as an attribute. `from econenv.export import
> journal_table` and `from econenv.export.writers import write_pdf` work; only
> the `import econenv.export.writers as w` form does not.

---

Related: [magic commands](magics.md) · [comparison](comparison.md) ·
[results](results.md)
