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


#: Namespaces a magic should consult, in order. ``user_global_ns`` differs from
#: ``user_ns`` only when the shell runs with a separate globals mapping, which
#: some frontends do; consulting it costs nothing and is the difference between
#: working and not on those.
def _namespaces(local_ns: Optional[dict], shell: Any) -> List[dict]:
    spaces: List[dict] = []
    if isinstance(local_ns, dict):
        spaces.append(local_ns)
    for attribute in ("user_ns", "user_global_ns"):
        candidate = getattr(shell, attribute, None)
        if isinstance(candidate, dict) and not any(candidate is s for s in spaces):
            spaces.append(candidate)
    return spaces


def resolve_python_name(name: str, local_ns: Optional[dict], shell: Any) -> Any:
    """The Python object called *name*, looked up the way a frontend stores it.

    Two things were wrong with the previous one-liner
    ``local_ns.get(name, shell.user_ns.get(name))``:

    1. It tested the *value* for ``None``, so a variable genuinely assigned
       ``None`` was reported as undefined — a misleading NameError for what is
       really an unsupported type.
    2. It consulted only two mappings. Under Google Colab's local runtime a
       variable set in one cell was not found in ``shell.user_ns`` at all, and
       ``%%matlab -i x`` failed with "'x' is not defined in Python" until the
       user wrote ``get_ipython().user_ns["x"] = x`` by hand.

    Membership is tested rather than truthiness, and every namespace the shell
    exposes is consulted, so the answer does not depend on which frontend is
    driving the kernel.
    """
    for namespace in _namespaces(local_ns, shell):
        if name in namespace:
            return namespace[name]

    known = sorted(
        {
            key
            for namespace in _namespaces(local_ns, shell)
            for key in namespace
            if not key.startswith("_")
        }
    )
    close = [key for key in known if key.lower() == name.lower()][:1]
    suffix = f" Did you mean {close[0]!r}?" if close else ""
    raise NameError(f"{name!r} is not defined in Python.{suffix}")
