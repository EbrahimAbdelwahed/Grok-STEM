
import uuid
import json
import asyncio
import logging
from typing import Dict, Any
from dotenv import load_dotenv

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from backend.logging_setup import (
    configure_logging,
    set_correlation_id,
    clear_correlation_id,
    get_correlation_id,
)
from backend.config import settings
from backend.chat_logic import process_user_message
from backend.qdrant_service import check_qdrant_status
from backend.llm_clients import check_llm_api_status
from backend.observability import tracing_middleware

# Configure logging
configure_logging()
logger = logging.getLogger(__name__)
load_dotenv()

app = FastAPI(
    title="GrokSTEM Backend API",
    description="Handles WebSocket connections and processing for the GrokSTEM chatbot.",
    version="0.2.1"
)

# Correlation-ID middleware
class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
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

# CORS
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
async def health_check() -> Dict[str, Any]:
    qdrant_status = await check_qdrant_status()
    llm_status = await check_llm_api_status()
    overall = (
        "ok"
        if qdrant_status["qdrant_status"] == "ok" and all(s == "ok" for s in llm_status.values())
        else "error"
    )
    return {"status": overall, "dependencies": {"qdrant": qdrant_status, "llms": llm_status}}

# In-memory map of chat_id → websocket
active_connections: Dict[str, WebSocket] = {}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Each WS connection is treated as a separate chat session with its own chat_id.
    Frontend must send/receive JSON: { chat_id, message } and responses include chat_id.
    """
    await websocket.accept()
    chat_id = uuid.uuid4().hex
    active_connections[chat_id] = websocket
    logger.info(f"WebSocket connected (chat_id={chat_id}) from {websocket.client.host}")
    try:
        # send the assigned chat_id back to client so it can reuse it
        await websocket.send_json({"type": "init", "chat_id": chat_id})

        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
                user_message = payload["message"]
                cid = payload.get("chat_id", chat_id)
            except Exception:
                # fallback: treat entire text as the message
                user_message = raw
                cid = chat_id

            logger.info(f"[{cid}] ← {user_message[:50]}")
            try:
                async for chunk in process_user_message(user_message, cid):
                    # ensure chat_id in every chunk
                    chunk["chat_id"] = cid
                    if cid in active_connections:
                        await active_connections[cid].send_json(chunk)
                # end-of-stream signal
                if cid in active_connections:
                    await active_connections[cid].send_json({"type": "end", "chat_id": cid})
            except Exception as e:
                logger.exception(f"Error handling message for chat {cid}: {e}")
                error = {"type": "error", "chat_id": cid, "content": "Internal server error."}
                await active_connections[cid].send_json(error)
                break

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected cleanly (chat_id={chat_id})")
    finally:
        active_connections.pop(chat_id, None)
        logger.info(f"Connection closed and cleaned up for chat_id={chat_id}")