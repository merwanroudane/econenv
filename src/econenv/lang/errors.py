"""EconLang's errors, which are meant to be read by an economist.

The specification is unusually specific about this (sections 80-82), and rightly: the
whole point of a research language is that someone who knows econometrics but
not software engineering can use it. A stack trace is a failure of the design,
not a diagnostic.

Every error carries a code from a fixed taxonomy, says what happened and where,
guesses at the cause, and — where it can — offers the corrected line:

    E101 — Variable not found

      GDP is not in the active dataset.
      at line 7, column 9

      Did you mean:  gdp

      Suggested fix:
        y = gdp

Codes are grouped so the first digit says which layer failed, which makes them
searchable and keeps the numbering from drifting:

    E1xx  data          E4xx  econometric     E7xx  capability
    E2xx  syntax        E5xx  backend         E8xx  export
    E3xx  semantic      E6xx  execution       E9xx  internal
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from ..exceptions import EconEnvError

#: The taxonomy, written out so a code can never be invented at a call site.
CODES = {
    # data
    "E101": "Variable not found",
    "E102": "Dataset not loaded",
    "E103": "Duplicate time index",
    "E104": "Invalid data type",
    "E105": "Missing values",
    "E106": "File not found",
    "E107": "Unsupported file format",
    "E108": "Gaps in the time index",
    "E109": "Observations are not sorted by time",
    # syntax
    "E201": "Invalid syntax",
    "E202": "Unexpected keyword",
    "E203": "Missing block",
    "E204": "Bad indentation",
    "E205": "Unterminated string",
    # semantic
    "E301": "Undefined model",
    "E302": "Invalid model option",
    "E303": "Duplicate model name",
    "E304": "Missing required option",
    # econometric
    "E401": "Insufficient observations",
    "E402": "Perfect multicollinearity",
    "E403": "Singular matrix",
    "E404": "Nonstationary series",
    "E405": "Panel structure missing",
    "E406": "Invalid instruments",
    "E407": "Dependent variable also appears as a regressor",
    # backend
    "E501": "Backend unavailable",
    "E502": "Unsupported backend version",
    "E503": "Required package unavailable",
    # execution
    "E601": "Execution timeout",
    "E602": "Backend process failed",
    # capability
    "E701": "Estimator unsupported by this backend",
    "E702": "Option unsupported by this backend",
    # export
    "E801": "Export format unavailable",
    # internal
    "E901": "Internal error",
}


@dataclass
class Location:
    """Where in the source the problem is."""

    line: int
    column: int = 0
    source_line: str = ""

    def __str__(self) -> str:
        where = f"line {self.line}"
        if self.column:
            where += f", column {self.column}"
        return where


class EconLangError(EconEnvError):
    """A problem in an EconLang program, reported the way §81 asks for.

    Subclasses :class:`~econenv.exceptions.EconEnvError` so existing handling
    keeps working; the difference is entirely in how it presents itself.
    """

    def __init__(
        self,
        code: str,
        detail: str,
        *,
        location: Optional[Location] = None,
        cause: Optional[str] = None,
        fix: Optional[str] = None,
        example: Optional[str] = None,
        did_you_mean: Sequence[str] = (),
        available: Sequence[str] = (),
        docs: Optional[str] = None,
        raw: Optional[BaseException] = None,
    ) -> None:
        self.code = code
        self.title = CODES.get(code, "Error")
        self.detail = detail
        self.location = location
        self.cause = cause
        self.fix = fix
        self.example = example
        self.did_you_mean = list(did_you_mean)
        self.available = list(available)
        self.docs = docs
        # EconEnvError's own signature does not take `raw`; keep the
        # original exception reachable without changing that contract.
        self.raw = raw
        super().__init__(self.render())

    def render(self) -> str:
        """The whole message, laid out to be read top to bottom."""
        out = [f"{self.code} — {self.title}", ""]
        out.append(f"  {self.detail}")
        if self.location is not None:
            out.append(f"  at {self.location}")
            if self.location.source_line:
                out.append("")
                out.append(f"    {self.location.source_line.rstrip()}")
                if self.location.column:
                    out.append("    " + " " * (self.location.column - 1) + "^")
        if self.cause:
            out += ["", f"  Probable cause: {self.cause}"]
        if self.did_you_mean:
            out += ["", "  Did you mean:"]
            out += [f"    {name}" for name in self.did_you_mean]
        if self.available:
            shown = self.available[:12]
            out += ["", "  Available:"]
            out += [f"    {name}" for name in shown]
            if len(self.available) > len(shown):
                out.append(f"    ... and {len(self.available) - len(shown)} more")
        if self.fix:
            out += ["", "  Suggested fix:"]
            out += [f"    {line}" for line in self.fix.splitlines()]
        if self.example:
            out += ["", "  For example:"]
            out += [f"    {line}" for line in self.example.splitlines()]
        if self.docs:
            out += ["", f"  See: {self.docs}"]
        return "\n".join(out)

    def __str__(self) -> str:
        return self.render()


@dataclass
class LangWarning:
    """Something worth saying that does not stop the run (section 83)."""

    code: str
    message: str
    location: Optional[Location] = None
    fix: Optional[str] = None

    def __str__(self) -> str:
        where = f" ({self.location})" if self.location else ""
        text = f"{self.code} — {self.message}{where}"
        if self.fix:
            text += f"\n    {self.fix}"
        return text


@dataclass
class Diagnostics:
    """Warnings collected across a run, so none of them are lost."""

    warnings: List[LangWarning] = field(default_factory=list)

    def warn(self, code: str, message: str, **kwargs) -> None:
        self.warnings.append(LangWarning(code, message, **kwargs))

    def __bool__(self) -> bool:
        return bool(self.warnings)

    def __iter__(self):
        return iter(self.warnings)

    def __len__(self) -> int:
        return len(self.warnings)


def suggest(name: str, candidates: Sequence[str], limit: int = 3) -> List[str]:
    """Names close to *name*, for "did you mean".

    Case is checked first and separately: ``GDP`` for ``gdp`` is the single most
    common mistake in a language whose data comes from spreadsheets, and it
    deserves to be the first suggestion rather than one of several.
    """
    exact_but_for_case = [c for c in candidates if c.lower() == name.lower() and c != name]
    if exact_but_for_case:
        return exact_but_for_case[:limit]
    return difflib.get_close_matches(name, list(candidates), n=limit, cutoff=0.6)


def variable_not_found(
    name: str, available: Sequence[str], location: Optional[Location] = None
) -> EconLangError:
    """The most common error in the language, so it is built once here."""
    near = suggest(name, available)
    fix = None
    if near and location is not None and location.source_line:
        fix = location.source_line.strip().replace(name, near[0])
    return EconLangError(
        "E101",
        f"{name!r} is not in the active dataset.",
        location=location,
        did_you_mean=near,
        available=list(available),
        fix=fix,
    )
