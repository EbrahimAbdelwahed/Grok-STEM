import asyncio
import contextvars
import functools
import logging
import time
from typing import Any, Callable, TypeVar

from backend.config import settings

logger = logging.getLogger(__name__)
_request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)

def set_request_id(rid: str) -> None:
    _request_id_var.set(rid)

def get_request_id() -> str | None:
    return _request_id_var.get()

F = TypeVar("F", bound=Callable[..., Any])

def trace(stage: str) -> Callable[[F], F]:
    """
    Decorator that logs entry/exit/exception for the wrapped function
    IFF VERBOSE_TRACE is enabled. Otherwise returns original func.
    """
    def decorator(func: F) -> F:  # type: ignore[misc]
        if not settings.VERBOSE_TRACE:
            return func

        log = logger.getChild(stage)

        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrap(*args, **kwargs):  # type: ignore[override]
                rid = get_request_id()
                start = time.perf_counter()
                log.debug("rid=%s | ⇢ %s(...)", rid, stage)
                try:
                    return await func(*args, **kwargs)
                except Exception:
                    log.exception("rid=%s | ✗ %s failed", rid, stage)
                    raise
                finally:
                    log.debug("rid=%s | ⇠ %s %.1f ms", rid, stage, (time.perf_counter() - start) * 1000)
            return async_wrap  # type: ignore[return-value]

        @functools.wraps(func)
        def sync_wrap(*args, **kwargs):  # type: ignore[override]
            rid = get_request_id()
            start = time.perf_counter()
            log.debug("rid=%s | ⇢ %s(...)", rid, stage)
            try:
                return func(*args, **kwargs)
            except Exception:
                log.exception("rid=%s | ✗ %s failed", rid, stage)
                raise
            finally:
                log.debug("rid=%s | ⇠ %s %.1f ms", rid, stage, (time.perf_counter() - start) * 1000)
        return sync_wrap  # type: ignore[return-value]
    return decorator