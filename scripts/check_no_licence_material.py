#!/usr/bin/env python
"""Refuse to commit licence material or commercial binaries (brief §30, §33).

EconEnv must never redistribute Stata or EViews, and must never carry a serial
number, licence key or credential into git. This runs as a pre-commit hook over
the staged files.

It is deliberately blunt: a false positive costs one `--no-verify` and a second
look, while a false negative puts a licence key in a public repository forever.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

#: File types that must never enter the repository.
FORBIDDEN_SUFFIXES = {
    ".exe", ".dll", ".so", ".dylib", ".lic", ".key", ".pem", ".p12", ".pfx",
    ".dta", ".wf1", ".wf2", ".edb", ".prg", ".ado", ".mlib", ".stpr",
}

#: Filenames that carry licence material for the two commercial engines.
FORBIDDEN_NAMES = {
    "stata.lic", "stata.key", "eviews.lic", "license.dat", "licence.dat",
    "serial.txt", ".env", "credentials.json",
}

PATTERNS = [
    (re.compile(r"(?i)\bserial\s*(number|no|#)?\s*[:=]\s*\S{6,}"), "a serial number"),
    (re.compile(r"(?i)\blicen[cs]e\s*key\s*[:=]\s*\S{6,}"), "a licence key"),
    # Only a *literal* value counts. `token = f"...{uuid}"` and
    # `token = compute()` are ordinary code, not secrets, so the value must be a
    # quoted string with no interpolation or call syntax in it.
    (
        re.compile(r"""(?i)\b(api[_-]?key|secret|password|passwd|token)\s*[:=]\s*['"][^'"{}()$\s]{12,}['"]"""),
        "a hard-coded credential",
    ),
    (re.compile(r"\b\d{4}-\d{4}-\d{4}-\d{4}\b"), "something shaped like a serial number"),
    (re.compile(r"(?i)stata\s+serial\s+number"), "Stata licence material"),
]

#: Files that legitimately discuss these words.
ALLOWLIST = {
    "scripts/check_no_licence_material.py",
    "LICENSE",
    "docs/troubleshooting.md",
    "docs/faq.md",
    "src/econenv/_logging.py",
    "CHANGELOG.md",
}

TEXT_SUFFIXES = {".py", ".md", ".toml", ".yaml", ".yml", ".cfg", ".txt", ".ipynb", ".cff", ".r", ".R"}


def check(path: Path) -> list[str]:
    problems: list[str] = []
    posix = path.as_posix()
    if posix in ALLOWLIST:
        return problems

    if path.suffix.lower() in FORBIDDEN_SUFFIXES:
        problems.append(f"{posix}: {path.suffix} files are never committed to this repository")
    if path.name.lower() in FORBIDDEN_NAMES:
        problems.append(f"{posix}: this filename carries licence material")

    if path.suffix.lower() not in TEXT_SUFFIXES or not path.is_file():
        return problems

    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return problems

    for pattern, description in PATTERNS:
        match = pattern.search(content)
        if match:
            line = content[: match.start()].count("\n") + 1
            problems.append(f"{posix}:{line}: looks like {description}")
    return problems


def main(argv: list[str]) -> int:
    problems: list[str] = []
    for name in argv:
        problems.extend(check(Path(name)))
    if problems:
        print("Refusing the commit — EconEnv must not carry licence material:\n", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        print(
            "\nIf this is a false positive, add the path to ALLOWLIST in "
            "scripts/check_no_licence_material.py and say why in the commit message.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
