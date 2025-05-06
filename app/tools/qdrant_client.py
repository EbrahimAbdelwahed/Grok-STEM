import logging
import os
from typing import Dict, Any, List, Optional
import hashlib

# Import Qdrant client library
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams
from qdrant_client.http.models import PointStruct

# For text embedding
import requests

logger = logging.getLogger(__name__)

# Configure Qdrant connection from environment variables
QDRANT_HOST = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))
EMBEDDING_API_KEY = os.environ.get("EMBEDDING_API_KEY")
EMBEDDING_API_ENDPOINT = os.environ.get("EMBEDDING_API_ENDPOINT", "https://api.openai.com/v1/embeddings")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-ada-002")
EMBEDDING_DIMENSION = int(os.environ.get("EMBEDDING_DIMENSION", "1536"))  # Default for OpenAI Ada

class QdrantWrapper:
    """Wrapper for Qdrant vector database client with text search capabilities."""
    
    def __init__(self):
        self.client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        self._ensure_collections_exist()
    
    def _ensure_collections_exist(self):
        """Ensure required collections exist in Qdrant."""
        collections = ["illustrations"]
        
        for collection in collections:
            try:
                collection_info = self.client.get_collection(collection_name=collection)
                logger.info(f"Collection {collection} exists")
            except Exception:
                logger.info(f"Creating collection {collection}")
                self.client.create_collection(
                    collection_name=collection,
                    vectors_config=VectorParams(size=EMBEDDING_DIMENSION, distance=Distance.COSINE)
                )
    
    def _get_text_embedding(self, text: str) -> List[float]:
        """
        Get embedding vector for text using OpenAI API.
        
        Args:
            text: The text to embed
            
        Returns:
            List of embedding values
        """
        if not EMBEDDING_API_KEY:
            raise ValueError("EMBEDDING_API_KEY not configured")
        
        headers = {
            "Authorization": f"Bearer {EMBEDDING_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "input": text,
            "model": EMBEDDING_MODEL
        }
        
        response = requests.post(
            EMBEDDING_API_ENDPOINT,
            headers=headers,
            json=payload
        )
        
        if response.status_code != 200:
            raise Exception(f"API error: {response.status_code} - {response.text}")
        
        result = response.json()
        if "data" not in result or not result["data"]:
            raise Exception("No embedding data returned from API")
        
        return result["data"][0]["embedding"]
    
    def search(self, collection_name: str, query_text: str, limit: int = 5):
        """
        Search for similar items based on text query.
        
        Args:
            collection_name: The name of the collection to search
            query_text: The text query to search for
            limit: Maximum number of results to return
            
        Returns:
            List of search results
        """
        query_vector = self._get_text_embedding(query_text)
        
        return self.client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit
        )
    
    def upload_text(self, collection_name: str, text: str, metadata: Dict[str, Any]):
        """
        Upload text with metadata to the vector database.
        
        Args:
            collection_name: The collection to store the data in
            text: The text to embed and store
            metadata: Additional metadata to store with the embedding
        """
        # Generate embedding for the text
        embedding = self._get_text_embedding(text)
        
        # Create a unique ID from the text content
        point_id = hashlib.md5(text.encode('utf-8')).hexdigest()
        
        # Upload the point to Qdrant
        self.client.upsert(
            collection_name=collection_name,
            points=[
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=metadata
                )
            ]
        )

# Singleton pattern for the client
_qdrant_client = None

def get_qdrant_client():
    """Get the singleton Qdrant client instance."""
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantWrapper()
    return _qdrant_client