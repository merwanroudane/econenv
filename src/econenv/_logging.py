"""Logging for EconEnv.

Everything goes through the ``econenv`` logger hierarchy. Nothing is configured
at import time — a library that reconfigures the root logger is a library that
breaks somebody's notebook.

Brief §33: licence keys, serial numbers and credentials must never be logged.
:func:`redact` is applied to anything that could plausibly carry one.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Optional

_ROOT_NAME = "econenv"

# Patterns that must never reach a log record.
_REDACTIONS = [
    (re.compile(r"(?i)\b(serial|licen[cs]e|key|token|password|secret)\b\s*[:=]\s*\S+"), r"\1=***"),
    (re.compile(r"\b\d{4}-\d{4}-\d{4}-\d{4}\b"), "****-****-****-****"),
]


def redact(text: str) -> str:
    """Blank out anything that looks like a credential or serial number."""
    for pattern, replacement in _REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


class _RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        return True


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return the ``econenv`` logger, or a child of it."""
    logger = logging.getLogger(_ROOT_NAME if name is None else f"{_ROOT_NAME}.{name}")
    if not any(isinstance(f, _RedactingFilter) for f in logger.filters):
        logger.addFilter(_RedactingFilter())
    return logger


def configure(level: str = "WARNING", *, force: bool = False) -> logging.Logger:
    """Attach a stderr handler to the ``econenv`` logger.

    Called by the CLI and by ``%econ config log <level>``. Library code never
    calls this on import.
    """
    root = get_logger()
    if force:
        for handler in list(root.handlers):
            root.removeHandler(handler)
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)-7s %(name)s: %(message)s"))
        handler.addFilter(_RedactingFilter())
        root.addHandler(handler)
    root.setLevel(level.upper())
    root.propagate = False
    return root


def level_from_env(default: str = "WARNING") -> str:
    """Read ``ECONENV_LOG_LEVEL`` from the environment."""
    return os.environ.get("ECONENV_LOG_LEVEL", default).upper()
