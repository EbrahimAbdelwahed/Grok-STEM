"""Tracing and observability helpers."""

import contextvars
import functools
import time
from typing import Any, Callable, TypeVar

from backend.observability.http_logging import get_async_http_client

F = TypeVar("F", bound=Callable[..., Any])

_request_id = contextvars.ContextVar[str]("request_id")

def set_request_id(request_id: str) -> None:
    """Set the request ID for the current async context."""
    _request_id.set(request_id)

def get_correlation_id() -> str | None:
    """Get the request ID for the current async context."""
    try:
        return _request_id.get()
    except LookupError:
        return None

def trace(tag: str) -> Callable[[F], F]:
    """Decorator to trace a function call with timing and request-ID."""
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            t_start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                elapsed = (time.perf_counter() - t_start) * 1000
                rid = get_correlation_id()
                print(f"TRACE rid={rid} | {tag} | {elapsed:.1f}ms")
        return wrapper
    return decorator

__all__ = [
    "get_correlation_id",
    "set_request_id", 
    "trace",
    "get_async_http_client",
]
