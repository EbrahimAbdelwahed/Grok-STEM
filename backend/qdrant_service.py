import logging
from qdrant_client import QdrantClient, AsyncQdrantClient, models
from qdrant_client.http.models import Distance, VectorParams, CollectionStatus
from qdrant_client.http import exceptions as qdrant_exceptions
from config import settings
from typing import Optional
from backend.observability.http_logging import get_async_http_client  # NEW

logger = logging.getLogger(__name__)

# --- Initialize Async Qdrant Client ---
qdrant_client: Optional[AsyncQdrantClient] = None
try:
    logger.info(f"Initializing Async Qdrant client for URL: {settings.QDRANT_URL}")
    qdrant_client = AsyncQdrantClient(
         url=settings.QDRANT_URL,
         api_key=settings.QDRANT_API_KEY or None,
         timeout=60,
         http_client=get_async_http_client(timeout=60)  # NEW
    )
    logger.info("Async Qdrant client initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize Async Qdrant client: {e}", exc_info=True)
    qdrant_client = None # Explicitly set to None on failure


# --- Helper Functions ---
async def ensure_collection_exists(
    client: AsyncQdrantClient,
    collection_name: str,
    vector_size: int,
    distance: Distance = Distance.COSINE
):
    """
    Asynchronously checks if a collection exists and creates it if not.
    """
    if not client:
        logger.error(f"Cannot ensure collection '{collection_name}': Qdrant client not initialized.")
        return False
    try:
        await client.get_collection(collection_name=collection_name)
        logger.info(f"Collection '{collection_name}' already exists.")
        return True
    except qdrant_exceptions.UnexpectedResponse as e:
         # Qdrant client raises this specific exception for 404 Not Found
         if e.status_code == 404:
              logger.info(f"Collection '{collection_name}' not found. Creating...")
              try:
                   await client.create_collection(
                       collection_name=collection_name,
                       vectors_config=VectorParams(size=vector_size, distance=distance)
                       # Add other configurations like HNSW, quantization here if needed
                       # Example: hnsw_config=models.HnswConfigDiff(payload_m=16, m=0) # m=0 uses default
                   )
                   logger.info(f"Successfully created collection '{collection_name}' with vector size {vector_size}.")
                   return True
              except Exception as create_e:
                   logger.error(f"Failed to create collection '{collection_name}': {create_e}", exc_info=True)
                   return False
         else:
              # Log other unexpected HTTP errors during check
              logger.error(f"Error checking collection '{collection_name}': {e}", exc_info=True)
              return False
    except Exception as e:
        # Catch other potential errors (network issues, etc.)
        logger.error(f"Unexpected error checking/creating collection '{collection_name}': {e}", exc_info=True)
        return False

@trace("qdrant_status")  # NEW
async def check_qdrant_status() -> dict:
    """
    Performs a basic health check on the Qdrant connection.
    Returns a dictionary with status information.
    """
    if not qdrant_client:
        return {"qdrant_status": "client_not_initialized"}

    try:
        # A lightweight operation like listing collections is a good check
        collections_response = await qdrant_client.get_collections()
        # Log found collections for debugging
        # logger.debug(f"Qdrant health check successful. Found collections: {[c.name for c in collections_response.collections]}")
        return {"qdrant_status": "ok", "collections_count": len(collections_response.collections)}
    except qdrant_exceptions.UnexpectedResponse as ue:
        logger.error(f"Qdrant API error during health check: {ue}", exc_info=False)
        return {"qdrant_status": "api_error", "detail": str(ue)}
    except Exception as e:
        logger.error(f"Qdrant connection error during health check: {e}", exc_info=False)
        return {"qdrant_status": "connection_error", "detail": str(e)}


# --- Cleanup ---
async def close_qdrant_client():
    """Closes the Async Qdrant client connection."""
    if qdrant_client:
        logger.info("Closing Async Qdrant client.")
        await qdrant_client.close()
        logger.info("Async Qdrant client closed.")

# Example usage (usually called from startup/shutdown events in main.py)
# if __name__ == "__main__":
#     import asyncio
#     async def main():
#         status = await check_qdrant_status()
#         print(f"Qdrant Status: {status}")
#         await close_qdrant_client()
#     asyncio.run(main())
