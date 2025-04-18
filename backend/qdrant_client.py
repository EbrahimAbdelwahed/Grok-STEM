# backend/qdrant_client.py

import logging
from typing import List, Optional, Dict, Any
from qdrant_client import QdrantClient, models
from qdrant_client.http.models import Distance, VectorParams

# Import settings from the config module
from config import settings

logger = logging.getLogger(__name__)

# --- Initialize Qdrant Client ---
try:
    logger.info(f"Initializing Qdrant client for URL: {settings.qdrant_url}")
    # Use API key only if it's provided in the settings
    qdrant_client = QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key if settings.qdrant_api_key else None,
        timeout=60 # Increase timeout slightly for potentially long operations
    )
    # Optional: Verify connection by attempting to list collections
    # qdrant_client.list_collections()
    logger.info("Qdrant client initialized successfully.")

except Exception as e:
    logger.error(f"Failed to initialize Qdrant client: {e}", exc_info=True)
    # Depending on the desired behavior, you might raise the exception
    # or set qdrant_client to None to indicate failure.
    # For now, we'll let the application fail to start if Qdrant isn't available.
    raise e

# --- Optional: Helper function to create collections if they don't exist ---
# This could also live in a separate setup/data_pipeline script.
def ensure_collection_exists(
    client: QdrantClient,
    collection_name: str,
    vector_size: int,
    vector_name: str = "default", # Or specific names like "text_embedding"
    distance: Distance = Distance.COSINE
):
    """Checks if a collection exists and creates it if not."""
    try:
        collection_info = client.get_collection(collection_name=collection_name)
        logger.info(f"Collection '{collection_name}' already exists.")
        # Optional: Add logic here to verify if existing config matches desired config
    except Exception as e:
        # Assuming error means collection doesn't exist (be cautious in production)
        logger.warning(f"Collection '{collection_name}' not found, attempting to create. Error: {e}")
        try:
            client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=vector_size,
                    distance=distance
                    # Add other params like HNSW config if needed
                )
                # Add sparse vectors config, quantization, etc. as needed per collection
            )
            logger.info(f"Successfully created collection '{collection_name}'.")
        except Exception as create_e:
            logger.error(f"Failed to create collection '{collection_name}': {create_e}", exc_info=True)
            raise create_e

# Example of ensuring collections on startup (can be called from main.py later)
# if __name__ == "__main__":
#    # Example dimensions - replace with actual model dimensions later
#    RAG_VECTOR_DIM = 768 # Example dimension for RAG embeddings
#    CACHE_VECTOR_DIM = 768 # Example dimension for cache embeddings (might be different)
#
#    ensure_collection_exists(
#        qdrant_client,
#        settings.qdrant_rag_collection,
#        RAG_VECTOR_DIM,
#        vector_name="content_embedding" # Give it a meaningful name
#    )
#    ensure_collection_exists(
#        qdrant_client,
#        settings.qdrant_cache_collection,
#        CACHE_VECTOR_DIM,
#        vector_name="question_embedding" # Name for cache vector
#    )