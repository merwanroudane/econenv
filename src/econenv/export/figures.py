"""Saving figures at a quality journals accept.

The important distinction is raster versus vector. A PNG is fixed pixels: print
it at column width and it looks fine, print it larger and it does not. A PDF or
EPS is instructions, so it stays sharp at any size — which is why most economics
journals ask for vector figures and reject screenshots.

EconEnv captures whatever the engine produced. If that was a PNG and you ask for
a PDF, the honest options are to re-render from the engine in vector form, or to
say the request cannot be met. This module does the first where it can and the
second otherwise; it never wraps a bitmap in a PDF container and calls it vector.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from ..results import Figure

#: Formats that stay sharp at any size.
VECTOR = frozenset({"pdf", "eps", "svg"})
#: Formats made of pixels.
RASTER = frozenset({"png", "jpg", "jpeg", "tif", "tiff"})

#: What each engine can be asked to produce directly.
ENGINE_VECTOR_SUPPORT = {
    "r": frozenset({"svg", "pdf", "eps"}),
    "matlab": frozenset({"pdf", "eps", "svg"}),
    "eviews": frozenset({"svg", "pdf", "emf"}),
    "python": frozenset({"pdf", "svg", "eps"}),
}

_MIME_TO_EXT = {
    "image/png": "png",
    "image/svg+xml": "svg",
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
}


def figure_extension(figure: Figure) -> str:
    """The extension matching what the figure actually contains."""
    return _MIME_TO_EXT.get(figure.mimetype, "png")


def is_vector(figure: Figure) -> bool:
    return figure_extension(figure) in VECTOR


def save_figure(figure: Figure, path: Path) -> Path:
    """Write the figure's bytes, using its own format.

    The extension of *path* is corrected to match the content rather than
    trusted: naming a PNG ``.pdf`` produces a file nothing can open.
    """
    extension = figure_extension(figure)
    target = (
        path if path.suffix.lower().lstrip(".") == extension else path.with_suffix(f".{extension}")
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(figure.data)
    return target


def save_figures(
    figures: Iterable[Figure],
    directory: Path,
    *,
    prefix: str = "figure",
) -> List[Path]:
    """Write several figures into *directory*, numbered in order."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    for position, figure in enumerate(figures, start=1):
        stem = _stem(figure, position, prefix)
        written.append(save_figure(figure, directory / f"{stem}.{figure_extension(figure)}"))
    return written


def vector_advice(figures: Sequence[Figure], wanted: str = "pdf") -> Optional[str]:
    """What to change to get vector output, when the captured figures are raster.

    Returns ``None`` when everything is already vector, so the caller can stay
    quiet rather than nagging.
    """
    raster = [f for f in figures if not is_vector(f)]
    if not raster:
        return None
    engines = sorted({f.engine for f in raster})
    lines = []
    for engine in engines:
        supported = ENGINE_VECTOR_SUPPORT.get(engine, frozenset())
        if wanted in supported:
            lines.append(f"%econ config {engine}.graphics {wanted}")
    if not lines:
        return (
            f"These figures are raster and {', '.join(engines)} cannot produce "
            f"{wanted} directly. They will print at their captured resolution."
        )
    return (
        "Captured as raster. For vector figures, set the engine to produce them "
        "before re-running:\n  " + "\n  ".join(lines)
    )


def _stem(figure: Figure, position: int, prefix: str) -> str:
    name = (figure.name or "").strip()
    if not name:
        return f"{prefix}{position:02d}_{figure.engine}"
    cleaned = "".join(ch if (ch.isalnum() or ch in "-_") else "_" for ch in name).strip("_")
    return f"{prefix}{position:02d}_{figure.engine}_{cleaned}"[:80] or f"{prefix}{position:02d}"
