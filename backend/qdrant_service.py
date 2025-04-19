# backend/qdrant_service.py

import logging
from qdrant_client import QdrantClient as QdrantClientLib, models
from qdrant_client.models import Distance, VectorParams
from config import settings

logger = logging.getLogger(__name__)

# Initialize the real Qdrant client
try:
    logger.info(f"Initializing Qdrant client for URL: {settings.qdrant_url}")
    qdrant_client = QdrantClientLib(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
        timeout=60
    )
    logger.info("Qdrant client initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize Qdrant client: {e}", exc_info=True)
    raise

def ensure_collection_exists(client, collection_name: str, vector_size: int, distance: Distance = Distance.COSINE):
    """
    Helper to create a collection if it doesn't exist.
    """
    try:
        client.get_collection(collection_name=collection_name)
        logger.info(f"Collection '{collection_name}' already exists.")
    except Exception:
        logger.info(f"Creating collection '{collection_name}'...")
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=distance)
        )
        logger.info(f"Collection '{collection_name}' created.")
