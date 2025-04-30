"""
Centralised logging configuration.

Import configure_logging() as early as possible (backend/__init__.py) so every
module sees the same handlers, filters and formatters.

Usage:
    from backend.logging_setup import set_correlation_id, clear_correlation_id
"""

from __future__ import annotations

import contextvars
import json
import logging
import logging.config
import os
import re
import sys
import uuid
from types import FrameType
from typing import Any, Dict, Mapping, MutableMapping, Optional

# --------------------------------------------------------------------------- #
# Settings are loaded lazily so we don't fail during unit tests that import
# this module before the app's settings are available.
# --------------------------------------------------------------------------- #
try:
    from backend.config import settings  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    settings = None  # type: ignore


# --------------------------------------------------------------------------- #
# Correlation‑ID plumbing
# --------------------------------------------------------------------------- #
correlation_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "correlation_id",
    default=None,
)


def set_correlation_id(cid: Optional[str] = None) -> str:
    """Set correlation ID for current context. Generates one if not provided."""
    cid = cid or str(uuid.uuid4())
    correlation_id_var.set(cid)
    return cid


def clear_correlation_id() -> None:
    """Clear correlation ID from current context."""
    correlation_id_var.set(None)


def get_correlation_id() -> Optional[str]:
    """Get current correlation ID."""
    return correlation_id_var.get()


class CorrelationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        cid = get_correlation_id()
        record.correlation_id = cid if cid else "nocid"
        return True


# --------------------------------------------------------------------------- #
# Sensitive‑data redaction
# Feel free to extend the REGEXES list with additional patterns.
# --------------------------------------------------------------------------- #
REGEXES = [
    re.compile(r"sk-[A-Za-z0-9]{32,}"),  # OpenAI‑style keys
    re.compile(r"pk_live_[A-Za-z0-9]{24,}"),  # Stripe keys
    re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"),  # e‑mails
]


class RedactionFormatter(logging.Formatter):
    """
    Formatter that applies regex redaction *after* the underlying formatter
    produced the final string / dict.
    """

    def __init__(self, wrapped: logging.Formatter):
        super().__init__()
        self._wrapped = wrapped

    def format(self, record: logging.LogRecord) -> str:
        msg = self._wrapped.format(record)
        for rx in REGEXES:
            msg = rx.sub("[REDACTED]", msg)
        return msg


# --------------------------------------------------------------------------- #
# JSON vs. plain‑text formatter helpers
# --------------------------------------------------------------------------- #
try:
    from pythonjsonlogger import jsonlogger
except ImportError:  # pragma: no cover
    jsonlogger = None  # type: ignore


def _json_formatter() -> logging.Formatter:
    if not jsonlogger:  # fall back to plain text
        return logging.Formatter(
            '{"time":"%(asctime)s", "level":"%(levelname)s", "correlation_id":"%(correlation_id)s", "message":"%(message)s"}'
        )

    fmt = (
        '{"time":"%(asctime)s", "level":"%(levelname)s", "correlation_id":"%(correlation_id)s", "message":"%(message)s"}'
    )
    return jsonlogger.JsonFormatter(fmt)


def _plain_formatter() -> logging.Formatter:
    return logging.Formatter(
        "%(asctime)s %(levelname)s [%(correlation_id)s] %(message)s"
    )


# --------------------------------------------------------------------------- #
# Structured Formatter
# --------------------------------------------------------------------------- #
class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # Extract any extra fields
        extra_fields = {
            k: v for k, v in record.__dict__.items() 
            if not k.startswith('_') and k not in {
                'name', 'msg', 'args', 'levelno', 'created', 'msecs', 'relativeCreated', 
                'exc_info', 'exc_text', 'filename', 'funcName', 'levelname', 'lineno', 
                'module', 'pathname', 'process', 'processName', 'thread', 'threadName',
                'correlation_id'
            }
        }
        
        if settings.LOG_JSON:
            log_data = {
                'time': self.formatTime(record),
                'level': record.levelname,
                'correlation_id': getattr(record, 'correlation_id', 'nocid'),
                'message': record.getMessage(),
                **extra_fields
            }
            if record.exc_info:
                log_data['exc_info'] = self.formatException(record.exc_info)
            return json.dumps(log_data)
        else:
            # For plain text, include extra fields at the end if present
            base_msg = super().format(record)
            if extra_fields:
                extras = ' '.join(f"{k}={v!r}" for k, v in extra_fields.items())
                return f"{base_msg} | {extras}"
            return base_msg


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def configure_logging(log_json: bool | None = None, level: str | None = None) -> None:
    """
    Configure root logging once for the entire process.
    Compatible with FastAPI/Starlette/Uvicorn logging.
    """
    # Resolve parameters with sensible fallbacks, but don't access settings yet
    log_json = (
        log_json if log_json is not None 
        else os.getenv("LOG_JSON", "0") == "1"
    )
    level = (
        level if level is not None
        else os.getenv("LOG_LEVEL", "INFO")
    ).upper()

    # Build formatter / handlers
    formatter: logging.Formatter = StructuredFormatter(
        '%(asctime)s %(levelname)s [%(correlation_id)s] %(message)s' 
        if not log_json else None
    )

    # Configure root logger but preserve existing handlers from Starlette/Uvicorn
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addFilter(CorrelationIdFilter())

    # Add our handler only if no handlers exist yet
    if not root_logger.handlers:
        console_handler: logging.Handler = logging.StreamHandler(stream=sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    else:
        # Otherwise update existing handlers with our formatter
        for handler in root_logger.handlers:
            handler.setFormatter(formatter)

    # Update uvicorn access logger to include correlation IDs
    uvicorn_logger = logging.getLogger("uvicorn.access")
    uvicorn_logger.addFilter(CorrelationIdFilter())

    logging.getLogger(__name__).debug(
        "Logging configured",
        extra={"log_json": log_json, "level": level}
    )