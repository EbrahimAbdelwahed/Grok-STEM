# backend/main.py
import uuid
import json
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from backend.logging_setup import (
    configure_logging,
    set_correlation_id,
    clear_correlation_id,
    get_correlation_id, # Import getter
)
from backend.config import settings
# Import new helper functions
from backend.chat_logic import process_user_message, handle_image_generation
from backend.llm_clients import generate_image_prompt_from_query, check_llm_api_status, close_clients # Import prompt gen
from backend.qdrant_service import check_qdrant_status, close_qdrant_client # Import qdrant close
# Import schemas for validation if needed, or handle dicts directly
# from backend.schemas import GenerateImageRequest

# Configure logging
configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="GrokSTEM Backend API",
    description="Handles WebSocket connections and processing for the GrokSTEM chatbot.",
    version="0.4.0" # Bump version
)

# --- Middleware ---
class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Get ID from header or generate a new one for the request lifespan
        cid = request.headers.get(settings.TRACE_ID_HEADER) or str(uuid.uuid4())
        set_correlation_id(cid)
        # Ensure the ID is set on the response header
        response = await call_next(request)
        response.headers[settings.TRACE_ID_HEADER] = get_correlation_id() # Use getter
        clear_correlation_id() # Clear after request finishes
        return response

app.add_middleware(CorrelationIdMiddleware)
# app.middleware("http")(tracing_middleware) # Ensure tracing middleware is added if needed

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- WebSocket Connection Management ---
active_connections: dict[str, WebSocket] = {}

# --- Application Lifespan (Startup/Shutdown) ---
@app.on_event("startup")
async def startup_event():
    logger.info("GrokSTEM Backend starting up...")
    # Perform initial health checks maybe?
    q_status = await check_qdrant_status()
    l_status = await check_llm_api_status()
    logger.info(f"Initial Qdrant Status: {q_status}")
    logger.info(f"Initial LLM Status: {l_status}")
    logger.info("GrokSTEM Backend started.")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("GrokSTEM Backend shutting down...")
    await close_qdrant_client()
    await close_clients()
    logger.info("GrokSTEM Backend shut down complete.")


# --- HTTP Routes ---
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


# --- WebSocket Endpoint ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    chat_id = str(uuid.uuid4())
    active_connections[chat_id] = websocket
    # Use chat_id as correlation ID for WS context
    set_correlation_id(chat_id)
    logger.info(f"WebSocket connected (chat_id={chat_id}) from {websocket.client.host}")

    try:
        # Send initial chat_id to client
        await websocket.send_json({"type": "init", "chat_id": chat_id})

        while True:
            raw_data = await websocket.receive_text()
            try:
                payload = json.loads(raw_data)
                message_type = payload.get("type", "chat") # Default to chat message
                cid = payload.get("chat_id", chat_id) # Use chat_id from payload or connection

                # Propagate correlation ID per request/message
                set_correlation_id(cid)

                if message_type == "chat":
                    user_message = payload.get("message", "")
                    logger.info(f"[{cid}] Received chat message: {user_message[:50]}...")
                    # Stream responses back using process_user_message
                    async for chunk in process_user_message(user_message, cid):
                        await websocket.send_json(chunk)

                elif message_type == "generate_image": # Handle user image request
                    original_query = payload.get("original_user_query")
                    assistant_message_id = payload.get("assistant_message_id") # ID of the message needing image
                    logger.info(f"[{cid}] Received image generation request for message {assistant_message_id} based on query: '{original_query[:50]}...'")

                    if not original_query or not assistant_message_id:
                         logger.warning(f"[{cid}] Invalid image generation request payload: {payload}")
                         await websocket.send_json({"type": "error", "id": assistant_message_id, "chat_id": cid, "content": "Invalid request for image generation."})
                         continue

                    # 1. Generate image prompt using small LLM
                    image_prompt = await generate_image_prompt_from_query(original_query)
                    if not image_prompt:
                         logger.error(f"[{cid}] Failed to generate image prompt for query: '{original_query[:50]}...'")
                         await websocket.send_json({"type": "image_error", "id": assistant_message_id, "chat_id": cid, "content": "Failed to create a prompt for image generation."})
                         continue

                    # 2. Handle generation (cache check, API call, retries) and stream results
                    # Make sure handle_image_generation yields chunks with the *assistant_message_id*
                    async for image_chunk in handle_image_generation(image_prompt, assistant_message_id, cid):
                        await websocket.send_json(image_chunk) # Forward image chunks to client

                else:
                    logger.warning(f"[{cid}] Received unknown WebSocket message type: {message_type}")
                    # Optionally send an error back to the client

            except json.JSONDecodeError:
                logger.warning(f"[{cid}] Received invalid JSON via WebSocket: {raw_data[:100]}")
                await websocket.send_json({"type": "error", "chat_id": cid, "id": "unknown", "content": "Invalid message format."})
            except WebSocketDisconnect:
                # Handled in the outer except block
                raise
            except Exception as e:
                # Catch errors during message processing
                logger.exception(f"[{cid}] Error processing WebSocket message: {e}")
                error_id = payload.get("id", "unknown") if isinstance(payload, dict) else "unknown"
                await websocket.send_json({"type": "error", "id": error_id, "chat_id": cid, "content": "Internal server error processing message."})
            finally:
                clear_correlation_id() # Clear after processing each message

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected (chat_id={chat_id})")
    except Exception as e:
        # Catch unexpected errors in the main loop/connection handling
        logger.exception(f"[{chat_id}] Unexpected error on WebSocket connection: {e}")
    finally:
        # Cleanup connection
        active_connections.pop(chat_id, None)
        # Clear correlation ID if exception happened before finally block in loop
        clear_correlation_id()
        logger.info(f"Connection closed and cleaned up (chat_id={chat_id})")