"""
Observability package: tracing and HTTP logging helpers.
"""

# HTTP client factory with logging hooks
from backend.observability.http_logging import get_async_http_client

# Reuse correlation-ID context from centralized logging_setup
from backend.logging_setup import (
    set_correlation_id,
    clear_correlation_id,
    get_correlation_id,
)

# Trace decorator for function-level timing
from backend.observability.tracing_middleware import trace

# Alias for clarity in HTTP middleware
set_request_id = set_correlation_id

__all__ = [
    "get_correlation_id",
    "set_request_id",
    "clear_correlation_id",
    "trace",
    "get_async_http_client",
]
