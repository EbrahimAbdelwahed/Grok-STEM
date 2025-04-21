import os
import json
import logging
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, HttpUrl, field_validator, validator
from typing import Optional, List, Union

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # --- LLM API Keys & Config ---
    XAI_API_KEY: str = Field(..., validation_alias='XAI_API_KEY')
    XAI_BASE_URL: HttpUrl = Field(..., validation_alias='XAI_BASE_URL')
    OPENAI_API_KEY: str = Field(..., validation_alias='OPENAI_API_KEY')

    # Model names (allow overriding via env vars)
    REASONING_MODEL_NAME: str = Field(
        "grok-3-mini-beta", validation_alias='REASONING_MODEL_NAME'
    )
    PLOTTING_MODEL_NAME: str = Field(
        "gpt-4o-mini", validation_alias='PLOTTING_MODEL_NAME'
    )

    # --- Embedding Model Configuration ---
    # Using all-MiniLM-L6-v2 as default for both RAG and Cache
    EMBEDDING_MODEL_NAME: str = Field(
        "sentence-transformers/all-MiniLM-L6-v2", validation_alias='EMBEDDING_MODEL_NAME'
    )
    # Vector dimensions are derived in rag_utils.py after loading model,
    # but we can define expected defaults or allow override here if needed.
    # RAG_VECTOR_DIM: int = Field(384, validation_alias='RAG_VECTOR_DIM')
    # CACHE_VECTOR_DIM: int = Field(384, validation_alias='CACHE_VECTOR_DIM')

    # --- Qdrant Configuration ---
    QDRANT_URL: str = Field("http://qdrant:6333", validation_alias='QDRANT_URL')
    QDRANT_API_KEY: Optional[str] = Field(None, validation_alias='QDRANT_API_KEY')
    QDRANT_RAG_COLLECTION: str = Field(
        "stem_rag_kb", validation_alias='QDRANT_RAG_COLLECTION'
    )
    QDRANT_CACHE_COLLECTION: str = Field(
        "semantic_cache", validation_alias='QDRANT_CACHE_COLLECTION'
    )

    # --- RAG & Cache Settings ---
    RAG_NUM_RESULTS: int = Field(3, validation_alias='RAG_NUM_RESULTS') # Increased default slightly
    CACHE_THRESHOLD: float = Field(
        0.92, validation_alias='CACHE_THRESHOLD' # Slightly increased default
    )

    # --- Backend Settings ---
    LOG_LEVEL: str = Field("INFO", validation_alias='LOG_LEVEL')

    # --- CORS Origins ---
    CORS_ALLOWED_ORIGINS: Union[str, List[str]] = Field(
        '["http://localhost:5173", "http://127.0.0.1:5173"]',
        validation_alias='CORS_ALLOWED_ORIGINS',
    )

    _cors_origins_list: List[str] = [] # Private attribute to store parsed list

    # Pydantic V2 validator for CORS_ALLOWED_ORIGINS
    @validator('CORS_ALLOWED_ORIGINS', pre=True, always=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, list):
            return [str(origin).strip() for origin in v if str(origin).strip()]
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return [] # Return empty list if string is empty
            if v.startswith('[') and v.endswith(']'):
                try:
                    parsed_list = json.loads(v)
                    if isinstance(parsed_list, list):
                        return [str(origin).strip() for origin in parsed_list if str(origin).strip()]
                    else:
                        logger.warning(f"CORS_ALLOWED_ORIGINS JSON string did not decode to a list: {v}")
                        return []
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse CORS_ALLOWED_ORIGINS as JSON list: {v}. Falling back to comma-separated.")
            # Fallback to comma-separated
            return [origin.strip() for origin in v.split(',') if origin.strip()]
        # Handle case where it's neither string nor list (e.g., None)
        logger.warning(f"Invalid type for CORS_ALLOWED_ORIGINS: {type(v)}. Returning empty list.")
        return []

    # Use a property to access the correctly parsed list
    @property
    def cors_allowed_origins_list(self) -> List[str]:
         # The validator ensures CORS_ALLOWED_ORIGINS is always a list of strings
        return self.CORS_ALLOWED_ORIGINS


    # Load from .env file if it exists
    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'
        # For Pydantic V2 SettingsConfigDict is used instead of inner class Config
        # model_config = SettingsConfigDict(
        #     env_file='.env',
        #     env_file_encoding='utf-8'
        # )

# Create a single instance for import elsewhere
settings = Settings()

# Optional: Log loaded settings on startup (e.g., in main.py)
# Example logging in main.py:
# logger.info("GrokSTEM Backend Settings Loaded:")
# logger.info(f"  - Reasoning Model: {settings.REASONING_MODEL_NAME}")
# logger.info(f"  - Plotting Model: {settings.PLOTTING_MODEL_NAME}")
# logger.info(f"  - Qdrant URL: {settings.QDRANT_URL}")
# logger.info(f"  - RAG Collection: {settings.QDRANT_RAG_COLLECTION}")
# logger.info(f"  - Cache Collection: {settings.QDRANT_CACHE_COLLECTION}")
# logger.info(f"  - CORS Origins: {settings.cors_allowed_origins_list}")
# logger.info(f"  - Log Level: {settings.LOG_LEVEL}")