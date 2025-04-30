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
from backend import get_correlation_id as get_request_id

logger = logging.getLogger(__name__)
_TRUNC = 400  # char preview length
TRACE_ID_HEADER = settings.TRACE_ID_HEADER


def _preview(blob: Optional[bytes | str]) -> str:
    """
    Return a (possibly truncated) printable preview of a request/response body.
    """
    if blob is None:
        return ""
    if isinstance(blob, bytes):
        blob = blob.decode(errors="ignore")
    if len(blob) <= _TRUNC:
        return blob
    return blob[:_TRUNC] + f"...[{len(blob) - _TRUNC} truncated]"


def _build_hooks() -> Dict[str, List]:
    """
    Build HTTPX event hooks that will:
    1. Inject the current request‑ID into the outgoing headers.
    2. Capture latency and formatted request/response information for logging.
    """
    async def on_request(request: httpx.Request) -> None:
        rid = get_request_id()
        if rid:
            request.headers[TRACE_ID_HEADER] = rid
        request.extensions["t_start"] = time.perf_counter()

        if settings.HTTP_LOG_BODY:
            logger.debug(
                "rid=%s | → %s %s | %s",
                rid,
                request.method,
                request.url,
                _preview(request.content),
            )
        else:
            logger.debug(
                "rid=%s | → %s %s | %s bytes",
                rid,
                request.method,
                request.url,
                len(request.content or b""),
            )

    async def on_response(response: httpx.Response) -> None:
        rid = get_request_id()
        elapsed = (time.perf_counter() - response.request.extensions["t_start"]) * 1000
        body = (
            _preview(response.text)
            if settings.HTTP_LOG_BODY
            else f"{len(response.content)} bytes"
        )
        logger.info(
            "rid=%s | ← %s %s -> %s | %.1f ms | %s",
            rid,
            response.request.method,
            response.request.url,
            response.status_code,
            elapsed,
            body,
        )

    return {"request": [on_request], "response": [on_response]}


def get_async_http_client(**kwargs: Any) -> httpx.AsyncClient:
    """
    Convenience factory that injects the logging/tracing hooks into an HTTPX AsyncClient.
    Additional kwargs are forwarded verbatim to `httpx.AsyncClient`.
    """
    return httpx.AsyncClient(event_hooks=_build_hooks(), **kwargs)
