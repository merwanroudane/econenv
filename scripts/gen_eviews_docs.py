"""Generate ``docs/engines/eviews-commands.md`` from the command catalogue.

The page and the ``%econ eviews`` lookup are the same content in two places,
which is exactly how documentation goes stale. Generating one from the other
means a command can only be wrong in both at once, and a test checks the file
on disk matches what this script would write.

Run it after editing ``econenv.engines.eviews_commands``::

    python scripts/gen_eviews_docs.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from econenv.engines import eviews_commands as catalogue  # noqa: E402

TARGET = ROOT / "docs" / "engines" / "eviews-commands.md"

PREAMBLE = """# EViews commands for people who use the GUI

In EViews you click. In a notebook there is nothing to click, and that is the
only real obstacle to using EconEnv: you already know *what* you want to do,
just not how to type it.

This page is the translation. Every entry gives the menu path you already know,
the command it becomes, what it does in plain language, and a line you can copy.

**You do not have to read it.** Look things up from inside the notebook
instead, while you are writing the cell:

```python
%econ eviews                      # the list of tasks
%econ eviews graph                # everything about plotting
%econ eviews find cointegration   # search all of it
```

Same content, no browser, no context switch.

## The one idea that makes EViews commands guessable

EViews objects work like this:

```
object_name.what_you_want
```

`eq1.output` shows an equation's results. `x.line` plots a series. `v1.impulse`
draws impulse responses. So:

- Anything in an object's **View** menu is `object.thatview`.
- Anything in its **Proc** menu is `object.thatproc`, usually followed by a
  name for whatever it creates.

That single rule covers most of this page. Once you see it, you can often guess
a command you have never used.

Three more conventions:

- `c` in a regressor list means **the constant** — not a variable called c.
- Options go in parentheses right after the command: `ls(cov=white) y c x`.
- `x`, `y`, `z` are series; `eq1` an equation; `g1` a group; `v1` a VAR.

## A first cell, annotated

```python
%%eviews
wfcreate q 1990Q1 2020Q4      ' a quarterly workfile, 1990Q1 to 2020Q4
series x = nrnd               ' a random series, to have something to look at
series y = 5 + 2*x + nrnd     ' y depends on x
equation eq1.ls y c x         ' regress y on a constant and x
eq1.output                    ' show the results table
line y                        ' plot y
```

Six lines, and you have a workfile, data, a regression, its output and a chart.
In the GUI that is about twenty clicks across five dialogs.

A `'` starts a comment in EViews, exactly like `#` in Python.

## Three ways to draw the same plot

This trips people up, because the GUI hides the distinction. All three work:

```python
%%eviews
line x            ' command form  - quickest
x.line            ' view form     - matches the View menu
graph gr1.line x  ' object form   - keeps the graph so you can edit it
```

Use the object form when you want to add a title or change colours afterwards.
Otherwise use whichever you find easier to remember.

## What a check mark means

An entry marked **✓** was run against EViews 13 through EconEnv while this page
was generated, and it worked. Unmarked entries are EViews' documented syntax
that this machine could not exercise — nearly all of them panel commands, which
need a panel-structured workfile.

---
"""

CLOSING = """
---

## When this page does not have it

Ask EViews itself. It has help for every command:

```python
%%eviews
help ls
help arch
```

And in the EViews window, the status line along the bottom echoes the command
for many things you click. Click once in the GUI, read the line, and you have
the syntax — which is often the fastest way to learn the command for something
unusual.

## If a command runs but you see nothing

Tell EconEnv, because that is a bug in EconEnv rather than in what you typed.
Every display command should produce either output, a plot, or a warning saying
it could not be read. Silence is never correct:
<https://github.com/merwanroudane/econenv/issues>

---

Related: [EViews engine](eviews.md) · [magic commands](../magics.md) ·
[troubleshooting](../troubleshooting.md)
"""


def render() -> str:
    parts = [PREAMBLE]

    parts.append("\n## Contents\n\n")
    for name, description in catalogue.categories().items():
        anchor = description.lower().replace(" ", "-").replace(",", "")
        parts.append(f"- [{description}](#{anchor}) — `%econ eviews {name}`\n")

    for name, description in catalogue.categories().items():
        commands = catalogue.by_category(name)
        if not commands:
            continue
        parts.append(f"\n\n## {description}\n\n")
        parts.append(f"Look these up from a cell with `%econ eviews {name}`.\n\n")
        parts.append("| You would click | Command | What it does | |\n")
        parts.append("|---|---|---|---|\n")
        for command in commands:
            gui = command.gui.replace("|", "\\|")
            does = command.does.replace("|", "\\|")
            example = command.example.replace("|", "\\|").replace("\n", " ")
            tick = "✓" if command.verified else ""
            parts.append(f"| {gui} | `{example}` | {does} | {tick} |\n")

    parts.append(CLOSING)
    return "".join(parts)


def main() -> int:
    text = render()
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    previous = TARGET.read_text(encoding="utf-8") if TARGET.exists() else None
    TARGET.write_text(text, encoding="utf-8")
    verified = sum(1 for c in catalogue.COMMANDS if c.verified)
    print(f"wrote {TARGET.relative_to(ROOT)}")
    print(f"  {len(catalogue.COMMANDS)} commands, {verified} verified against EViews 13")
    print(f"  {len(text.splitlines())} lines")
    print("  unchanged" if previous == text else "  updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
