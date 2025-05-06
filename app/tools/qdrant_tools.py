import hashlib
from typing import Optional

import openai
import qdrant_client
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance, VectorParams, PointStruct


# Initialize the Qdrant client
client = QdrantClient(url="http://localhost:6333")

# Collection configuration
COLLECTION_NAME = "prompt_cache"
VECTOR_SIZE = 384  # Dimension size for text-embedding-3-mini


def ensure_collection():
    """
    Ensures that the prompt_cache collection exists with the correct configuration.
    If it doesn't exist, creates it with the appropriate vector parameters.
    """
    # Check if collection exists
    collections = client.get_collections().collections
    collection_names = [collection.name for collection in collections]
    
    if COLLECTION_NAME not in collection_names:
        # Create the collection with the required parameters
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config={
                "prompt": VectorParams(
                    size=VECTOR_SIZE,
                    distance=Distance.COSINE
                )
            }
        )
        print(f"Created collection '{COLLECTION_NAME}'")
    else:
        print(f"Collection '{COLLECTION_NAME}' already exists")


def get_embedding(text: str) -> list[float]:
    """
    Gets the embedding vector for a text prompt using OpenAI's embedding API.
    
    Args:
        text: The text to embed
        
    Returns:
        A list of floats representing the embedding vector
    """
    response = openai.embeddings.create(
        model="text-embedding-3-mini",
        input=text,
    )
    return response.data[0].embedding


def search_image_by_prompt(prompt: str) -> Optional[str]:
    """
    Searches for an image corresponding to a prompt in the Qdrant collection.
    
    Args:
        prompt: The text prompt to search for
        
    Returns:
        The image URL if found with high similarity, otherwise None
    """
    # Get the embedding for the prompt
    prompt_vector = get_embedding(prompt)
    
    # Search for similar prompts in Qdrant
    search_results = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=("prompt", prompt_vector),
        limit=1,
        score_threshold=0.95  # Only return results with ≥ 95% similarity
    )
    
    # Return the image URL if we found a match
    if search_results:
        return search_results[0].payload.get("image_url")
    return None


def upload_image_to_qdrant(prompt: str, image_url: str):
    """
    Uploads a prompt and corresponding image URL to Qdrant for caching.
    
    Args:
        prompt: The text prompt associated with the image
        image_url: The URL where the image is stored
    """
    # Create a stable ID based on the SHA-256 hash of the prompt
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
    point_id = int(prompt_hash[:16], 16)  # Convert first 16 chars of hash to integer
    
    # Get the embedding for the prompt
    prompt_vector = get_embedding(prompt)
    
    # Create a point with the prompt vector and payload
    point = PointStruct(
        id=point_id,
        vector={"prompt": prompt_vector},
        payload={
            "prompt_text": prompt,
            "image_url": image_url
        }
    )
    
    # Upsert the point into the collection
    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[point]
    )
    print(f"Uploaded image with prompt: '{prompt[:30]}...' to Qdrant")


# Ensure the collection exists when the module is imported
ensure_collection()