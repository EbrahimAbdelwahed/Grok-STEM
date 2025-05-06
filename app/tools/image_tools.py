import logging
import requests
import os
from typing import Optional

# Import Qdrant client
from app.tools.qdrant_client import get_qdrant_client

logger = logging.getLogger(__name__)

# Configure API keys and endpoints from environment variables
IMAGE_API_KEY = os.environ.get("GPT_IMAGE_API_KEY")
IMAGE_API_ENDPOINT = os.environ.get("GPT_IMAGE_API_ENDPOINT", "https://api.openai.com/v1/images/generations")
IMAGE_COLLECTION_NAME = "illustrations"

def search_image_by_prompt(prompt: str) -> Optional[str]:
    """
    Search for an existing image in Qdrant based on the prompt.
    
    Args:
        prompt: The text prompt to search for
        
    Returns:
        URL to the image if found, None otherwise
    """
    try:
        client = get_qdrant_client()
        
        # Search for the closest match to the prompt
        results = client.search(
            collection_name=IMAGE_COLLECTION_NAME,
            query_text=prompt,
            limit=1
        )
        
        # Return the URL if we found a good match
        if results and len(results) > 0 and results[0].score > 0.8:
            return results[0].payload.get("url")
        
        return None
    except Exception as e:
        logger.error(f"Error searching for image: {str(e)}")
        return None

def generate_image(prompt: str) -> str:
    """
    Generate an image using GPT-Image-1 based on the prompt.
    
    Args:
        prompt: The text description for image generation
        
    Returns:
        URL to the generated image
    """
    if not IMAGE_API_KEY:
        raise ValueError("GPT_IMAGE_API_KEY not configured")
    
    headers = {
        "Authorization": f"Bearer {IMAGE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "prompt": prompt,
        "n": 1,
        "size": "1024x1024"
    }
    
    response = requests.post(
        IMAGE_API_ENDPOINT,
        headers=headers,
        json=payload
    )
    
    if response.status_code != 200:
        raise Exception(f"API error: {response.status_code} - {response.text}")
    
    result = response.json()
    if "data" not in result or not result["data"]:
        raise Exception("No image data returned from API")
    
    return result["data"][0]["url"]

def upload_image_to_qdrant(prompt: str, image_url: str) -> None:
    """
    Store the image prompt and URL in Qdrant for future retrieval.
    
    Args:
        prompt: The text prompt used to generate the image
        image_url: The URL of the generated image
    """
    try:
        client = get_qdrant_client()
        
        # Create a point with the prompt as text and url as payload
        client.upload_text(
            collection_name=IMAGE_COLLECTION_NAME,
            text=prompt,
            metadata={
                "url": image_url,
                "prompt": prompt,
                "source": "gpt-image-1"
            }
        )
        
        logger.info(f"Uploaded image to Qdrant with prompt: {prompt}")
    except Exception as e:
        logger.error(f"Error uploading image to Qdrant: {str(e)}")
        # Don't raise - this is not critical for the user experience