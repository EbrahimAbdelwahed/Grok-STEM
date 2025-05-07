# backend/rag_utils.py
import logging
import uuid
import hashlib
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from qdrant_client import models
from sentence_transformers import SentenceTransformer, util
from httpx import ConnectError

# Import the single async Qdrant client instance
from backend.qdrant_service import qdrant_client
from backend.config import settings
# Corrected import: Pydantic models define structure, payload is dict
from backend.schemas import ImageCachePayload # Import the new schema
from backend.observability import trace

logger = logging.getLogger(__name__)

# --- Embedding Models ---
RAG_VECTOR_DIM: Optional[int] = None
CACHE_VECTOR_DIM: Optional[int] = None
rag_encoder: Optional[SentenceTransformer] = None
cache_encoder: Optional[SentenceTransformer] = None

try:
    logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL_NAME}")
    # Use the same model for RAG, semantic cache, and image prompt cache
    encoder = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
    rag_encoder = encoder
    cache_encoder = encoder # Use the same encoder for all caches
    RAG_VECTOR_DIM = encoder.get_sentence_embedding_dimension()
    CACHE_VECTOR_DIM = RAG_VECTOR_DIM # Dimensions will be the same
    logger.info(f"Embedding model '{settings.EMBEDDING_MODEL_NAME}' loaded (Dim: {RAG_VECTOR_DIM}).")
except ConnectError as ce:
     logger.error(f"Connection error downloading embedding model '{settings.EMBEDDING_MODEL_NAME}'. Error: {ce}", exc_info=True)
     RAG_VECTOR_DIM, CACHE_VECTOR_DIM = None, None
except Exception as e:
    logger.error(f"Failed to load embedding model '{settings.EMBEDDING_MODEL_NAME}': {e}", exc_info=True)
    RAG_VECTOR_DIM, CACHE_VECTOR_DIM = None, None


# --- RAG Retrieval ---
@trace("rag_kb_search")
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
        collection_name = settings.QDRANT_RAG_COLLECTION

        logger.debug(f"Searching RAG collection '{collection_name}'...")
        search_result = await qdrant_client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=settings.RAG_NUM_RESULTS,
            # Optional: Add score threshold if needed
            # score_threshold=0.7, # Example threshold
        )

        contexts = [
            hit.payload.get("text_content", "")
            for hit in search_result if hit.payload and hit.payload.get("text_content")
        ]
        logger.info(f"RAG search for '{query[:50]}...' found {len(contexts)} contexts.")
        return contexts
    except Exception as e:
        logger.error(f"Error during RAG search for collection '{collection_name}': {e}", exc_info=True)
        return []

# --- Semantic (LLM Response) Cache ---
@trace("semantic_cache_search")
async def search_semantic_cache(query: str) -> Optional[List[Dict[str, Any]]]:
    """
    Searches the semantic cache collection in Qdrant.
    Returns the cached response data list if a hit above the threshold is found.
    """
    if not qdrant_client or not cache_encoder or CACHE_VECTOR_DIM is None:
        logger.error("Cannot search semantic cache: Dependencies not initialized.")
        return None

    try:
        logger.debug(f"Generating semantic cache query vector for: '{query[:50]}...'")
        query_vector = cache_encoder.encode(query).tolist()
        collection_name = settings.QDRANT_CACHE_COLLECTION
        threshold = settings.CACHE_THRESHOLD

        logger.debug(f"Searching semantic cache '{collection_name}' with threshold {threshold}...")
        search_result = await qdrant_client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=1,
            score_threshold=threshold,
        )

        if search_result:
            hit = search_result[0]
            logger.info(f"Semantic cache hit for '{query[:50]}...' (Score: {hit.score:.4f})")
            cached_response_data = hit.payload.get("response_data") if hit.payload else None

            if isinstance(cached_response_data, list):
                logger.debug(f"Returning cached response with {len(cached_response_data)} parts.")
                return cached_response_data
            else:
                logger.warning(f"Semantic cache hit for '{query[:50]}' but response_data is not a list. Discarding.")
                return None
        else:
             logger.debug(f"Semantic cache miss for '{query[:50]}...'.")
             return None

    except Exception as e:
        logger.error(f"Error during semantic cache search for collection '{collection_name}': {e}", exc_info=True)
        return None

@trace("semantic_cache_add")
async def add_to_semantic_cache(query: str, response_data: List[Dict[str, Any]]):
    """
    Adds a query and its structured response data to the semantic cache.
    """
    if not qdrant_client or not cache_encoder or CACHE_VECTOR_DIM is None:
        logger.error("Cannot add to semantic cache: Dependencies not initialized.")
        return
    if not isinstance(response_data, list) or not response_data:
         logger.warning(f"Attempted to cache invalid response_data for query '{query[:50]}...'. Aborting cache add.")
         return

    try:
        logger.debug(f"Generating semantic cache vector for query: '{query[:50]}...'")
        query_vector = cache_encoder.encode(query).tolist()
        point_id = str(uuid.uuid4()) # Unique ID for each cache entry
        collection_name = settings.QDRANT_CACHE_COLLECTION

        payload = {
            "question_text": query,
            "response_data": response_data, # Store the list of message dicts
            "cached_at": datetime.now(timezone.utc).isoformat()
        }

        logger.info(f"Adding entry to semantic cache '{collection_name}' for query: '{query[:50]}...'")
        await qdrant_client.upsert(
            collection_name=collection_name,
            points=[models.PointStruct(id=point_id, vector=query_vector, payload=payload)],
            wait=False
        )
        logger.debug(f"Successfully queued upsert to semantic cache for ID {point_id}.")

    except Exception as e:
        logger.error(f"Error adding to semantic cache for collection '{collection_name}': {e}", exc_info=True)


# --- Image Cache ---

@trace("image_cache_search")
async def search_image_cache(prompt: str) -> Optional[str]:
    """
    Searches the image cache for a similar prompt.
    Returns the cached image URL if a hit above the threshold is found.
    """
    if not qdrant_client or not cache_encoder or CACHE_VECTOR_DIM is None:
        logger.error("Cannot search image cache: Dependencies not initialized.")
        return None

    try:
        logger.debug(f"Generating image cache query vector for prompt: '{prompt[:50]}...'")
        query_vector = cache_encoder.encode(prompt).tolist() # Use same encoder
        collection_name = settings.QDRANT_IMAGE_CACHE_COLLECTION
        threshold = settings.IMAGE_CACHE_THRESHOLD

        logger.debug(f"Searching image cache '{collection_name}' with threshold {threshold}...")
        search_result = await qdrant_client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=1,
            score_threshold=threshold,
        )

        if search_result:
            hit = search_result[0]
            logger.info(f"Image cache hit for prompt '{prompt[:50]}...' (Score: {hit.score:.4f})")
            cached_payload = hit.payload
            if cached_payload and isinstance(cached_payload.get("image_url"), str):
                # Optional: Implement TTL check here if IMAGE_CACHE_TTL_DAYS is set
                logger.debug(f"Returning cached image URL: {cached_payload['image_url']}")
                return cached_payload["image_url"]
            else:
                logger.warning(f"Image cache hit for prompt '{prompt[:50]}' but payload invalid. Discarding.")
                return None
        else:
             logger.debug(f"Image cache miss for prompt '{prompt[:50]}...'.")
             return None

    except Exception as e:
        logger.error(f"Error during image cache search for collection '{collection_name}': {e}", exc_info=True)
        return None

@trace("image_cache_add")
async def add_to_image_cache(prompt: str, image_url: str, generating_model: Optional[str] = None):
    """
    Adds a generated image prompt and URL to the image cache.
    Uses a hash of the prompt as the point ID for potential deduplication.
    """
    if not qdrant_client or not cache_encoder or CACHE_VECTOR_DIM is None:
        logger.error("Cannot add to image cache: Dependencies not initialized.")
        return
    if not prompt or not image_url:
        logger.warning("Attempted to add empty prompt or URL to image cache. Aborting.")
        return

    try:
        logger.debug(f"Generating image cache vector for prompt: '{prompt[:50]}...'")
        prompt_vector = cache_encoder.encode(prompt).tolist() # Use same encoder
        collection_name = settings.QDRANT_IMAGE_CACHE_COLLECTION

        # Use SHA256 hash of the prompt as the point ID
        point_id = hashlib.sha256(prompt.encode('utf-8')).hexdigest()

        # Prepare payload using the Pydantic model for structure/validation
        payload_data = {
            "prompt_text": prompt,
            "image_url": image_url,
            "cached_at": datetime.now(timezone.utc), # Store datetime object
            "generating_model": generating_model
        }
        # Create payload dict from model, excluding unset fields
        payload = ImageCachePayload(**payload_data).model_dump(exclude_unset=True)
        # Ensure datetime is ISO formatted string for JSON compatibility in Qdrant
        payload["cached_at"] = payload["cached_at"].isoformat()

        logger.info(f"Adding entry to image cache '{collection_name}' for prompt: '{prompt[:50]}...' (ID: {point_id})")
        await qdrant_client.upsert(
            collection_name=collection_name,
            points=[models.PointStruct(id=point_id, vector=prompt_vector, payload=payload)],
            wait=False
        )
        logger.debug(f"Successfully queued upsert to image cache for ID {point_id}.")

    except Exception as e:
        logger.error(f"Error adding to image cache for collection '{collection_name}': {e}", exc_info=True)