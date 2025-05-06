import uuid
import json
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from backend.logging_setup import (
    configure_logging,
    set_correlation_id,
    clear_correlation_id,
)
from backend.config import settings
from backend.chat_logic import process_user_message
from backend.qdrant_service import check_qdrant_status
from backend.llm_clients import check_llm_api_status
from backend.observability import tracing_middleware

# Configure logging
configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="GrokSTEM Backend API",
    description="Handles WebSocket connections and processing for the GrokSTEM chatbot.",
    version="0.3.0"
)

# Correlation-ID middleware for HTTP routes
class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        cid = request.headers.get(settings.TRACE_ID_HEADER)
        set_correlation_id(cid)
        try:
            response = await call_next(request)
        finally:
            clear_correlation_id()
        response.headers[settings.TRACE_ID_HEADER] = get_correlation_id()
        return response

app.add_middleware(CorrelationIdMiddleware)
app.middleware("http")(tracing_middleware)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", tags=["General"])
async def read_root():
    return {"message": "GrokSTEM Backend is running"}

@app.get("/health", tags=["Health"])
async def health_check():
    qdrant_status = await check_qdrant_status()
    llm_status = await check_llm_api_status()
    overall = (
        "ok"
        if qdrant_status.get("qdrant_status") == "ok" and all(s == "ok" for s in llm_status.values())
        else "error"
    )
    return {"status": overall, "dependencies": {"qdrant": qdrant_status, "llms": llm_status}}

# Active WebSocket connections: chat_id -> WebSocket
active_connections: dict[str, WebSocket] = {}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Accept connection and assign a unique chat_id
    await websocket.accept()
    chat_id = uuid.uuid4().hex
    active_connections[chat_id] = websocket
    set_correlation_id(chat_id)
    logger.info(f"WebSocket connected (chat_id={chat_id}) from {websocket.client.host}")

    # Send initial chat_id to client
    await websocket.send_json({"type": "init", "chat_id": chat_id})

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
                user_message = payload.get("message", "")
                cid = payload.get("chat_id", chat_id)
            except json.JSONDecodeError:
                user_message = raw
                cid = chat_id

            # Propagate correlation ID per request
            set_correlation_id(cid)
            logger.info(f"[{cid}] Received message: {user_message[:50]}...")

            try:
                # Stream responses back to client
                async for chunk in process_user_message(user_message, cid):
                    chunk["chat_id"] = cid
                    await websocket.send_json(chunk)
            except Exception as exc:
                logger.exception(f"Error streaming response for chat {cid}: {exc}")
                await websocket.send_json({"type": "error", "chat_id": cid, "content": "Internal server error."})
                break
            finally:
                # Clear correlation ID after processing
                clear_correlation_id()

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected (chat_id={chat_id})")
    except Exception as uncaught:
        logger.exception(f"Unexpected error on WebSocket (chat_id={chat_id}): {uncaught}")
    finally:
        # Cleanup
        active_connections.pop(chat_id, None)
        clear_correlation_id()
        logger.info(f"Connection cleaned up (chat_id={chat_id})")
