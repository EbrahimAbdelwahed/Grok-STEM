# backend/main.py

import os
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Import the core processing logic
from chat_logic import process_user_message  # Fixed relative import

# --- Configuration & Setup ---
load_dotenv()
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="GrokSTEM Chatbot API",
    description="API for the GrokSTEM interactive learning assistant.",
    version="0.1.0"
)

# --- CORS Middleware ---
# Use settings from config.py
from config import settings  # Fixed relative import
logger.info(f"Configuring CORS for origins: {settings.cors_allowed_origins}")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- WebSocket Connection Manager ---
# Simple in-memory manager (consider Redis/alternatives for scaling)
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket {websocket.client} connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket {websocket.client} disconnected. Total clients: {len(self.active_connections)}")

    # Optional: async def send_personal_message(self, message: str, websocket: WebSocket): ...
    # Optional: async def broadcast(self, message: str): ...

manager = ConnectionManager()

# --- API Routes ---
@app.get("/")
async def read_root():
    logger.debug("Root endpoint '/' accessed.")
    return {"message": "GrokSTEM Backend is running"}

@app.get("/health")
async def health_check():
    # Add checks for DB, LLM connectivity if needed
    logger.debug("Health check endpoint '/health' accessed.")
    return {"status": "ok"}

# --- WebSocket Endpoint ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Handles WebSocket connections and delegates message processing."""
    await manager.connect(websocket)
    try:
        while True:
            # Wait for a message from the client
            user_message = await websocket.receive_text()
            logger.info(f"Received message: '{user_message[:100]}...' from {websocket.client}")

            # --- Call the chat logic processor ---
            # process_user_message is an async generator
            try:
                async for response_chunk in process_user_message(user_message, websocket):
                    await websocket.send_json(response_chunk)
            except Exception as processing_error:
                 # Log error from chat_logic if it wasn't caught internally
                 logger.error(f"Error during message processing for {websocket.client}: {processing_error}", exc_info=True)
                 # Send a generic error message to the client
                 error_payload = {
                     "type": "error",
                     "content": "An internal error occurred while processing your request.",
                     "id": "error-" + uuid.uuid4().hex # Give error its own ID
                 }
                 await websocket.send_json(error_payload)
                 # Send an end message to signal completion, even after error
                 await websocket.send_json({"type": "end", "id": error_payload["id"]})
            # ---------------------------------------

    except WebSocketDisconnect:
        logger.info(f"WebSocket {websocket.client} disconnected cleanly.")
    except Exception as e:
        # Catch potential errors during receive_text or unexpected issues
        logger.error(f"Unexpected WebSocket error for {websocket.client}: {e}", exc_info=True)
    finally:
        # Ensure disconnection cleanup happens
        manager.disconnect(websocket)

# --- Optional: Add startup event to ensure Qdrant collections ---
# from .qdrant_client import ensure_collection_exists, qdrant_client
# from .rag_utils import RAG_VECTOR_DIM, CACHE_VECTOR_DIM # Need to expose these dims

# @app.on_event("startup")
# async def startup_event():
#     logger.info("Running startup tasks...")
#     try:
#         if qdrant_client:
#             logger.info("Ensuring Qdrant collections exist...")
#             # Ensure dimensions are correctly defined/imported in rag_utils.py
#             ensure_collection_exists(qdrant_client, settings.qdrant_rag_collection, RAG_VECTOR_DIM)
#             ensure_collection_exists(qdrant_client, settings.qdrant_cache_collection, CACHE_VECTOR_DIM)
#             logger.info("Qdrant collection check complete.")
#         else:
#              logger.warning("Qdrant client not initialized, skipping collection check.")
#     except Exception as e:
#         logger.error(f"Error during startup collection check: {e}", exc_info=True)
#     logger.info("Startup tasks finished.")

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

# Path to the Vite build output
frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    # Serve all files in /dist at the root URL.
    # Requesting /assets/* etc. will now work.
    app.mount(
        "/",                       # mount at root
        StaticFiles(directory=str(frontend_dist), html=True),
        name="frontend"
    )
    logger.info(f"Serving React build from {frontend_dist}")
else:
    logger.warning("frontend/dist not found – the SPA won't be served by the backend.")

# History‑fallback: for any unknown path that *isn't* an API route or a file,
# return index.html so that React‑Router can handle it on the client.
if frontend_dist.exists():
    index_file = frontend_dist / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        """
        Return React's index.html for any route that hasn't been matched
        by the previous FastAPI endpoints. This allows direct navigation
        or page refresh on /chat and other SPA routes.
        """
        if index_file.exists():
            return FileResponse(index_file)
        # If the file is missing (e.g., in dev mode) still raise 404
        return {"detail": "Not Found"}

# --- Main execution (for local testing without uvicorn command) ---
if __name__ == "__main__":
    import uvicorn
    # Use log level from settings for direct run too
    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["loggers"]["uvicorn"]["level"] = settings.log_level.upper()
    log_config["loggers"]["uvicorn.access"]["level"] = settings.log_level.upper()

    logger.info(f"Starting Uvicorn server directly on port 8000 with log level {settings.log_level}...")
    uvicorn.run(
        "main:app", # Important: Use string reference for reload to work
        host="0.0.0.0",
        port=8000,
        log_config=log_config,
        reload=True # Enable reload for local dev when run directly
    )
