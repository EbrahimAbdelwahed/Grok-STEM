# data_pipeline/create_collections.py

import sys
import os
import logging
from backend.qdrant_service import qdrant_client


# Add backend directory to sys.path to allow importing config, clients etc.
# This assumes the script is run from the project root directory (e.g., `python data_pipeline/create_collections.py`)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from backend.config import settings
    from backend.qdrant_service import qdrant_client # Use the initialized client
    # Import necessary Qdrant models directly
    from qdrant_client import models
    from qdrant_client.http.models import Distance, VectorParams
    # We need the vector dimensions. We could import them from rag_utils,
    # but that might load models unnecessarily here. Let's define them
    # explicitly based on the chosen models, or better, add them to config.
    # For now, using dimensions for "all-MiniLM-L6-v2":
    RAG_VECTOR_DIM = 384
    CACHE_VECTOR_DIM = 384 # Same model in this example

except ImportError as e:
    print(f"Error importing backend modules. Make sure you run this script from the project root.")
    print(f"ImportError: {e}")
    sys.exit(1)
except AttributeError as e:
     print(f"Error accessing vector dimensions. Ensure rag_utils.py defines them or add them to config.py")
     print(f"AttributeError: {e}")
     sys.exit(1)


logging.basicConfig(level=settings.log_level.upper(), format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def setup_collections():
    """Creates the Qdrant collections if they don't exist."""
    if not qdrant_client:
        logger.error("Qdrant client is not available. Cannot setup collections.")
        return

    # --- 1. Setup RAG Knowledge Base Collection ---
    collection_name_rag = settings.qdrant_rag_collection
    logger.info(f"Checking/Creating RAG collection: '{collection_name_rag}'...")

    try:
        qdrant_client.get_collection(collection_name=collection_name_rag)
        logger.info(f"Collection '{collection_name_rag}' already exists.")
    except Exception:
        logger.info(f"Collection '{collection_name_rag}' does not exist. Creating...")
        try:
            qdrant_client.create_collection(
                collection_name=collection_name_rag,
                vectors_config=models.VectorParams(
                    size=RAG_VECTOR_DIM,        # Dimension from the RAG encoder
                    distance=models.Distance.COSINE # Cosine similarity is common for text embeddings
                    # on_disk=True # Consider for very large datasets
                ),
                # Add other configurations if needed later (sparse vectors, quantization, etc.)
                # optimizers_config=models.OptimizersConfigDiff(memmap_threshold=20000),
                # hnsw_config=models.HnswConfigDiff(on_disk=True, m=16, ef_construct=100)
            )
            logger.info(f"Successfully created collection '{collection_name_rag}'.")
        except Exception as create_e:
            logger.error(f"Failed to create collection '{collection_name_rag}': {create_e}", exc_info=True)
            return # Stop if creation fails

    # --- 2. Setup Semantic Cache Collection ---
    collection_name_cache = settings.qdrant_cache_collection
    logger.info(f"Checking/Creating Semantic Cache collection: '{collection_name_cache}'...")

    try:
        qdrant_client.get_collection(collection_name=collection_name_cache)
        logger.info(f"Collection '{collection_name_cache}' already exists.")
    except Exception:
        logger.info(f"Collection '{collection_name_cache}' does not exist. Creating...")
        try:
            qdrant_client.create_collection(
                collection_name=collection_name_cache,
                vectors_config=models.VectorParams(
                    size=CACHE_VECTOR_DIM,       # Dimension from the Cache encoder
                    distance=models.Distance.COSINE
                )
            )
            logger.info(f"Successfully created collection '{collection_name_cache}'.")
        except Exception as create_e:
            logger.error(f"Failed to create collection '{collection_name_cache}': {create_e}", exc_info=True)
            return

    logger.info("Collection setup finished.")


if __name__ == "__main__":
    setup_collections()