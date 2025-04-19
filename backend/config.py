# backend/rag_utils.py

import logging
import uuid
from typing import List, Optional, Dict, Any

from qdrant_client import models
from sentence_transformers import SentenceTransformer

# Absolute import for the local Qdrant service module (to avoid shadowing)
from qdrant_service import qdrant_client
from config import settings
from schemas import SemanticCacheItem

logger = logging.getLogger(__name__)

# --- Embedding Models ---
try:
    logger.info("Loading embedding models...")
    rag_embedding_model_name = "sentence-transformers/all-MiniLM-L6-v2"
    rag_encoder = SentenceTransformer(rag_embedding_model_name)
    RAG_VECTOR_DIM = rag_encoder.get_sentence_embedding_dimension()
    logger.info(f"RAG encoder '{rag_embedding_model_name}' loaded (Dim: {RAG_VECTOR_DIM}).")

    cache_embedding_model_name = "sentence-transformers/all-MiniLM-L6-v2"
    cache_encoder = SentenceTransformer(cache_embedding_model_name)
    CACHE_VECTOR_DIM = cache_encoder.get_sentence_embedding_dimension()
    logger.info(f"Cache encoder '{cache_embedding_model_name}' loaded (Dim: {CACHE_VECTOR_DIM}).")
except Exception as e:
    logger.error(f"Failed to load embedding models: {e}", exc_info=True)
    rag_encoder = None
    cache_encoder = None

# --- RAG Retrieval ---
async def search_rag_kb(query: str, k: int = settings.rag_num_results) -> List[str]:
    if not qdrant_client or not rag_encoder:
        logger.error("Qdrant client or RAG encoder not initialized.")
        return []
    try:
        query_vector = rag_encoder.encode(query).tolist()
        search_result = await qdrant_client.search(
            collection_name=settings.qdrant_rag_collection,
            query_vector=query_vector,
            limit=k,
        )
        contexts = [hit.payload.get("text_content", "") for hit in search_result if hit.payload]
        logger.info(f"RAG search for '{query[:50]}...' found {len(contexts)} contexts.")
        return contexts
    except Exception as e:
        logger.error(f"Error during RAG search: {e}", exc_info=True)
        return []

# --- Semantic Cache ---
async def search_semantic_cache(query: str, threshold: float = settings.cache_threshold) -> Optional[List[Dict[str, Any]]]:
    if not qdrant_client or not cache_encoder:
        logger.error("Qdrant client or Cache encoder not initialized.")
        return None
    try:
        query_vector = cache_encoder.encode(query).tolist()
        search_result = await qdrant_client.search(
            collection_name=settings.qdrant_cache_collection,
            query_vector=query_vector,
            limit=1,
            score_threshold=threshold,
        )
        if search_result:
            hit = search_result[0]
            logger.info(f"Semantic cache hit for '{query[:50]}...' with score {hit.score:.4f}")
            cached_response = hit.payload.get("response_data") if hit.payload else None
            if isinstance(cached_response, list):
                return cached_response
            logger.warning(f"Cache hit but invalid response_data type: {type(cached_response)}")
        return None
    except Exception as e:
        logger.error(f"Error during semantic cache search: {e}", exc_info=True)
        return None

async def add_to_semantic_cache(query: str, response_data: List[Dict[str, Any]]):
    if not qdrant_client or not cache_encoder:
        logger.error("Cannot add to cache: Qdrant client or Cache encoder not initialized.")
        return
    try:
        query_vector = cache_encoder.encode(query).tolist()
        point_id = str(uuid.uuid4())
        payload = {
            "question_text": query,
            "response_data": response_data,
            # Add additional metadata if desired
        }
        await qdrant_client.upsert(
            collection_name=settings.qdrant_cache_collection,
            points=[
                models.PointStruct(
                    id=point_id,
                    vector=query_vector,
                    payload=payload
                )
            ],
            wait=False
        )
        logger.info(f"Added '{query[:50]}...' to semantic cache.")
    except Exception as e:
        logger.error(f"Error adding to semantic cache: {e}", exc_info=True)
