"""
backend package initialisation
==============================

The sole purpose of this file is to ensure **centralised logging is configured
exactly once**—before any other backend module (or a 3rd-party library)
emits a log record.

It also re-exports the correlation-id helpers so downstream code can simply:

    from backend import set_correlation_id, clear_correlation_id
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# Configure logging FIRST — nothing must precede this import / call.
# --------------------------------------------------------------------------- #
from backend.logging_setup import (  # noqa: E402  (import after future-imports)
    configure_logging,
    set_correlation_id,
    clear_correlation_id,
    correlation_id_var,
)

configure_logging()  # honours settings.LOG_JSON & settings.LOG_LEVEL


# --------------------------------------------------------------------------- #
# Convenience re-exports
# --------------------------------------------------------------------------- #
__all__ = [
    "set_correlation_id",
    "clear_correlation_id",
    "correlation_id_var",
]
