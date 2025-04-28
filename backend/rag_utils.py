import logging
import uuid
from typing import List, Optional, Dict, Any

from qdrant_client import models
from sentence_transformers import SentenceTransformer, util
from httpx import ConnectError # For handling embedding model download errors

# Import the single async Qdrant client instance
from qdrant_service import qdrant_client
from config import settings
from schemas import SemanticCachePayload # Corrected import (payload is dict, model defines structure)
from backend.observability import trace  # Ensure import is available

logger = logging.getLogger(__name__)

# --- Embedding Models ---
RAG_VECTOR_DIM: Optional[int] = None
CACHE_VECTOR_DIM: Optional[int] = None
rag_encoder: Optional[SentenceTransformer] = None
cache_encoder: Optional[SentenceTransformer] = None

try:
    logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL_NAME}")
    # Use the same model for both RAG and cache for simplicity, can be changed
    encoder = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
    rag_encoder = encoder
    cache_encoder = encoder
    RAG_VECTOR_DIM = encoder.get_sentence_embedding_dimension()
    CACHE_VECTOR_DIM = RAG_VECTOR_DIM # Same dimension
    logger.info(f"Embedding model '{settings.EMBEDDING_MODEL_NAME}' loaded (Dim: {RAG_VECTOR_DIM}).")
except ConnectError as ce:
     logger.error(f"Connection error downloading embedding model '{settings.EMBEDDING_MODEL_NAME}'. "
                  f"Check network or Hugging Face Hub status. Error: {ce}", exc_info=True)
     # Set dimensions to None to indicate failure
     RAG_VECTOR_DIM = None
     CACHE_VECTOR_DIM = None
except Exception as e:
    logger.error(f"Failed to load embedding model '{settings.EMBEDDING_MODEL_NAME}': {e}", exc_info=True)
    RAG_VECTOR_DIM = None
    CACHE_VECTOR_DIM = None


# --- RAG Retrieval ---
async def search_rag_kb(query: str) -> List[str]:
    """
    Searches the RAG knowledge base collection in Qdrant.
    """
    if not qdrant_client or not rag_encoder or RAG_VECTOR_DIM is None:
        logger.error("Cannot perform RAG search: Qdrant client, RAG encoder, or vector dim not initialized.")
        return []

    try:
        logger.debug(f"Generating RAG query vector for: '{query[:50]}...'")
        query_vector = rag_encoder.encode(query).tolist()

        logger.debug(f"Searching RAG collection '{settings.QDRANT_RAG_COLLECTION}'...")
        search_result = await qdrant_client.search(
            collection_name=settings.QDRANT_RAG_COLLECTION,
            query_vector=query_vector,
            limit=settings.RAG_NUM_RESULTS,
        )
        # Extract text content from payload
        contexts = [
            hit.payload.get("text_content", "")
            for hit in search_result if hit.payload and hit.payload.get("text_content")
        ]
        logger.info(f"RAG search for '{query[:50]}...' found {len(contexts)} contexts.")
        return contexts
    except Exception as e:
        logger.error(f"Error during RAG search for collection '{settings.QDRANT_RAG_COLLECTION}': {e}", exc_info=True)
        return []

# --- Semantic Cache ---
@trace("semantic_cache_search")  # NEW
async def search_semantic_cache(query: str) -> Optional[List[Dict[str, Any]]]:
    """
    Searches the semantic cache collection in Qdrant.
    Returns the cached response data list if a hit above the threshold is found.
    """
    if not qdrant_client or not cache_encoder or CACHE_VECTOR_DIM is None:
        logger.error("Cannot search cache: Qdrant client, cache encoder, or vector dim not initialized.")
        return None

    try:
        logger.debug(f"Generating cache query vector for: '{query[:50]}...'")
        query_vector = cache_encoder.encode(query).tolist()

        logger.debug(f"Searching cache collection '{settings.QDRANT_CACHE_COLLECTION}' with threshold {settings.CACHE_THRESHOLD}...")
        search_result = await qdrant_client.search(
            collection_name=settings.QDRANT_CACHE_COLLECTION,
            query_vector=query_vector,
            limit=1, # We only need the top hit for caching
            score_threshold=settings.CACHE_THRESHOLD,
        )

        if search_result:
            hit = search_result[0]
            logger.info(f"Semantic cache hit for '{query[:50]}...' (Score: {hit.score:.4f})")
            cached_response_data = hit.payload.get("response_data") if hit.payload else None

            # Validate that the cached data is a list (of message dicts)
            if isinstance(cached_response_data, list):
                logger.debug(f"Returning cached response with {len(cached_response_data)} parts.")
                return cached_response_data
            else:
                logger.warning(f"Cache hit for '{query[:50]}' but response_data is not a list (Type: {type(cached_response_data)}). Discarding cache entry.")
                # Optionally, delete the invalid cache entry here
                # await qdrant_client.delete(collection_name=settings.QDRANT_CACHE_COLLECTION, points_selector=[hit.id])
                return None
        else:
             logger.debug(f"Semantic cache miss for '{query[:50]}...'.")
             return None

    except Exception as e:
        logger.error(f"Error during semantic cache search for collection '{settings.QDRANT_CACHE_COLLECTION}': {e}", exc_info=True)
        return None

async def add_to_semantic_cache(query: str, response_data: List[Dict[str, Any]]):
    """
    Adds a query and its structured response data to the semantic cache.
    """
    if not qdrant_client or not cache_encoder or CACHE_VECTOR_DIM is None:
        logger.error("Cannot add to cache: Qdrant client, cache encoder, or vector dim not initialized.")
        return
    if not isinstance(response_data, list) or not response_data:
         logger.warning(f"Attempted to cache invalid response_data for query '{query[:50]}...'. Aborting cache add.")
         return

    try:
        logger.debug(f"Generating cache vector for query: '{query[:50]}...'")
        query_vector = cache_encoder.encode(query).tolist()
        point_id = str(uuid.uuid4()) # Generate a unique ID for the cache entry

        payload = {
            "question_text": query,
            "response_data": response_data, # Store the list of message dicts
            # Add timestamp or other metadata if useful
            # "cached_at": datetime.utcnow().isoformat()
        }

        logger.info(f"Adding entry to semantic cache collection '{settings.QDRANT_CACHE_COLLECTION}' for query: '{query[:50]}...'")
        await qdrant_client.upsert(
            collection_name=settings.QDRANT_CACHE_COLLECTION,
            points=[
                models.PointStruct(
                    id=point_id,
                    vector=query_vector,
                    payload=payload
                )
            ],
            wait=False # Don't wait for confirmation in the main chat flow
        )
        logger.debug(f"Successfully queued upsert to semantic cache for ID {point_id}.")

    except Exception as e:
        logger.error(f"Error adding to semantic cache for collection '{settings.QDRANT_CACHE_COLLECTION}': {e}", exc_info=True)