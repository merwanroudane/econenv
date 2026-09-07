"""The GAUSS command-line backend.

GAUSS ships a terminal executable — ``tgauss`` on this machine, historically
also ``engauss`` — which compiles and runs a program file and exits. Everything
here was verified against GAUSS 26.1.1 rather than taken from documentation,
because two of the design assumptions turned out to be wrong:

* the executable is ``tgauss``, not ``engauss``;
* ``loadall`` is not available to the batch compiler, so a whole-workspace
  restore is not the way to carry state.

**Invocation.** ``tgauss -nb -nj -x -b program.gss``. ``-nb`` suppresses the
banner and must come first, ``-nj`` the batch job notice, ``-b`` runs and exits,
and ``-x`` turns failures into exit codes:

===== ==========================================
exit  meaning
===== ==========================================
0     ran to completion
3     translator failed
7     compilation failed — **nothing ran**
15    execution failed partway
===== ==========================================

That 7 matters more than it looks. GAUSS compiles the whole program before
running any of it, so one undefined symbol on the last line means the first line
never executed either. A user who sees no output from a cell that "obviously
should have printed something" has almost always hit this, and the message says
so.

**State.** A process exits when the cell finishes, so nothing survives on its
own. Rather than replaying previous cells — which would silently re-run side
effects, and which the design document rightly forbids — this carries the
*values* across with GAUSS's own ``save`` and ``load``: matrices to ``.fmt``,
strings to ``.fst``, in a session directory. That is genuine state transfer, and
what it does not carry (procedures, ``#include``s, local scopes) is documented
rather than pretended.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..exceptions import EngineExecutionError

#: Terminal executables a GAUSS installation may ship, newest naming first.
CLI_NAMES = ("tgauss", "engauss", "gauss")

#: What ``-x`` reports. Anything else is treated as a runtime failure.
EXIT_MEANING = {
    0: "ok",
    3: "translator",
    7: "compile",
    15: "runtime",
}

#: Printed by the wrapper so EconEnv learns each saved symbol's GAUSS type.
_TYPE_MARKER = "__ECONENV_TYPE__"

#: ``error G0025 : Undefined symbol: 'x'`` followed by an indented file/line.
_ERROR_RE = re.compile(r"^error (G\d+)\s*:\s*(.*)$", re.MULTILINE)
_LOCATION_RE = re.compile(r"^\t(.*), line (\d+)$", re.MULTILINE)

#: ``G0276: Illegal use of reserved word 'vec'`` — a name GAUSS already owns.
_RESERVED_RE = re.compile(r"Illegal use of reserved word '([^']+)'")


def find_executable(home: Path) -> Optional[Path]:
    """The terminal executable inside a GAUSS installation."""
    suffix = ".exe" if os.name == "nt" else ""
    for name in CLI_NAMES:
        candidate = home / f"{name}{suffix}"
        if candidate.is_file():
            return candidate
    return None


class GaussCliBackend:
    """Runs GAUSS by launching the terminal executable once per cell."""

    kind = "cli"

    #: A session cannot outlive a process, so this backend never claims one.
    persistent = False

    def __init__(self, executable: Path, home: Optional[Path] = None) -> None:
        self.executable = Path(executable)
        self.home = Path(home) if home else self.executable.parent
        self._session: Optional[Path] = None
        self._carried: Dict[str, str] = {}  # name -> "matrix" | "string"
        #: Lines this wrapper prepended, so GAUSS's line numbers can be
        #: translated back to the line the user actually typed.
        self._offset = 0

    # ------------------------------------------------------------------ #
    # lifecycle
    # ------------------------------------------------------------------ #
    def start(self) -> None:
        """Create the session directory that carries values between cells."""
        if self._session is None:
            self._session = Path(tempfile.mkdtemp(prefix="econenv-gauss-"))

    def stop(self) -> None:
        if self._session is not None:
            shutil.rmtree(self._session, ignore_errors=True)
            self._session = None
        self._carried.clear()

    @property
    def session(self) -> Path:
        self.start()
        assert self._session is not None
        return self._session

    # ------------------------------------------------------------------ #
    # execution
    # ------------------------------------------------------------------ #
    def execute(
        self, code: str, *, timeout: float = 600.0, carry: bool = True
    ) -> Tuple[str, Optional[str]]:
        """Run *code*. Returns ``(output, error)``; *error* is None on success.

        *carry* is False for EconEnv's own transfer programs. They define helper
        procedures, and saving "every name assigned at the top level" from one
        of those picked up the procedure's locals — emitting ``save nr;`` for a
        variable that only exists inside a proc, which fails to compile.
        """
        program = self.instrument(code, carry=carry)
        return self._run(program, timeout=timeout)

    def _run(self, program: str, *, timeout: float) -> Tuple[str, Optional[str]]:
        source = self.session / "econenv_cell.gss"
        source.write_text(program, encoding="utf-8")

        try:
            completed = subprocess.run(
                [
                    str(self.executable),
                    "-nb",  # must be first
                    "-nj",
                    "-x",
                    "-b",
                    str(source),
                ],
                cwd=str(self.session),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise EngineExecutionError(
                f"GAUSS did not finish within {timeout:.0f}s and was stopped.",
                engine="gauss",
                code=program,
                raw=exc,
            ) from exc
        except OSError as exc:
            raise EngineExecutionError(
                f"Could not run {self.executable}: {exc}",
                engine="gauss",
                code=program,
                raw=exc,
            ) from exc

        output = (completed.stdout or "") + (completed.stderr or "")
        return self._interpret(output, completed.returncode, program)

    def _interpret(self, output: str, code: int, program: str) -> Tuple[str, Optional[str]]:
        """Split GAUSS's combined output into what it printed and what failed."""
        output = self._absorb_markers(output)
        errors = _ERROR_RE.findall(output)
        if code == 0 and not errors:
            return _strip_errors(_strip_locations(output)).strip(), None

        stage = EXIT_MEANING.get(code, "runtime")
        message = "; ".join(f"{number}: {text.strip()}" for number, text in errors[:4])
        if not message:
            message = _strip_locations(output).strip()[-400:] or f"exit code {code}"

        lines = [f"GAUSS {stage} error — {message}"]
        for _, reported in _LOCATION_RE.findall(output)[:1]:
            in_cell = int(reported) - self._offset
            if in_cell >= 1:
                lines.append(f"  at line {in_cell} of the cell")
        reserved = _RESERVED_RE.findall(output)
        if reserved:
            lines.append(
                f"  {reserved[0]!r} is a name GAUSS already uses for a built-in. "
                "Choose another, or push under a different name: "
                f"%econ push gauss {reserved[0]} --as my_{reserved[0]}"
            )
        if stage == "compile":
            lines.append(
                "  GAUSS compiles the whole cell before running any of it, so "
                "nothing in this cell ran — not even the lines before the error."
            )
        return _strip_errors(_strip_locations(output)).strip(), "\n".join(lines)

    def _absorb_markers(self, output: str) -> str:
        """Record the types the wrapper reported, and take them out of the output."""
        kept = []
        for line in output.splitlines():
            if _TYPE_MARKER in line:
                parts = line.replace(_TYPE_MARKER, "").split()
                if len(parts) >= 2:
                    name, code = parts[0], parts[-1]
                    self._carried[name] = "string" if code.startswith("13") else "matrix"
                continue
            kept.append(line)
        return "\n".join(kept)

    # ------------------------------------------------------------------ #
    # values carried between cells
    # ------------------------------------------------------------------ #
    def remember(self, name: str, kind: str) -> None:
        """Record that *name* is in the session directory and should be reloaded."""
        self._carried[name] = kind

    def forget(self, name: str) -> None:
        self._carried.pop(name, None)

    def carried(self) -> Dict[str, str]:
        return dict(self._carried)

    def instrument(self, code: str, *, carry: bool = True) -> str:
        """Wrap a cell: restore what earlier cells left, then save what this one makes.

        Only top-level assignments are picked up. That is deliberate — guessing
        at everything GAUSS created would carry procedure locals and
        temporaries across cells, which is worse than carrying too little.

        Each saved symbol also prints a type marker, because ``load`` and
        ``loads`` are different commands and the next cell has to know which to
        use. Asking GAUSS is the only reliable way; inferring it here would be a
        guess about a language whose types we do not track.
        """
        assigned = _assigned_names(code) if carry else []
        preamble = self._preamble()
        self._offset = len(preamble.splitlines()) if preamble else 0
        parts = [preamble, code.rstrip()]
        for name in assigned:
            parts.append(f'save path="{_gauss_path(self.session)}" {name};')
            parts.append(f'print "{_TYPE_MARKER} {name} " type({name});')
        return "\n".join(part for part in parts if part) + "\n"

    def _preamble(self) -> str:
        """Restore the values earlier cells left behind."""
        if not self._carried:
            return ""
        lines = [f'chdir "{_gauss_path(self.session)}";']
        for name, kind in sorted(self._carried.items()):
            lines.append(f"loads {name};" if kind == "string" else f"load {name};")
        return "\n".join(lines)


def _assigned_names(code: str) -> List[str]:
    """Top-level names assigned in *code*, in order, without duplicates."""
    names: List[str] = []
    depth = 0
    for raw in code.splitlines():
        line = raw.strip()
        if not line or line.startswith(("/*", "//", "@")):
            continue
        lowered = line.lower()
        # A procedure's locals are not the cell's variables. Saving them
        # produced `save nr;` for a name that exists only inside the proc.
        if lowered.startswith("proc ") or lowered.startswith("proc("):
            depth += 1
            continue
        if lowered.startswith("endp"):
            depth = max(0, depth - 1)
            continue
        if depth:
            continue
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=[^=]", line)
        if match:
            name = match.group(1)
            if name.lower() not in _RESERVED and name not in names:
                names.append(name)
    return names


#: GAUSS keywords that can begin a line and be followed by ``=``.
_RESERVED = {"if", "else", "elseif", "endif", "do", "until", "while", "endo", "for", "endfor"}


def _gauss_path(path: Path) -> str:
    """A path GAUSS will read correctly.

    GAUSS treats a backslash inside a double-quoted string as an escape, so a
    Windows path has to be given with forward slashes — the same trap the EViews
    adapter hit from the other direction.
    """
    return str(path).replace("\\", "/")


def _strip_errors(output: str) -> str:
    """Remove the diagnostics, which are reported separately.

    Leaving them in means the notebook shows the same failure twice — once as
    GAUSS printed it and once as EconEnv explains it.
    """
    return "\n".join(
        line
        for line in output.splitlines()
        if not line.startswith("error G") and line.strip() != "Program execute failed"
    )


def _strip_locations(output: str) -> str:
    """Drop the tab-indented ``file, line N`` lines that follow each error.

    They name a temporary file the user never wrote and cannot open, so they are
    noise; the line number is reported separately against the cell.
    """
    return "\n".join(line for line in output.splitlines() if not _LOCATION_RE.match(line + "\n"))


def probe_version(executable: Path, *, timeout: float = 60.0) -> Optional[str]:
    """The GAUSS version, from the executable's own banner.

    ``-h`` prints ``GAUSS 26.1.1 (Apr 14 2026, 5516) 64-bit`` and exits, which
    costs a few milliseconds and does not start a session — detection must not
    launch GAUSS proper.
    """
    try:
        completed = subprocess.run(
            [str(executable), "-h"], capture_output=True, text=True, timeout=timeout
        )
    except (OSError, subprocess.SubprocessError):
        return None
    banner = (completed.stdout or "") + (completed.stderr or "")
    match = re.search(r"GAUSS\s+([0-9]+(?:\.[0-9]+)*)", banner)
    return match.group(1) if match else None


def describe(executable: Path) -> Dict[str, Any]:
    """What this backend can say about itself without starting anything."""
    return {
        "backend": "cli",
        "executable": str(executable),
        "persistent_session": False,
        "note": (
            "The CLI backend runs one process per cell. Values are carried "
            "between cells with GAUSS's own save/load; procedures and "
            "#include state are not."
        ),
    }
