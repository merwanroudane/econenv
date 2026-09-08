"""Turning EconLang source into tokens.

The syntax rules are §5: English keywords, blocks introduced by ``:``,
indentation carries meaning, ``#`` starts a comment, strings are quoted, lists
are comma-separated.

Indentation is handled the way Python's own tokenizer does it — a stack of
levels emitting INDENT and DEDENT — because that is the behaviour users of an
indentation-sensitive language already expect, including the error when a block
is indented inconsistently.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class Kind(Enum):
    NAME = "name"
    NUMBER = "number"
    STRING = "string"
    COLON = "colon"
    EQUALS = "equals"
    COMMA = "comma"
    TILDE = "tilde"
    PLUS = "plus"
    NEWLINE = "newline"
    INDENT = "indent"
    DEDENT = "dedent"
    END = "end"


@dataclass
class Token:
    kind: Kind
    text: str
    line: int
    column: int

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"{self.kind.value}({self.text!r})@{self.line}:{self.column}"


#: A bare word: a keyword, a variable name, or a value like ``annual``.
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*")
#: A number, including a negative or a decimal.
_NUMBER = re.compile(r"-?\d+(\.\d+)?")

_SIMPLE = {
    ":": Kind.COLON,
    "=": Kind.EQUALS,
    ",": Kind.COMMA,
    "~": Kind.TILDE,
    "+": Kind.PLUS,
}


class LexError(Exception):
    """Raised with a line and column; the parser turns it into an EconLangError."""

    def __init__(self, message: str, line: int, column: int, code: str = "E201") -> None:
        super().__init__(message)
        self.message = message
        self.line = line
        self.column = column
        self.code = code


def tokenize(source: str) -> List[Token]:
    """Tokens for *source*, with INDENT/DEDENT where the indentation changes."""
    tokens: List[Token] = []
    levels = [0]
    lines = source.splitlines()

    for number, raw in enumerate(lines, start=1):
        # A line that is blank or only a comment has no indentation meaning at
        # all — treating it as a dedent would end a block on a blank line.
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = _indent_width(raw, number)
        if indent > levels[-1]:
            levels.append(indent)
            tokens.append(Token(Kind.INDENT, "", number, 1))
        else:
            while indent < levels[-1]:
                levels.pop()
                tokens.append(Token(Kind.DEDENT, "", number, 1))
            if indent != levels[-1]:
                raise LexError(
                    "This line is indented to a level that does not match any open block.",
                    number,
                    indent + 1,
                    code="E204",
                )

        tokens.extend(_scan_line(raw, number))
        tokens.append(Token(Kind.NEWLINE, "", number, len(raw) + 1))

    while len(levels) > 1:
        levels.pop()
        tokens.append(Token(Kind.DEDENT, "", len(lines) + 1, 1))
    tokens.append(Token(Kind.END, "", len(lines) + 1, 1))
    return tokens


def _indent_width(raw: str, line: int) -> int:
    """Leading whitespace as a column count, with tabs refused.

    Mixing tabs and spaces is the classic way an indentation-sensitive language
    becomes unreadable, and guessing a tab width would make the same file mean
    different things in different editors.
    """
    width = 0
    for character in raw:
        if character == " ":
            width += 1
        elif character == "\t":
            raise LexError(
                "Indent with spaces, not tabs — a tab means a different width in "
                "every editor, so the same file would parse differently.",
                line,
                width + 1,
                code="E204",
            )
        else:
            break
    return width


def _scan_line(raw: str, line: int) -> List[Token]:
    """Every token on one line, comments and trailing whitespace removed."""
    out: List[Token] = []
    index = 0
    length = len(raw)

    while index < length:
        character = raw[index]

        if character in " \t":
            index += 1
            continue
        if character == "#":
            break

        if character in ('"', "'"):
            text, index = _scan_string(raw, index, line)
            out.append(Token(Kind.STRING, text, line, index))
            continue

        if character in _SIMPLE:
            out.append(Token(_SIMPLE[character], character, line, index + 1))
            index += 1
            continue

        match = _NUMBER.match(raw, index)
        # A leading '-' is only a number when it actually starts one; otherwise
        # it belongs to a name or is a stray character.
        if match and (character != "-" or match.end() > index + 1):
            out.append(Token(Kind.NUMBER, match.group(0), line, index + 1))
            index = match.end()
            continue

        match = _NAME.match(raw, index)
        if match:
            out.append(Token(Kind.NAME, match.group(0), line, index + 1))
            index = match.end()
            continue

        raise LexError(
            f"{character!r} does not belong here.",
            line,
            index + 1,
        )
    return out


def _scan_string(raw: str, start: int, line: int) -> tuple:
    """A quoted string, returning its contents and the index after the closer."""
    quote = raw[start]
    index = start + 1
    out: List[str] = []
    while index < len(raw):
        character = raw[index]
        if character == "\\" and index + 1 < len(raw):
            out.append(raw[index + 1])
            index += 2
            continue
        if character == quote:
            return "".join(out), index + 1
        out.append(character)
        index += 1
    raise LexError(
        "This string is never closed.",
        line,
        start + 1,
        code="E205",
    )


def describe(tokens: List[Token], limit: Optional[int] = None) -> str:  # pragma: no cover
    """Tokens as text, for debugging a parse."""
    shown = tokens[:limit] if limit else tokens
    return " ".join(repr(token) for token in shown)
