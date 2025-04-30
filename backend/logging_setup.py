"""
Centralized correlation-ID context and logging configuration.
"""

import logging
from contextvars import ContextVar
from typing import Optional

# Context variable to hold the current correlation ID
correlation_id_var: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)

def set_correlation_id(cid: str) -> None:
    """
    Set the current correlation ID in the context.
    """
    correlation_id_var.set(cid)

def get_correlation_id() -> Optional[str]:
    """
    Retrieve the current correlation ID, or None if unset.
    """
    return correlation_id_var.get()

def clear_correlation_id() -> None:
    """
    Clear the correlation ID from the context.
    """
    correlation_id_var.set(None)

class CorrelationIdFilter(logging.Filter):
    """
    A logging filter that injects the current correlation_id into each LogRecord.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_correlation_id() or ""
        return True

def configure_logging() -> None:
    """
    Set up the root logger:
      - Attach a StreamHandler with a formatter that includes %(correlation_id)s
      - Install the CorrelationIdFilter so every record has the attribute
      - Clear any existing handlers to avoid duplicates
    Call this once at application startup.
    """
    fmt = "%(asctime)s | %(levelname)s | cid=%(correlation_id)s | %(name)s | %(message)s"
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(fmt))
    handler.addFilter(CorrelationIdFilter())

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(handler)
