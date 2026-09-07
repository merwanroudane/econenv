"""Generate ``docs/engines/gauss-commands.md`` from the command catalogue.

Same reasoning as the EViews and MATLAB generators: the page and ``%econ
gauss`` are one body of content, so generating the page from the module means a
command can only be wrong in both at once. A test checks the file on disk
matches what this script would write.

Run it after editing ``econenv.engines.gauss_commands``::

    python scripts/gen_gauss_docs.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from econenv.engines import gauss_commands as catalogue  # noqa: E402

TARGET = ROOT / "docs" / "engines" / "gauss-commands.md"

PREAMBLE = """# GAUSS commands for research

GAUSS is the least like the other engines EconEnv drives. It has no DataFrame,
its matrix syntax is its own, and the operators a researcher needs most are not
guessable from a Python or R background. This page is the translation.

Look it up from a cell instead of reading here — same content, no context
switch:

```python
%econ gauss                   # the categories
%econ gauss regression        # ols and friends
%econ gauss find missing      # search everything
```

## The three things that catch everyone out

**1. Every statement ends with a semicolon.** A missing one is a syntax error,
not a warning.

```gauss
x = 5;
```

**2. A bare expression prints nothing.** Where Python echoes the last value,
GAUSS needs to be told:

```gauss
x           /* shows nothing at all */
print x;    /* shows it */
```

**3. `~` joins columns, `|` stacks rows.** This is how a design matrix is
built, and it has no equivalent in the other engines' syntax:

```gauss
X = ones(rows(y),1) ~ x1 ~ x2;   /* constant, then two regressors */
z = a | b;                       /* a on top of b */
```

## And one that looks like a bug

GAUSS **compiles the whole cell before running any of it**. A mistyped name on
the last line means the first line never ran either, so a cell can produce no
output at all rather than a partial result. EconEnv says so explicitly when it
happens, because the natural reading — "my print statement did nothing" — sends
people looking in the wrong place.

## Least squares, annotated

```python
%%gauss -i df -o b
y = df[.,3];                                /* third column            */
X = ones(rows(df),1) ~ df[.,1] ~ df[.,2];   /* constant + regressors   */
b = y / X;                                  /* solve X*b = y           */
print b;
```

`/` is the least-squares solve, not division — it is GAUSS's equivalent of
`numpy.linalg.lstsq`, and it is more accurate than forming `inv(X'X)X'y`
yourself. For standard errors and R-squared use `ols`, which is what
`econenv.compare_ols` calls.

## What a check mark means

An entry marked **✓** was resolved against a live GAUSS through EconEnv while
this page was generated. Operators and keywords cannot be probed that way and
are unmarked; so are the functions belonging to libraries this machine does not
have, which say so in their note.

---
"""

CLOSING = """
---

## When this page does not have it

Ask GAUSS itself, from the notebook:

```python
%%gauss
help ols;
```

GAUSS also ships its full documentation with the installation, and the command
reference there is the authority for arguments this page summarises.

## What does not carry between cells

Values assigned at the top level do — EconEnv saves and reloads them using
GAUSS's own `save`/`load`. **Procedures, `#include`s and library loads do
not**, because each cell runs in a fresh process. Define a `proc` in the same
cell that uses it.

That is a real limit of the command-line backend rather than a choice, and it
is stated rather than worked around: rebuilding a session by replaying earlier
cells would silently re-run their side effects.

---

Related: [GAUSS engine](gauss.md) · [magic commands](../magics.md) ·
[comparison](../comparison.md) · [troubleshooting](../troubleshooting.md)
"""


def render() -> str:
    parts = [PREAMBLE]

    verified = sum(1 for c in catalogue.COMMANDS if c.verified)
    parts.append(
        f"\n## Contents\n\n{len(catalogue.COMMANDS)} commands, {verified} resolved "
        "against a live GAUSS.\n\n"
    )
    for name, description in catalogue.categories().items():
        anchor = description.lower().replace(" ", "-").replace(",", "").replace("/", "")
        parts.append(f"- [{description}](#{anchor}) — `%econ gauss {name}`\n")

    parts.append("\n| Commands | Library |\n|---|---|\n")
    for library, count in catalogue.libraries().items():
        label = "the GAUSS language itself" if library == catalogue.BASE else library
        parts.append(f"| {count} | {label} |\n")

    for name, description in catalogue.categories().items():
        commands = catalogue.by_category(name)
        if not commands:
            continue
        parts.append(f"\n\n## {description}\n\n")
        parts.append(f"Look these up from a cell with `%econ gauss {name}`.\n\n")
        parts.append("| Command | What it does | Needs | |\n")
        parts.append("|---|---|---|---|\n")
        for command in commands:
            does = command.does.replace("|", "\\|")
            if command.notes:
                does += f" <br><sub>{command.notes}</sub>"
            needs = "—" if command.library == catalogue.BASE else command.library
            tick = "✓" if command.verified else ""
            display = command.name.replace("|", "\\|")
            parts.append(f"| `{display}` | {does} | {needs} | {tick} |\n")

        parts.append("\n```gauss\n")
        for command in commands[:4]:
            parts.append(f"{command.example}\n")
        parts.append("```\n")

    parts.append(CLOSING)
    return "".join(parts)


def main() -> int:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    text = render()
    TARGET.write_text(text, encoding="utf-8")
    print(f"wrote {TARGET.relative_to(ROOT)}  ({len(text):,} bytes)")
    print(f"  {len(catalogue.COMMANDS)} commands in {len(catalogue.CATEGORIES)} categories")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
