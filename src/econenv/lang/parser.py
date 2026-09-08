"""EconLang source to AST.

A recursive-descent parser, because the grammar is small and hand-written
parsing is what lets each failure carry the line, the column and a suggested
correction — which §81 asks for and a generated parser makes awkward.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .errors import EconLangError, Location
from .lexer import Kind, LexError, Token, tokenize
from .nodes import Command, DataLoad, Model, PanelDecl, Program, Project, Setting, TimeDecl

#: Statements that introduce a block and are otherwise ordinary words, so they
#: are only keywords in the first position of a line.
_BLOCK_VERBS = {"project", "data", "set", "model"}

#: One-line commands. Each takes a target name, except `doctor`.
_COMMANDS = {"show", "dryrun", "explain", "export", "compare", "doctor", "summary", "translate"}

#: Words that read as yes/no in an option, since a researcher writes
#: `intercept = yes` far more naturally than `intercept = true`.
_TRUE = {"yes", "true", "on"}
_FALSE = {"no", "false", "off"}


def parse(source: str) -> Program:
    """Parse *source* into a :class:`Program`."""
    try:
        tokens = tokenize(source)
    except LexError as exc:
        raise EconLangError(
            exc.code,
            exc.message,
            location=_locate(source, exc.line, exc.column),
        ) from None
    return _Parser(tokens, source).program()


def _locate(source: str, line: int, column: int = 0) -> Location:
    lines = source.splitlines()
    text = lines[line - 1] if 0 < line <= len(lines) else ""
    return Location(line=line, column=column, source_line=text)


class _Parser:
    def __init__(self, tokens: List[Token], source: str) -> None:
        self.tokens = tokens
        self.source = source
        self.index = 0

    # ------------------------------------------------------------------ #
    # token helpers
    # ------------------------------------------------------------------ #
    @property
    def current(self) -> Token:
        return self.tokens[self.index]

    def at(self, kind: Kind) -> bool:
        return self.current.kind is kind

    def advance(self) -> Token:
        token = self.current
        if token.kind is not Kind.END:
            self.index += 1
        return token

    def accept(self, kind: Kind) -> Optional[Token]:
        if self.at(kind):
            return self.advance()
        return None

    def expect(self, kind: Kind, what: str) -> Token:
        if not self.at(kind):
            raise self.error("E201", f"Expected {what}, found {self._describe(self.current)}.")
        return self.advance()

    @staticmethod
    def _describe(token: Token) -> str:
        if token.kind is Kind.END:
            return "the end of the file"
        if token.kind is Kind.NEWLINE:
            return "the end of the line"
        if token.kind is Kind.INDENT:
            return "an indented block"
        if token.kind is Kind.DEDENT:
            return "the end of a block"
        return repr(token.text)

    def error(self, code: str, detail: str, **kwargs) -> EconLangError:
        token = self.current
        return EconLangError(
            code,
            detail,
            location=_locate(self.source, token.line, token.column),
            **kwargs,
        )

    def location(self) -> Location:
        return _locate(self.source, self.current.line, self.current.column)

    def skip_newlines(self) -> None:
        while self.at(Kind.NEWLINE):
            self.advance()

    # ------------------------------------------------------------------ #
    # grammar
    # ------------------------------------------------------------------ #
    def program(self) -> Program:
        statements = []
        self.skip_newlines()
        while not self.at(Kind.END):
            statements.append(self.statement())
            self.skip_newlines()
        return Program(statements=statements, source=self.source)

    def statement(self):
        if not self.at(Kind.NAME):
            raise self.error(
                "E201",
                f"A statement starts with a keyword; found {self._describe(self.current)}.",
                example='data "macro.csv"',
            )
        word = self.current.text.lower()

        if word == "project":
            return self.project()
        if word == "data":
            return self.data()
        if word == "set":
            return self.setting_block()
        if word == "model":
            return self.model()
        if word in _COMMANDS:
            return self.command()

        # `key = value` at the top level is a project setting
        if self.tokens[self.index + 1].kind is Kind.EQUALS:
            return self.assignment()

        raise self.error(
            "E202",
            f"{self.current.text!r} is not a statement keyword.",
            available=sorted(_BLOCK_VERBS | _COMMANDS),
            example="model ols baseline:",
        )

    def project(self) -> Project:
        location = self.location()
        self.advance()
        name = self.expect(Kind.STRING, "a project name in quotes").text
        return Project(name=name, location=location)

    def assignment(self) -> Setting:
        location = self.location()
        key = self.advance().text
        self.expect(Kind.EQUALS, "'='")
        return Setting(key=key, value=self.value(), location=location)

    def data(self) -> DataLoad:
        location = self.location()
        self.advance()
        # `data load "file"` and `data "file"` mean the same thing
        if self.at(Kind.NAME) and self.current.text.lower() == "load":
            self.advance()
        if not self.at(Kind.STRING):
            raise self.error(
                "E201",
                "`data` needs a file path in quotes.",
                example='data "macro.csv"',
            )
        path = self.advance().text
        options, where = self.block() if self.at(Kind.COLON) else ({}, {})
        return DataLoad(path=path, options=options, option_locations=where, location=location)

    def setting_block(self):
        location = self.location()
        self.advance()
        if not self.at(Kind.NAME):
            raise self.error(
                "E201",
                "`set` needs to say what is being set.",
                example="set time:\n    variable = year",
            )
        what = self.advance().text.lower()
        options, _ = self.block()

        if what == "time":
            if "variable" not in options:
                raise EconLangError(
                    "E304",
                    "`set time` needs a `variable`.",
                    location=location,
                    example="set time:\n    variable = year\n    frequency = annual",
                )
            return TimeDecl(
                variable=str(options["variable"]),
                frequency=_optional_str(options.get("frequency")),
                location=location,
            )
        if what == "panel":
            missing = [key for key in ("id", "time") if key not in options]
            if missing:
                raise EconLangError(
                    "E304",
                    f"`set panel` needs {' and '.join(missing)}.",
                    location=location,
                    example="set panel:\n    id = country\n    time = year",
                )
            return PanelDecl(
                entity=str(options["id"]), time=str(options["time"]), location=location
            )

        raise EconLangError(
            "E202",
            f"`set {what}` is not something EconLang knows how to set.",
            location=location,
            available=["time", "panel"],
        )

    def model(self) -> Model:
        location = self.location()
        self.advance()
        if not self.at(Kind.NAME):
            raise self.error(
                "E201",
                "`model` needs an estimator, such as `ols`.",
                example="model ols baseline:\n    y = gdp\n    x = inflation",
            )
        estimator = self.advance().text.lower()

        name = estimator
        if self.at(Kind.NAME):
            name = self.advance().text
        options, where = self.block()
        return Model(
            estimator=estimator,
            name=name,
            options=options,
            option_locations=where,
            location=location,
        )

    def command(self) -> Command:
        location = self.location()
        verb = self.advance().text.lower()
        arguments: List[Any] = []

        # `show code m1` — the second word refines the verb
        if verb == "show" and self.at(Kind.NAME):
            verb = f"show {self.advance().text.lower()}"

        target = self.advance().text if self.at(Kind.NAME) else None
        while not self.at(Kind.NEWLINE) and not self.at(Kind.END):
            arguments.append(self.value())
            self.accept(Kind.COMMA)
        return Command(verb=verb, target=target, arguments=arguments, location=location)

    # ------------------------------------------------------------------ #
    # blocks and values
    # ------------------------------------------------------------------ #
    def block(self) -> tuple:
        """``:`` then an indented run of ``key = value`` lines.

        Returns the options and where each one was written.
        """
        self.expect(Kind.COLON, "':' to open the block")
        self.expect(Kind.NEWLINE, "a new line after ':'")
        self.skip_newlines()
        if not self.at(Kind.INDENT):
            raise self.error(
                "E203",
                "This block is empty — the lines after ':' need to be indented.",
                example="model ols m1:\n    y = gdp\n    x = inflation",
            )
        self.advance()

        options: Dict[str, Any] = {}
        where: Dict[str, Location] = {}
        while not self.at(Kind.DEDENT) and not self.at(Kind.END):
            self.skip_newlines()
            if self.at(Kind.DEDENT) or self.at(Kind.END):
                break
            key_token = self.expect(Kind.NAME, "an option name")
            key = key_token.text.lower()
            if key in options:
                raise EconLangError(
                    "E302",
                    f"{key!r} is given twice in this block.",
                    location=_locate(self.source, key_token.line, key_token.column),
                )
            where[key] = _locate(self.source, key_token.line, key_token.column)
            self.expect(Kind.EQUALS, f"'=' after {key!r}")
            options[key] = self.value()
            if not self.at(Kind.DEDENT) and not self.at(Kind.END):
                self.expect(Kind.NEWLINE, "a new line after the value")
            self.skip_newlines()
        self.accept(Kind.DEDENT)
        return options, where

    def value(self) -> Any:
        """A single value, or a comma-separated list of them."""
        first = self.single_value()
        if not self.at(Kind.COMMA):
            return first
        items = [first]
        while self.accept(Kind.COMMA):
            self.skip_newlines()
            items.append(self.single_value())
        return items

    def single_value(self) -> Any:
        token = self.current
        if token.kind is Kind.STRING:
            self.advance()
            return token.text
        if token.kind is Kind.NUMBER:
            self.advance()
            return float(token.text) if "." in token.text else int(token.text)
        if token.kind is Kind.NAME:
            self.advance()
            lowered = token.text.lower()
            if lowered in _TRUE:
                return True
            if lowered in _FALSE:
                return False
            return token.text
        raise self.error("E201", f"Expected a value, found {self._describe(token)}.")


def _optional_str(value: Any) -> Optional[str]:
    return None if value is None else str(value)
