"""Writers that turn a formatted table into a file a journal will accept.

Each writer takes a DataFrame that has already been laid out by
:mod:`econenv.export.tables` and is responsible only for the file format. That
split matters: the decision about what a table *says* is made once, so the
LaTeX and the Word version of a result cannot disagree.

``docx`` and ``xlsx`` need optional packages. Rather than fail at import time,
they raise when used and name the one command that fixes it — a researcher who
only wants LaTeX should never be asked to install python-docx.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Sequence

import pandas as pd

from ..exceptions import EconEnvError

#: Characters LaTeX treats specially in ordinary text.
_LATEX_ESCAPES = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


#: Unicode superscripts that appear in our own labels (R², adjusted R²).
#: A raw ² compiles only with the right inputenc; 	extsuperscript always does.
_SUPERSCRIPTS = {"\u00b2": r"\textsuperscript{2}", "\u00b3": r"\textsuperscript{3}"}


def latex_escape(text: Any) -> str:
    """Escape a cell for LaTeX, leaving already-mathy content alone.

    Superscript stars are the one exception: ``***`` is meant as a marker, and
    escaping it to ``\\textasciicircum`` would be wrong.
    """
    value = "" if text is None else str(text)
    if value.startswith("$") and value.endswith("$") and len(value) > 1:
        return value  # the author wrote maths deliberately
    return "".join(_SUPERSCRIPTS.get(ch) or _LATEX_ESCAPES.get(ch, ch) for ch in value)


def write_latex(
    table: pd.DataFrame,
    path: Path,
    *,
    caption: Optional[str] = None,
    label: Optional[str] = None,
    note: Optional[str] = None,
    booktabs: bool = True,
    fragment: bool = False,
) -> Path:
    """A ``table`` environment with booktabs rules, ready to ``\\input``.

    ``fragment=True`` writes only the ``tabular``, for authors who keep their
    own float and caption in the manuscript.
    """
    columns = list(table.columns)
    align = "l" + "c" * len(columns)
    rule_top, rule_mid, rule_bot = (
        (r"\toprule", r"\midrule", r"\bottomrule")
        if booktabs
        else (r"\hline", r"\hline", r"\hline")
    )

    lines = []
    if not fragment:
        lines += [r"\begin{table}[htbp]", r"\centering"]
        if caption:
            lines.append(rf"\caption{{{latex_escape(caption)}}}")
        if label:
            lines.append(rf"\label{{{label}}}")
    lines.append(rf"\begin{{tabular}}{{{align}}}")
    lines.append(rule_top)
    lines.append(" & ".join([""] + [latex_escape(c) for c in columns]) + r" \\")
    lines.append(rule_mid)

    for index, row in zip(table.index, table.itertuples(index=False)):
        cells = [latex_escape(index)] + [latex_escape(v) for v in row]
        lines.append(" & ".join(cells) + r" \\")

    lines.append(rule_bot)
    lines.append(r"\end{tabular}")
    if note and not fragment:
        lines += [
            r"\begin{minipage}{\textwidth}",
            r"\footnotesize",
            latex_escape(note),
            r"\end{minipage}",
        ]
    if not fragment:
        lines.append(r"\end{table}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_markdown(table: pd.DataFrame, path: Path, *, note: Optional[str] = None) -> Path:
    body = table.to_markdown()
    if note:
        body += f"\n\n_{note}_\n"
    path.write_text(body + "\n", encoding="utf-8")
    return path


def write_html(
    table: pd.DataFrame,
    path: Path,
    *,
    caption: Optional[str] = None,
    note: Optional[str] = None,
) -> Path:
    """Self-contained HTML, styled the way a journal table looks."""
    style = (
        "<style>"
        "table{border-collapse:collapse;font-family:Georgia,serif;font-size:14px;margin:1em 0}"
        "th,td{padding:5px 14px;text-align:center}"
        "th:first-child,td:first-child{text-align:left}"
        "thead th{border-top:1.4px solid #222;border-bottom:.8px solid #222;font-weight:600}"
        "tbody tr:last-child td{border-bottom:1.4px solid #222}"
        "caption{caption-side:top;font-weight:600;padding-bottom:8px}"
        ".note{font-size:12px;color:#444;max-width:40em}"
        "</style>"
    )
    html = table.to_html(escape=True, border=0)
    if caption:
        html = html.replace("<table", f"<table><caption>{caption}</caption", 1).replace(
            "<table><caption", "<table class='ee'><caption", 1
        )
    pieces = [style, html]
    if note:
        pieces.append(f"<p class='note'>{note}</p>")
    path.write_text("\n".join(pieces) + "\n", encoding="utf-8")
    return path


def write_csv(table: pd.DataFrame, path: Path) -> Path:
    table.to_csv(path, encoding="utf-8")
    return path


def write_xlsx(
    tables: Any,
    path: Path,
    *,
    note: Optional[str] = None,
) -> Path:
    """One sheet per table, with the numbers kept at full precision.

    A dict of ``{sheet name: DataFrame}`` writes several sheets; a single frame
    writes one called ``results``.
    """
    try:
        import openpyxl  # noqa: F401
    except ImportError as exc:
        raise EconEnvError('Writing .xlsx needs openpyxl: pip install "econenv[export]"') from exc

    frames = tables if isinstance(tables, dict) else {"results": tables}
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for name, frame in frames.items():
            sheet = _safe_sheet_name(name)
            frame.to_excel(writer, sheet_name=sheet)
            if note:
                worksheet = writer.sheets[sheet]
                worksheet.cell(row=len(frame) + 3, column=1, value=note)
    return path


def write_docx(
    table: pd.DataFrame,
    path: Path,
    *,
    caption: Optional[str] = None,
    note: Optional[str] = None,
    font: str = "Times New Roman",
    size: int = 10,
) -> Path:
    """A real Word table — editable cells, not a picture of a table."""
    try:
        from docx import Document
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.shared import Pt
    except ImportError as exc:
        raise EconEnvError(
            'Writing .docx needs python-docx: pip install "econenv[export]"'
        ) from exc

    document = Document()
    if caption:
        heading = document.add_paragraph(caption)
        heading.runs[0].bold = True

    word_table = document.add_table(rows=1, cols=len(table.columns) + 1)
    word_table.style = "Table Grid"

    header = word_table.rows[0].cells
    header[0].text = ""
    for position, column in enumerate(table.columns, start=1):
        header[position].text = str(column)

    for index, row in zip(table.index, table.itertuples(index=False)):
        cells = word_table.add_row().cells
        cells[0].text = str(index)
        for position, value in enumerate(row, start=1):
            cells[position].text = "" if value is None else str(value)

    for row in word_table.rows:
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                for run in paragraph.runs:
                    run.font.name = font
                    run.font.size = Pt(size)
    for row in word_table.rows:
        first = row.cells[0]
        for paragraph in first.paragraphs:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT

    if note:
        footnote = document.add_paragraph(note)
        footnote.runs[0].font.size = Pt(size - 1)
        footnote.runs[0].italic = True

    document.save(str(path))
    return path


def write_rtf(table: pd.DataFrame, path: Path, *, note: Optional[str] = None) -> Path:
    """RTF, for the journals whose submission systems still want it."""
    columns = len(table.columns) + 1
    width = int(9000 / columns)
    lines = [r"{\rtf1\ansi\deff0{\fonttbl{\f0 Times New Roman;}}\fs20"]

    def row(cells: Sequence[str], bold: bool = False) -> str:
        borders = "".join(rf"\cellx{width * (i + 1)}" for i in range(columns))
        body = "".join(
            (r"\b " if bold else "") + _rtf_escape(c) + (r"\b0 " if bold else "") + r"\cell "
            for c in cells
        )
        return r"\trowd\trgaph100" + borders + body + r"\row"

    lines.append(row([""] + [str(c) for c in table.columns], bold=True))
    for index, values in zip(table.index, table.itertuples(index=False)):
        lines.append(row([str(index)] + ["" if v is None else str(v) for v in values]))
    if note:
        lines.append(r"\par\fs16\i " + _rtf_escape(note) + r"\i0")
    lines.append("}")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _rtf_escape(text: str) -> str:
    return (
        str(text)
        .replace("\\", r"\\")
        .replace("{", r"\{")
        .replace("}", r"\}")
        .encode("ascii", "backslashreplace")
        .decode("ascii")
    )


def _safe_sheet_name(name: str) -> str:
    """Excel forbids ``[]:*?/\\`` and caps sheet names at 31 characters."""
    cleaned = re.sub(r"[\[\]:*?/\\]", "_", str(name))
    return cleaned[:31] or "sheet"


#: Extension -> writer, for the dispatcher in :mod:`econenv.export`.
TABLE_WRITERS: Dict[str, Callable[..., Path]] = {
    "tex": write_latex,
    "latex": write_latex,
    "docx": write_docx,
    "xlsx": write_xlsx,
    "csv": write_csv,
    "html": write_html,
    "md": write_markdown,
    "rtf": write_rtf,
}
