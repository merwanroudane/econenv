"""EconEnv exception hierarchy.

Every error raised by EconEnv derives from :class:`EconEnvError`, so callers can
guard a whole multi-engine workflow with a single ``except``.

Vendor errors are *translated*, never swallowed: the human-readable message is
rewritten into something an econometrician can act on, while the original
exception stays reachable through :attr:`EngineError.raw`.
"""

from __future__ import annotations

from typing import Any, Optional


class EconEnvError(Exception):
    """Base class for every EconEnv error."""


class ConfigurationError(EconEnvError):
    """The user's configuration is malformed or contradictory."""


class EngineError(EconEnvError):
    """Base class for anything that goes wrong inside an engine.

    Parameters
    ----------
    message:
        Message shown to the user.
    engine:
        Engine name (``"r"``, ``"stata"``, ``"eviews"`` ...).
    raw:
        The original vendor exception, kept verbatim so nothing is lost.
    hint:
        A concrete next action, when one exists.
    """

    def __init__(
        self,
        message: str,
        *,
        engine: Optional[str] = None,
        raw: Optional[BaseException] = None,
        hint: Optional[str] = None,
    ) -> None:
        self.engine = engine
        self.raw = raw
        self.hint = hint
        parts = [f"[{engine}] {message}" if engine else message]
        if hint:
            parts.append(f"Hint: {hint}")
        super().__init__("\n".join(parts))


class EngineNotFoundError(EngineError):
    """The engine is not registered under that name."""


class EngineUnavailableError(EngineError):
    """The software is not installed, or not usable on this platform."""


class EngineNotConfiguredError(EngineError):
    """The software exists but EconEnv has not been pointed at it yet."""


class EngineStartError(EngineError):
    """The engine could not be started (licence, initialisation, COM ...)."""


class EngineNotStartedError(EngineError):
    """An operation needing a live session was attempted before ``start()``."""


class EngineExecutionError(EngineError):
    """The engine ran the code and rejected it.

    Attributes
    ----------
    code:
        The source that failed, verbatim.
    stdout, stderr:
        Whatever the engine produced before failing.
    """

    def __init__(
        self,
        message: str,
        *,
        engine: Optional[str] = None,
        code: str = "",
        stdout: str = "",
        stderr: str = "",
        raw: Optional[BaseException] = None,
        hint: Optional[str] = None,
    ) -> None:
        self.code = code
        self.stdout = stdout
        self.stderr = stderr
        super().__init__(message, engine=engine, raw=raw, hint=hint)


class EngineTimeoutError(EngineError):
    """The engine did not answer within the allotted time."""


class SessionError(EngineError):
    """The persistent session died or is in an unusable state."""


class DataTransferError(EconEnvError):
    """A dataset could not be moved between Python and an engine."""

    def __init__(
        self,
        message: str,
        *,
        engine: Optional[str] = None,
        name: Optional[str] = None,
        raw: Optional[BaseException] = None,
        hint: Optional[str] = None,
    ) -> None:
        self.engine = engine
        self.name = name
        self.raw = raw
        self.hint = hint
        prefix = f"[{engine}] " if engine else ""
        subject = f"{prefix}{name!r}: " if name else prefix
        msg = f"{subject}{message}"
        if hint:
            msg += f"\nHint: {hint}"
        super().__init__(msg)


class UnsupportedDataTypeError(DataTransferError):
    """A column's dtype has no faithful representation in the target engine."""


class LossyConversionError(DataTransferError):
    """A conversion would silently lose information and was refused.

    EconEnv warns for recoverable narrowing and raises this only when the value
    itself would change (brief §11: no silent dangerous conversions).
    """


class ModelSpecificationError(EconEnvError):
    """A :class:`~econenv.models.spec.ModelSpec` is invalid or untranslatable."""


class CapabilityError(EconEnvError):
    """The engine cannot do what was asked of it, and says so up front."""


def describe(exc: BaseException) -> str:
    """Render *exc* as a single compact line, including its type."""
    text = str(exc).strip().replace("\n", " ")
    return f"{type(exc).__name__}: {text}" if text else type(exc).__name__


def com_message(exc: BaseException) -> Optional[str]:
    """Pull the human-readable description out of a ``comtypes`` ``COMError``.

    ``COMError.args`` is ``(hresult, text, (description, source, ...))`` and the
    third element carries the message EViews actually wrote. Returns ``None``
    when *exc* is not shaped like a ``COMError``.
    """
    args: Any = getattr(exc, "args", ())
    if len(args) >= 3 and isinstance(args[2], tuple) and args[2]:
        first = args[2][0]
        if isinstance(first, str) and first.strip():
            return first.strip()
    return None
