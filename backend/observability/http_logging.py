"""
HTTP logging helpers.

This module wraps httpx.AsyncClient to inject request/response logging and
trace-ID propagation.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import httpx

from backend.config import settings
# Now import directly from logging_setup to avoid circular imports
from backend.logging_setup import get_correlation_id as get_request_id

logger = logging.getLogger(__name__)
_TRUNC = 400  # char preview length
TRACE_ID_HEADER = settings.TRACE_ID_HEADER


def _preview(blob: Optional[bytes | str]) -> str:
    """
    Return a (possibly truncated) printable preview of a request/response body.
    """
    if blob is None:
        return "[No Body]" # Indicate explicitly if None
    if isinstance(blob, bytes):
        try:
            # Attempt to decode as UTF-8, ignore errors for non-text data
            blob = blob.decode('utf-8', errors="ignore")
        except Exception:
             # Fallback if decoding itself fails unexpectedly
             return f"[Could not decode {len(blob)} bytes]"
    # Ensure it's treated as a string from here
    blob_str = str(blob)
    if not blob_str:
         return "[Empty Body]" # Indicate explicitly if empty string
    if len(blob_str) <= _TRUNC:
        return blob_str
    # Use f-string for cleaner formatting
    return f"{blob_str[:_TRUNC]}...[{len(blob_str) - _TRUNC} truncated]"


def _build_hooks() -> Dict[str, List]:
    """
    Build HTTPX event hooks that will:
    1. Inject the current request-ID into the outgoing headers.
    2. Capture latency and formatted request/response information for logging.
    """
    async def on_request(request: httpx.Request) -> None:
        rid = get_request_id()
        if rid:
            request.headers[TRACE_ID_HEADER] = rid
        request.extensions["t_start"] = time.perf_counter()

        # Log request details
        request_body_preview: str
        if settings.HTTP_LOG_BODY:
            try:
                # Ensure request body is read if needed for logging
                # Read content only if it hasn't been read yet (e.g., by previous middleware)
                # Note: This might still be racy depending on other hooks, but safer than unconditional read.
                # Consider if request body logging is strictly necessary if issues persist.
                if not request.is_read:
                     await request.aread()
                request_body_preview = _preview(request.content)
            except Exception as read_err:
                 logger.warning(f"rid={rid} | Could not read request body for logging: {read_err}")
                 request_body_preview = "[Request body read error]"
        else:
            content_length = request.headers.get('content-length')
            request_body_preview = f"{content_length} bytes" if content_length else "[No Content-Length header]"

        logger.debug(
            "rid=%s | → %s %s | %s",
            rid,
            request.method,
            request.url,
            request_body_preview,
        )


    async def on_response(response: httpx.Response) -> None:
        # --- **CORRECTED SECTION** ---
        read_error_occurred = False
        try:
            # Ensure the body is read so .content/.text can be accessed later by the SDK
            # We still need this call here to make sure the SDK doesn't hit ResponseNotRead later.
            await response.aread()
        except httpx.ResponseNotRead as e:
             # This specific error shouldn't happen if aread() is called correctly,
             # but catch defensively.
             logger.error(f"Unexpected ResponseNotRead during aread() in hook: {e}")
             read_error_occurred = True
        except httpx.ResponseClosed as e:
             logger.warning(f"Response closed prematurely during aread() in hook: {e}")
             read_error_occurred = True
        except Exception as read_err:
            # Log other errors during reading
            logger.warning(f"Failed to read response body in logging hook: {read_err}")
            read_error_occurred = True

        # Calculate elapsed time
        rid = get_request_id()
        # Guard against potential KeyError if t_start wasn't set (shouldn't happen usually)
        start_time = response.request.extensions.get("t_start", time.perf_counter())
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # Prepare body preview based on settings and whether reading failed
        body_preview: str
        if read_error_occurred:
             body_preview = "[Response body read error]"
        elif settings.HTTP_LOG_BODY:
            # Safe to access .text now because aread() succeeded (or we logged the error)
            body_preview = _preview(response.text)
        else:
            # Safe to access .content now
            body_preview = f"{len(response.content)} bytes"

        # Log the response info
        logger.info(
            "rid=%s | ← %s %s -> %s | %.1f ms | %s",
            rid,
            response.request.method,
            response.request.url,
            response.status_code,
            elapsed_ms,
            body_preview, # Use the prepared preview
        )
        # --- **END CORRECTED SECTION** ---

    return {"request": [on_request], "response": [on_response]}


def get_async_http_client(**kwargs: Any) -> httpx.AsyncClient:
    """
    Convenience factory that injects the logging/tracing hooks into an HTTPX AsyncClient.
    Additional kwargs are forwarded verbatim to `httpx.AsyncClient`.
    """
    # Ensure default timeout if not provided
    if 'timeout' not in kwargs:
        kwargs['timeout'] = 60.0 # Default timeout

    return httpx.AsyncClient(event_hooks=_build_hooks(), **kwargs)