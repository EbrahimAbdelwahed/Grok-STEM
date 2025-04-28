import logging
import time
import uuid
from typing import Callable, Awaitable

from fastapi import Request, Response
from backend.config import settings
from backend.observability.tracing import set_request_id

logger = logging.getLogger(__name__)

async def tracing_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    rid = request.headers.get(settings.TRACE_ID_HEADER) or str(uuid.uuid4())
    request.state.request_id = rid
    set_request_id(rid)

    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("rid=%s | Unhandled error %s %s", rid, request.method, request.url.path)
        raise
    elapsed = (time.perf_counter() - started) * 1000
    logger.info("rid=%s | %s %s -> %s | %.1f ms",
                rid, request.method, request.url.path, response.status_code, elapsed)
    response.headers[settings.TRACE_ID_HEADER] = rid
    return response