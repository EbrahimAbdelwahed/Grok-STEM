"""
Tracing middleware: wraps functions to add correlation-ID context and logging around execution.
Supports both:
  @trace
  @trace("custom_name")
"""
from functools import wraps
import time
import logging
import uuid
from inspect import iscoroutinefunction
from typing import Callable, Any, TypeVar, ParamSpec, Concatenate, Optional, Union

# Import correlation-ID management directly to avoid circular imports
from backend.logging_setup import set_correlation_id, clear_correlation_id

P = ParamSpec('P')
R = TypeVar('R')
logger = logging.getLogger(__name__)


def trace(func_or_name: Union[Callable[..., Any], str, None] = None):
    """
    Decorator to trace function execution with a correlation-ID.
    Usage:
      @trace
      def foo(...): ...

      @trace("custom_name")
      async def bar(...): ...
    """
    # If used as @trace without args
    if callable(func_or_name) and not isinstance(func_or_name, str):
        func = func_or_name  # type: ignore
        return _decorate(func, func.__name__)

    # Otherwise, func_or_name is a custom name or None
    name = func_or_name if isinstance(func_or_name, str) else None

    def decorator(func: Callable[Concatenate[Any, P], R]) -> Callable[Concatenate[Any, P], R]:
        return _decorate(func, name or func.__name__)

    return decorator


def _decorate(func: Callable[Concatenate[Any, P], R], trace_name: str) -> Callable[Concatenate[Any, P], R]:
    """
    Internal helper to produce the wrapped function, sync or async.
    """
    if iscoroutinefunction(func):
        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            request_id = str(uuid.uuid4())
            set_correlation_id(request_id)
            start = time.perf_counter()
            logger.info(f"rid={request_id} | → {trace_name} called")
            try:
                return await func(*args, **kwargs)
            finally:
                elapsed = (time.perf_counter() - start) * 1000
                logger.info(f"rid={request_id} | ← {trace_name} completed in {elapsed:.1f}ms")
                clear_correlation_id()
        return async_wrapper  # type: ignore

    else:
        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            request_id = str(uuid.uuid4())
            set_correlation_id(request_id)
            start = time.perf_counter()
            logger.info(f"rid={request_id} | → {trace_name} called")
            try:
                return func(*args, **kwargs)
            finally:
                elapsed = (time.perf_counter() - start) * 1000
                logger.info(f"rid={request_id} | ← {trace_name} completed in {elapsed:.1f}ms")
                clear_correlation_id()
        return sync_wrapper

