"""Generate ``docs/engines/matlab-commands.md`` from the command catalogue.

Same reasoning as ``gen_eviews_docs.py``: the page and the ``%econ matlab``
lookup are one body of content, so generating the page from the module means a
command can only be wrong in both at once. A test checks the file on disk
matches what this script would write.

Run it after editing ``econenv.engines.matlab_commands``::

    python scripts/gen_matlab_docs.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from econenv.engines import matlab_commands as catalogue  # noqa: E402

TARGET = ROOT / "docs" / "engines" / "matlab-commands.md"

PREAMBLE = """# MATLAB commands for research

MATLAB is not short of documentation. It is short of a way to answer, without
leaving the notebook, the question a researcher actually has: *is there a
function for this, is it in a toolbox I have, and what does the call look
like?*

That is what this page and `%econ matlab` are for. They are the same content —
look it up from a cell instead of reading here:

```python
%econ matlab                     # the categories
%econ matlab timeseries          # unit roots, ARIMA, VAR
%econ matlab find cointegration  # search everything
```

## Toolboxes

Most of MATLAB's econometrics lives in toolboxes that are licensed separately,
so every entry names the one it needs. Check what you have:

```python
%%matlab
ver                              % release and every licensed toolbox
license('test', 'Econometrics_Toolbox')
which adftest                    % where a function came from
```

A function you do not have licensed fails with `Unrecognized function or
variable`, which reads like a typo and is not one — that is why the toolbox is
named here rather than left to be discovered.

## What a check mark means

An entry marked **✓** was resolved against a live MATLAB through EconEnv while
this page was generated: `exist` for functions, `which -all` for methods that
belong to a class rather than sitting on the path. Unmarked entries are
documented syntax that this machine could not confirm.

## Getting values in and out

```python
%%matlab -i df -o coefs
mdl = fitlm(df, 'y ~ x1 + x2');
coefs = mdl.Coefficients;
```

`-i` sends a Python object in; `-o` brings a MATLAB variable back as its
natural Python type — a scalar is a number, a matrix is a NumPy array, a table
is a DataFrame. The full type tables are in [matlab.md](matlab.md).

---
"""

CLOSING = """
---

## When this page does not have it

Ask MATLAB itself, from the notebook:

```python
%%matlab
help fitlm            % one-screen summary
lookfor cointegration % search every function's summary line
which wcoherence      % where it lives, and so which toolbox
```

`lookfor` is the one to reach for: it searches the first line of every function
on the path, which is how you find a function whose name you do not know.

## If a command runs but you see nothing

Tell EconEnv — that is a bug here rather than in what you typed. Output,
figures, or a warning saying something could not be read: silence is never
correct. <https://github.com/merwanroudane/econenv/issues>

---

Related: [MATLAB engine](matlab.md) · [magic commands](../magics.md) ·
[export](../export.md) · [troubleshooting](../troubleshooting.md)
"""


def render() -> str:
    parts = [PREAMBLE]

    verified = sum(1 for c in catalogue.COMMANDS if c.verified)
    parts.append(
        f"\n## Contents\n\n{len(catalogue.COMMANDS)} commands, {verified} resolved "
        "against a live MATLAB.\n\n"
    )
    for name, description in catalogue.categories().items():
        anchor = description.lower().replace(" ", "-").replace(",", "").replace("/", "")
        parts.append(f"- [{description}](#{anchor}) — `%econ matlab {name}`\n")

    parts.append("\nToolboxes these commands need:\n\n")
    parts.append("| Commands | Toolbox |\n|---|---|\n")
    for toolbox, count in catalogue.toolboxes().items():
        label = "ships with MATLAB" if toolbox == catalogue.BASE else toolbox
        parts.append(f"| {count} | {label} |\n")

    for name, description in catalogue.categories().items():
        commands = catalogue.by_category(name)
        if not commands:
            continue
        parts.append(f"\n\n## {description}\n\n")
        parts.append(f"Look these up from a cell with `%econ matlab {name}`.\n\n")
        parts.append("| Command | What it does | Needs | |\n")
        parts.append("|---|---|---|---|\n")
        for command in commands:
            does = command.does.replace("|", "\\|")
            if command.notes:
                does += f" <br><sub>{command.notes}</sub>"
            needs = "—" if command.toolbox == catalogue.BASE else command.toolbox
            tick = "✓" if command.verified else ""
            parts.append(f"| `{command.name}` | {does} | {needs} | {tick} |\n")

        parts.append("\n```python\n")
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
