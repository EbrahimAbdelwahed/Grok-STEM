# backend/rag_utils.py

import logging
import uuid
from typing import List, Optional, Dict, Any, Tuple

from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer # For embeddings

# Import the initialized Qdrant client and settings
from qdrant_client import qdrant_client
from config import settings
from schemas import SemanticCacheItem # Import schema for type hints

logger = logging.getLogger(__name__)

# --- Embedding Models ---
# Initialize models here. Consider loading them only once.
# Using smaller, efficient models suitable for CPU if not using GPU backend.
# Make model names configurable via settings if needed.
try:
    logger.info("Loading embedding models...")
    # Model for RAG retrieval (adjust model name as needed)
    # Example: Using a smaller multilingual model good for technical text
    rag_embedding_model_name = "sentence-transformers/all-MiniLM-L6-v2"
    rag_encoder = SentenceTransformer(rag_embedding_model_name)
    RAG_VECTOR_DIM = rag_encoder.get_sentence_embedding_dimension()
    logger.info(f"RAG encoder '{rag_embedding_model_name}' loaded (Dim: {RAG_VECTOR_DIM}).")

    # Model for Semantic Cache (can be the same or different)
    # Using a potentially different model optimized for semantic similarity search
    cache_embedding_model_name = "sentence-transformers/all-MiniLM-L6-v2" # Using same for simplicity now
    cache_encoder = SentenceTransformer(cache_embedding_model_name)
    CACHE_VECTOR_DIM = cache_encoder.get_sentence_embedding_dimension()
    logger.info(f"Cache encoder '{cache_embedding_model_name}' loaded (Dim: {CACHE_VECTOR_DIM}).")

except Exception as e:
    logger.error(f"Failed to load embedding models: {e}", exc_info=True)
    rag_encoder = None
    cache_encoder = None
    # Handle failure appropriately - maybe raise or exit


# --- RAG Functions ---

async def search_rag_kb(query: str, k: int = settings.rag_num_results) -> List[str]:
    """Searches the RAG knowledge base for relevant documents."""
    if not qdrant_client or not rag_encoder:
        logger.error("Qdrant client or RAG encoder not initialized.")
        return [] # Return empty list if dependencies aren't ready

    try:
        query_vector = rag_encoder.encode(query).tolist()

        search_result = await qdrant_client.search( # Use async client method if available
            collection_name=settings.qdrant_rag_collection,
            query_vector=query_vector,
            limit=k,
            # Optional: Add filters here if needed (e.g., based on metadata)
            # query_filter=models.Filter(...)
        )

        # Extract text content from payloads
        # Assumes payload has a 'text_content' field based on RAGDocument schema idea
        contexts = [hit.payload.get("text_content", "") for hit in search_result if hit.payload]
        logger.info(f"RAG search for '{query[:50]}...' found {len(contexts)} contexts.")
        return contexts

    except Exception as e:
        logger.error(f"Error during RAG search in Qdrant: {e}", exc_info=True)
        return []

# --- Semantic Cache Functions ---

async def search_semantic_cache(query: str, threshold: float = settings.cache_threshold) -> Optional[List[Dict[str, Any]]]:
    """
    Searches the semantic cache for a similar previous question.
    Returns the cached response data (list of message dicts) if found above threshold.
    """
    if not qdrant_client or not cache_encoder:
        logger.error("Qdrant client or Cache encoder not initialized.")
        return None

    try:
        query_vector = cache_encoder.encode(query).tolist()

        search_result = await qdrant_client.search( # Use async client method if available
            collection_name=settings.qdrant_cache_collection,
            query_vector=query_vector,
            limit=1, # Only need the top hit for cache lookup
            score_threshold=threshold, # Use Qdrant's score thresholding
        )

        if search_result:
            hit = search_result[0]
            logger.info(f"Semantic cache hit for '{query[:50]}...' with score {hit.score:.4f}")
            # Extract the cached response data (list of dicts)
            # Assumes payload matches SemanticCacheItem schema idea
            cached_response = hit.payload.get("response_data") if hit.payload else None
            if isinstance(cached_response, list):
                 return cached_response
            else:
                 logger.warning(f"Cache hit found but response_data format is invalid: {type(cached_response)}")
                 return None # Invalid data format
        else:
            logger.info(f"Semantic cache miss for '{query[:50]}...' (Threshold: {threshold})")
            return None

    except Exception as e:
        logger.error(f"Error during semantic cache search: {e}", exc_info=True)
        return None


async def add_to_semantic_cache(query: str, response_data: List[Dict[str, Any]]):
    """Adds a question and its structured response data to the semantic cache."""
    if not qdrant_client or not cache_encoder:
        logger.error("Cannot add to cache: Qdrant client or Cache encoder not initialized.")
        return

    try:
        query_vector = cache_encoder.encode(query).tolist()
        point_id = str(uuid.uuid4())

        # Prepare payload according to SemanticCacheItem (excluding embedding)
        payload = {
            "question_text": query,
            "response_data": response_data, # Store the list of message dicts
            "metadata": {"timestamp": models.Datetime(isoformat=True)} # Example metadata
        }

        await qdrant_client.upsert( # Use async client method if available
            collection_name=settings.qdrant_cache_collection,
            points=[
                models.PointStruct(
                    id=point_id,
                    vector=query_vector,
                    payload=payload
                )
            ],
            wait=False # Don't wait for confirmation for potentially faster writes
        )
        logger.info(f"Added query '{query[:50]}...' to semantic cache.")

    except Exception as e:
        logger.error(f"Error adding to semantic cache: {e}", exc_info=True)


# --- Simple Test ---
if __name__ == "__main__":
    async def test_rag_cache():
        if not qdrant_client or not rag_encoder or not cache_encoder:
             print("Clients or encoders not initialized. Cannot run tests.")
             return

        print("\n--- Testing RAG Search ---")
        test_query_rag = "Explain Newton's second law"
        try:
            # Ensure the RAG collection exists first (using placeholder dim)
            # from qdrant_client import ensure_collection_exists
            # ensure_collection_exists(qdrant_client, settings.qdrant_rag_collection, 384) # Use actual dim if known

            rag_results = await search_rag_kb(test_query_rag)
            if rag_results:
                print(f"Found {len(rag_results)} RAG results (showing first):")
                print(rag_results[0][:200] + "...")
            else:
                print("No RAG results found (collection might be empty).")
        except Exception as e:
            print(f"RAG search test failed: {e}")


        print("\n--- Testing Semantic Cache ---")
        test_query_cache = "What is the formula for kinetic energy?"
        test_response = [
            {"type": "text", "content": "The formula is KE = 1/2 * m * v^2", "id": "test-id"}
        ]

        try:
            # Ensure cache collection exists (using placeholder dim)
            # from qdrant_client import ensure_collection_exists
            # ensure_collection_exists(qdrant_client, settings.qdrant_cache_collection, 384) # Use actual dim if known

            # 1. Add to cache
            print(f"Adding '{test_query_cache}' to cache...")
            await add_to_semantic_cache(test_query_cache, test_response)
            print("Added.")

            # Allow time for indexing (might not be needed depending on Qdrant config)
            import asyncio
            await asyncio.sleep(1)

            # 2. Search cache
            print(f"Searching cache for '{test_query_cache}'...")
            cached_result = await search_semantic_cache(test_query_cache)
            if cached_result:
                print("Cache Hit! Response data:", cached_result)
            else:
                print("Cache Miss.")

            # 3. Search for something different
            print("\nSearching cache for 'What is potential energy?'...")
            miss_result = await search_semantic_cache("What is potential energy?")
            if not miss_result:
                print("Cache Miss (as expected).")
            else:
                print("Cache Hit (unexpected). Result:", miss_result)

        except Exception as e:
            print(f"Semantic cache test failed: {e}")

    import asyncio
    asyncio.run(test_rag_cache())