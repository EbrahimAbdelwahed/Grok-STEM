import os
import logging
import uuid
import asyncio
from typing import List, Dict, Any
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from dotenv import load_dotenv

# Import backend components
from backend.config import settings
from backend.chat_logic import process_user_message
from backend.qdrant_service import check_qdrant_status, close_qdrant_client, qdrant_client
from backend.llm_clients import check_llm_api_status, close_openai_client, close_grok_client
from backend.schemas import ChatMessage, ChatResponse
from backend.observability import trace
from backend import set_correlation_id, clear_correlation_id, correlation_id_var
from backend.observability.tracing_middleware import tracing_middleware

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Log loaded settings
logger.info("--- GrokSTEM Backend Settings ---")
logger.info(f"  Log Level: {settings.LOG_LEVEL}")
logger.info(f"  Reasoning Model: {settings.REASONING_MODEL_NAME}")
logger.info(f"  Plotting Model: {settings.PLOTTING_MODEL_NAME}")
logger.info(f"  Embedding Model: {settings.EMBEDDING_MODEL_NAME}")
logger.info(f"  Qdrant URL: {settings.QDRANT_URL}")
logger.info(f"  RAG Collection: {settings.QDRANT_RAG_COLLECTION}")
logger.info(f"  Cache Collection: {settings.QDRANT_CACHE_COLLECTION}")
logger.info(f"  Cache Threshold: {settings.CACHE_THRESHOLD}")
logger.info(f"  RAG Num Results: {settings.RAG_NUM_RESULTS}")
logger.info(f"  CORS Origins: {settings.cors_allowed_origins_list}")
logger.info("---------------------------------")


# --- FastAPI App Initialization ---
app = FastAPI(
    title="GrokSTEM Backend API",
    description="Handles WebSocket connections and processing for the GrokSTEM chatbot.",
    version="0.2.0"
)

# --- Middleware for Request Tracing ---
app.middleware("http")(tracing_middleware)

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins_list, # Use the parsed list
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Correlation ID Middleware ---
class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        cid = request.headers.get(settings.TRACE_ID_HEADER)
        set_correlation_id(cid)
        try:
            response = await call_next(request)
        finally:
            clear_correlation_id()
        response.headers[settings.TRACE_ID_HEADER] = correlation_id_var.get()
        return response

app.add_middleware(CorrelationIdMiddleware)

# --- WebSocket Connection Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {} # Store by a unique client ID

    async def connect(self, websocket: WebSocket) -> str:
        await websocket.accept()
        client_id = uuid.uuid4().hex # Assign a unique ID to each connection
        cid = set_correlation_id(client_id)
        self.active_connections[client_id] = websocket
        logger.info(f"WebSocket connected: {websocket.client.host}:{websocket.client.port}. Total: {len(self.active_connections)}")
        return client_id

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            set_correlation_id(client_id)
            try:
                websocket = self.active_connections.pop(client_id)
                logger.info(f"WebSocket disconnected: {websocket.client.host}:{websocket.client.port}. Total: {len(self.active_connections)}")
            finally:
                clear_correlation_id()

    async def send_personal_json(self, message: dict, client_id: str):
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            try:
                await websocket.send_json(message)
            except Exception as e:
                 logger.error(f"Failed to send JSON to client {client_id}: {e}")
                 # Optionally disconnect on persistent send errors
                 # self.disconnect(client_id)
        else:
            logger.warning(f"Attempted to send message to non-existent client ID: {client_id}")

manager = ConnectionManager()

# --- API Routes ---
@app.get("/", tags=["General"])
async def read_root():
    logger.debug("Root endpoint '/' accessed.")
    return {"message": "GrokSTEM Backend is running"}

@trace("health_check")  # NEW
@app.get("/health", tags=["Health"], response_model=Dict[str, Any])
async def health_check():
    """Checks the status of the backend and its dependencies."""
    logger.debug("Health check endpoint '/health' accessed.")
    qdrant_status = await check_qdrant_status()
    llm_status = await check_llm_api_status()
    overall_status = "ok"
    if qdrant_status.get("qdrant_status") != "ok" or any(status != "ok" for status in llm_status.values()):
        overall_status = "error"
    return {
        "status": overall_status,
        "dependencies": {"qdrant": qdrant_status, "llms": llm_status}
    }

@trace("websocket_endpoint")  # NEW
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Handles WebSocket connections and delegates message processing."""
    client_id = await manager.connect(websocket)
    try:
        while True:
            user_message = await websocket.receive_text()
            logger.info(f"Received message from client {client_id}: '{user_message[:100]}...'")
            try:
                async for response_chunk in process_user_message(user_message, websocket):
                    await manager.send_personal_json(response_chunk, client_id)
            except Exception as processing_error:
                logger.error(f"Error during message processing for client {client_id}: {processing_error}", exc_info=True)
                error_payload = schemas.ErrorMessage(
                    id="error-" + uuid.uuid4().hex,
                    content="An internal error occurred while processing your request. Please check logs or try again later."
                ).model_dump()
                await manager.send_personal_json(error_payload, client_id)
                end_payload = schemas.EndMessage(id=error_payload["id"]).model_dump()
                await manager.send_personal_json(end_payload, client_id)
    except WebSocketDisconnect:
        logger.info(f"WebSocket client {client_id} disconnected cleanly.")
    except Exception as e:
        logger.error(f"Unexpected WebSocket error for client {client_id}: {e}", exc_info=True)
    finally:
        manager.disconnect(client_id)

# --- Event Handlers for Startup/Shutdown ---
@app.on_event("startup")
async def startup_event():
    logger.info("Application startup...")
    # Perform initial dependency checks
    q_status = await check_qdrant_status()
    l_status = await check_llm_api_status()
    logger.info(f"Initial Qdrant status: {q_status}")
    logger.info(f"Initial LLM status: {l_status}")
    if q_status.get("qdrant_status") != "ok":
         logger.warning("Qdrant connection check failed on startup.")
    if any(s != "ok" for s in l_status.values()):
         logger.warning("One or more LLM API connection checks failed on startup.")
    # No need to create collections here, handled by data_pipeline scripts
    logger.info("Startup complete.")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutdown...")
    # Gracefully close client connections
    await close_qdrant_client()
    # Use the functions added to llm_clients.py:
    await close_openai_client()
    await close_grok_client()
    logger.info("Shutdown complete.")


# --- Static Files Hosting (for Production) ---
# Serve the React frontend build if it exists
frontend_dist_str = str(Path(__file__).resolve().parent.parent / "frontend" / "dist")
frontend_dist_path = Path(frontend_dist_str)
static_files_app = None

if frontend_dist_path.exists() and (frontend_dist_path / "index.html").exists():
     logger.info(f"Serving static files from: {frontend_dist_str}")
     static_files_app = StaticFiles(directory=frontend_dist_str, html=True)
     app.mount("/assets", StaticFiles(directory=str(frontend_dist_path / "assets")), name="assets") # Explicitly mount assets
     # Mount at root AFTER API routes are defined
     app.mount("/", static_files_app, name="frontend")
else:
     logger.warning(f"Frontend build directory '{frontend_dist_str}' not found or missing index.html. SPA frontend will not be served by the backend.")

# --- SPA Fallback Route ---
# This should come AFTER all other API routes and static mounts
# It ensures that any path not matched by API or static files serves index.html
if static_files_app: # Only add fallback if static files are being served
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        """Serve index.html for SPA routing."""
        index_path = frontend_dist_path / "index.html"
        if index_path.exists():
            logger.debug(f"SPA fallback triggered for path: /{full_path}. Serving index.html.")
            return FileResponse(index_path)
        else:
            # This case should not happen if the initial check passed, but good practice
            logger.error("SPA fallback: index.html not found!")
            raise HTTPException(status_code=404, detail="SPA index.html not found")


# --- Main execution (for local testing without uvicorn command) ---
if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting Uvicorn server directly on port 8000 with log level {settings.LOG_LEVEL}...")
    # Note: Uvicorn logging config might need adjustment for optimal format with basicConfig
    uvicorn.run(
        "main:app", # Use string for reload to work properly
        host="0.0.0.0",
        port=8000,
        log_level=settings.LOG_LEVEL.lower(), # Use lowercase for uvicorn log_level
        reload=True, # Enable reload for local development
        reload_dirs=[str(Path(__file__).parent)] # Specify directory to watch for reload
    )