# data_pipeline/create_collections.py

import sys
import os
import logging
import asyncio

# Add backend directory to sys.path to allow importing config, clients etc.
# This assumes the script is run from the project root directory
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from backend.config import settings
    # Import the specific functions/client we need
    from backend.qdrant_service import qdrant_client, ensure_collection_exists
    from backend.rag_utils import RAG_VECTOR_DIM, CACHE_VECTOR_DIM # Get dims after model load
    from qdrant_client.models import Distance
except ImportError as e:
    print(f"Error importing backend modules. Make sure you run this script from the project root "
          f"(e.g., `python data_pipeline/create_collections.py` or "
          f"`docker-compose exec backend python data_pipeline/create_collections.py`).")
    print(f"ImportError: {e}")
    sys.exit(1)
except AttributeError as e:
     print(f"Error accessing vector dimensions. Ensure rag_utils.py loads models successfully.")
     print(f"AttributeError: {e}")
     sys.exit(1)

logging.basicConfig(
    level=settings.LOG_LEVEL.upper(),
    format='%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def setup_collections():
    """Asynchronously creates the Qdrant collections if they don't exist."""
    if not qdrant_client:
        logger.error("Qdrant client is not available. Cannot setup collections.")
        return

    if RAG_VECTOR_DIM is None or CACHE_VECTOR_DIM is None:
         logger.error("Vector dimensions not determined (likely embedding model loading failed). Cannot create collections.")
         return

    logger.info("--- Starting Qdrant Collection Setup ---")

    # 1. Setup RAG Knowledge Base Collection
    collection_name_rag = settings.QDRANT_RAG_COLLECTION
    logger.info(f"Ensuring RAG collection '{collection_name_rag}' exists (Vector Dim: {RAG_VECTOR_DIM})...")
    rag_created = await ensure_collection_exists(
        qdrant_client,
        collection_name_rag,
        vector_size=RAG_VECTOR_DIM,
        distance=Distance.COSINE # Cosine is common for text embeddings
    )
    if not rag_created:
         logger.error(f"Failed to ensure RAG collection '{collection_name_rag}' exists.")
         # Decide if we should exit or continue
         # return

    # 2. Setup Semantic Cache Collection
    collection_name_cache = settings.QDRANT_CACHE_COLLECTION
    logger.info(f"Ensuring Semantic Cache collection '{collection_name_cache}' exists (Vector Dim: {CACHE_VECTOR_DIM})...")
    cache_created = await ensure_collection_exists(
        qdrant_client,
        collection_name_cache,
        vector_size=CACHE_VECTOR_DIM,
        distance=Distance.COSINE # Cosine is suitable for semantic similarity
    )
    if not cache_created:
        logger.error(f"Failed to ensure Semantic Cache collection '{collection_name_cache}' exists.")
        # Decide if we should exit or continue

    logger.info("--- Qdrant Collection Setup Finished ---")

if __name__ == "__main__":
    # Run the async setup function
    asyncio.run(setup_collections())