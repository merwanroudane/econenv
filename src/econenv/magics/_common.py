"""Shared plumbing for the magics: argument parsing and result display."""

from __future__ import annotations

import argparse
import shlex
from typing import Any, List, Optional, Sequence

from ..exceptions import EconEnvError
from ..results import ExecutionResult


class MagicArgumentError(EconEnvError):
    """Raised instead of ``SystemExit`` when a magic's arguments are wrong."""


class MagicParser(argparse.ArgumentParser):
    """``argparse`` that reports errors instead of killing the kernel.

    Brief §13 asks for a real parser rather than ad-hoc string slicing, but
    stock ``argparse`` calls ``sys.exit`` on a bad argument, which in a notebook
    kills the cell with an unhelpful traceback.
    """

    def error(self, message: str) -> None:  # type: ignore[override]
        raise MagicArgumentError(f"{self.prog}: {message}\n\n{self.format_usage().strip()}")

    def exit(self, status: int = 0, message: Optional[str] = None) -> None:  # type: ignore[override]
        if message:
            raise MagicArgumentError(message)
        raise MagicArgumentError("")


def shell_of(magics: Any) -> Any:
    """The live :class:`InteractiveShell`, or a clear error.

    ``Magics.shell`` is typed ``Optional``; every magic here only runs inside a
    shell, so this narrows it once instead of at twenty call sites.
    """
    shell = getattr(magics, "shell", None)
    if shell is None:  # pragma: no cover - magics cannot run without a shell
        raise EconEnvError("This magic needs a running IPython shell.")
    return shell


def split_line(line: str) -> List[str]:
    """Tokenise a magic line, tolerating Windows paths."""
    try:
        return shlex.split(line, posix=False)
    except ValueError:
        return line.split()


def strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def display_result(result: ExecutionResult, *, quiet: bool = False) -> Optional[ExecutionResult]:
    """Show *result* in the notebook and decide what the cell returns.

    Text goes straight to stdout so it appears exactly as the engine wrote it —
    monospaced, unwrapped, and streamed above any figures. Figures are displayed
    through the rich-display machinery.
    """
    from IPython.display import display

    if quiet:
        return None

    if result.text:
        print(result.text.rstrip("\n"))
    for note in result.warnings:
        print(f"Warning: {note}")
    for figure in result.figures:
        display(figure)
    for table in result.tables:
        display(table)
    return None


def push_outputs(shell: Any, names: Sequence[str], values: Sequence[Any]) -> None:
    """Bind pulled objects into the user's namespace."""
    for name, value in zip(names, values):
        shell.push({name: value})
