"""Getting results out of EconEnv and into a paper.

One call takes whatever you have — a model, a comparison across five engines, a
DataFrame, a figure, or a whole list of them — and writes it in every format you
name:

    econenv.export(comparison, "paper/table1", formats=["tex", "docx", "xlsx"])

The design point is that the *content* decision happens once. A table is laid
out by :mod:`econenv.export.tables`, and the LaTeX, Word and Excel versions are
three renderings of that same object. They cannot disagree about a coefficient,
which is exactly what happens when a table is retyped into a manuscript.

What it will not do is fake precision. A statistic an engine did not report is
left blank; a raster figure is not re-wrapped as a "vector" PDF. Where a request
cannot be met honestly, the result says so and tells you what to change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import pandas as pd

from ..exceptions import EconEnvError
from ..results import ExecutionResult, Figure
from .figures import save_figures, vector_advice
from .tables import DEFAULT_STARS, build_table, full_table, journal_table, star_note
from .writers import TABLE_WRITERS, write_xlsx

__all__ = [
    "FIGURE_FORMATS",
    "TABLE_FORMATS",
    "ExportResult",
    "build_table",
    "export",
    "export_figures",
    "export_table",
    "full_table",
    "journal_table",
    "star_note",
]

#: Table formats ``export`` understands.
TABLE_FORMATS = ("tex", "docx", "xlsx", "csv", "html", "md", "rtf")
#: Figure formats, written in whatever the engine actually produced.
FIGURE_FORMATS = ("png", "svg", "pdf", "eps")

#: Sensible bundle for a journal submission.
JOURNAL_FORMATS = ("tex", "docx", "xlsx")


@dataclass
class ExportResult:
    """What was written, and anything the caller should know about it."""

    tables: List[Path] = field(default_factory=list)
    figures: List[Path] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    @property
    def paths(self) -> List[Path]:
        return [*self.tables, *self.figures]

    def __len__(self) -> int:
        return len(self.paths)

    def __str__(self) -> str:
        lines = []
        if self.tables:
            lines.append(f"Tables ({len(self.tables)}):")
            lines += [f"  {p}" for p in self.tables]
        if self.figures:
            lines.append(f"Figures ({len(self.figures)}):")
            lines += [f"  {p}" for p in self.figures]
        if not lines:
            lines.append("Nothing was written.")
        for note in self.notes:
            lines.append("")
            lines.append(note)
        return "\n".join(lines)

    def _repr_mimebundle_(self, include=None, exclude=None):
        return {"text/plain": str(self)}


def export(
    obj: Any,
    path: Union[str, Path],
    *,
    formats: Optional[Sequence[str]] = None,
    style: str = "journal",
    caption: Optional[str] = None,
    label: Optional[str] = None,
    note: Optional[str] = None,
    stars: Sequence = DEFAULT_STARS,
    digits: int = 4,
    figures: bool = True,
    **kwargs: Any,
) -> ExportResult:
    """Write *obj* to *path* in each of *formats*.

    *obj* may be a :class:`~econenv.results.ModelResult`, a ``ComparisonResult``,
    an :class:`~econenv.results.ExecutionResult`, a ``DataFrame``, a
    :class:`~econenv.results.Figure`, or a list mixing them.

    If *path* has a suffix it names a single file and *formats* is inferred from
    it. Otherwise it is treated as a stem — ``paper/table1`` writes
    ``table1.tex``, ``table1.docx`` and so on — or, when *obj* holds figures too,
    as a directory to fill.

    ``style="journal"`` gives the layout a paper prints: estimate with stars,
    standard error beneath. ``style="full"`` gives every statistic the engine
    reported.
    """
    target = Path(path)
    chosen = _resolve_formats(target, formats)
    result = ExportResult()

    tables, figure_list = _split(obj)

    # `is not None`, never truthiness: a DataFrame raises on bool().
    if tables is not None:
        frame = _to_frame(tables, style=style, stars=stars, digits=digits, **kwargs)
        footer = note if note is not None else (star_note(stars) if style == "journal" else None)
        result.tables += _write_table(
            frame, target, chosen, caption=caption, label=label, note=footer
        )

    if figure_list and figures:
        directory = target if target.suffix == "" else target.parent
        result.figures += save_figures(figure_list, directory, prefix=_figure_prefix(target))
        advice = vector_advice(figure_list, wanted="pdf")
        if advice:
            result.notes.append(advice)

    if not result.paths:
        raise EconEnvError(
            "Nothing to export. Pass a model, a comparison, a DataFrame or a figure."
        )
    return result


def export_table(obj: Any, path: Union[str, Path], **kwargs: Any) -> ExportResult:
    """Tables only, ignoring any figures attached to *obj*."""
    return export(obj, path, figures=False, **kwargs)


def export_figures(
    obj: Any, directory: Union[str, Path], *, prefix: str = "figure"
) -> ExportResult:
    """Figures only, numbered into *directory*."""
    _, figure_list = _split(obj)
    if not figure_list:
        raise EconEnvError("No figures to export. Run a cell that draws one first.")
    result = ExportResult()
    result.figures += save_figures(figure_list, Path(directory), prefix=prefix)
    advice = vector_advice(figure_list, wanted="pdf")
    if advice:
        result.notes.append(advice)
    return result


# --------------------------------------------------------------------------- #
# internals
# --------------------------------------------------------------------------- #
def _split(obj: Any) -> tuple:
    """Separate the tabular content from the figures in whatever was passed."""
    items = obj if isinstance(obj, (list, tuple)) else [obj]
    tables: List[Any] = []
    figures: List[Figure] = []
    for item in items:
        if isinstance(item, Figure):
            figures.append(item)
        elif isinstance(item, ExecutionResult):
            figures.extend(item.figures)
            for extra in getattr(item, "tables", []) or []:
                tables.append(extra)
        else:
            tables.append(item)
    if len(tables) == 1:
        return tables[0], figures
    return (tables if tables else None), figures


def _to_frame(obj: Any, *, style: str, stars: Sequence, digits: int, **kwargs: Any) -> pd.DataFrame:
    if isinstance(obj, pd.DataFrame):
        return obj
    if isinstance(obj, pd.Series):
        return obj.to_frame()
    if style == "journal":
        return journal_table(obj, stars=stars, digits=digits, **kwargs)
    return full_table(obj, digits=max(digits, 6))


def _resolve_formats(target: Path, formats: Optional[Sequence[str]]) -> List[str]:
    if formats:
        unknown = [f for f in formats if f.lower() not in TABLE_WRITERS]
        if unknown:
            raise EconEnvError(
                f"Unknown export format(s): {', '.join(unknown)}. "
                f"Available: {', '.join(sorted(set(TABLE_FORMATS)))}"
            )
        return [f.lower() for f in formats]
    suffix = target.suffix.lower().lstrip(".")
    if suffix in TABLE_WRITERS:
        return [suffix]
    return list(JOURNAL_FORMATS)


def _write_table(
    frame: pd.DataFrame,
    target: Path,
    formats: Sequence[str],
    *,
    caption: Optional[str],
    label: Optional[str],
    note: Optional[str],
) -> List[Path]:
    stem = target if target.suffix == "" else target.with_suffix("")
    if target.suffix == "" and target.is_dir():
        stem = target / "table"
    stem.parent.mkdir(parents=True, exist_ok=True)

    written: List[Path] = []
    for fmt in formats:
        writer = TABLE_WRITERS[fmt]
        destination = stem.with_suffix(f".{'tex' if fmt == 'latex' else fmt}")
        if writer is write_xlsx:
            written.append(writer(frame, destination, note=note))
            continue
        kwargs: Dict[str, Any] = {}
        if fmt in ("tex", "latex", "html", "docx"):
            kwargs["caption"] = caption
            kwargs["note"] = note
        if fmt in ("tex", "latex"):
            kwargs["label"] = label
        if fmt in ("md", "rtf"):
            kwargs["note"] = note
        written.append(writer(frame, destination, **kwargs))
    return written


def _figure_prefix(target: Path) -> str:
    if target.suffix == "":
        return "figure"
    return target.stem or "figure"
