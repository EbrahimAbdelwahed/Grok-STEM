# backend/config.py

import os
import json
from pathlib import Path
from typing import List, Optional, Union
from pydantic import Field, AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# Load settings from .env file if it exists
# You can override these with actual environment variables
load_dotenv()

# Determine the base directory of the project (one level up from backend)
BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # --- LLM API Keys & Config ---
    xai_api_key: Optional[str] = Field(None, validation_alias='XAI_API_KEY')
    xai_base_url: Optional[Union[str, AnyHttpUrl]] = Field(None, validation_alias='XAI_BASE_URL')
    openai_api_key: Optional[str] = Field(None, validation_alias='OPENAI_API_KEY')

    # Model names (allow overriding via env vars)
    reasoning_model_name: str = Field("grok-3-mini-beta", validation_alias='REASONING_MODEL_NAME')
    plotting_model_name: str = Field("gpt-4o-mini", validation_alias='PLOTTING_MODEL_NAME')

    # --- Qdrant Configuration ---
    qdrant_url: str = Field("http://localhost:6333", validation_alias='QDRANT_URL')
    qdrant_api_key: Optional[str] = Field(None, validation_alias='QDRANT_API_KEY')
    qdrant_rag_collection: str = Field("stem_rag_kb", validation_alias='QDRANT_RAG_COLLECTION')
    qdrant_cache_collection: str = Field("semantic_cache", validation_alias='QDRANT_CACHE_COLLECTION')

    # --- RAG & Cache Settings ---
    rag_num_results: int = Field(2, validation_alias='RAG_NUM_RESULTS') # Number of docs to retrieve
    cache_threshold: float = Field(0.90, validation_alias='CACHE_THRESHOLD') # Similarity threshold for cache hit

    # --- Backend Settings ---
    log_level: str = Field("INFO", validation_alias='LOG_LEVEL')
    _cors_allowed_origins: str = Field("http://localhost:5173", validation_alias='CORS_ALLOWED_ORIGINS')

    @property
    def cors_allowed_origins(self) -> List[str]:
        if isinstance(self._cors_allowed_origins, str):
            return [origin.strip() for origin in self._cors_allowed_origins.split(',')]
        return []

    # Pydantic settings configuration
    model_config = SettingsConfigDict(
        env_file='.env',        # Load from .env file in the current directory (backend/)
        env_file_encoding='utf-8',
        extra='ignore'          # Ignore extra fields not defined in the model
    )

# Create a single instance of the settings to be imported elsewhere
settings = Settings()

# --- Example Usage ---
if __name__ == "__main__":
    print("Loaded Settings:")
    print(f"  Grok API Key: {'*' * (len(settings.xai_api_key) - 4) + settings.xai_api_key[-4:] if settings.xai_api_key else 'Not Set'}")
    print(f"  Grok Base URL: {settings.xai_base_url if settings.xai_base_url else 'Not Set'}")
    print(f"  OpenAI API Key: {'*' * (len(settings.openai_api_key) - 4) + settings.openai_api_key[-4:] if settings.openai_api_key else 'Not Set'}")
    print(f"  Reasoning Model: {settings.reasoning_model_name}")
    print(f"  Plotting Model: {settings.plotting_model_name}")
    print(f"  Qdrant URL: {settings.qdrant_url}")
    print(f"  Qdrant RAG Collection: {settings.qdrant_rag_collection}")
    print(f"  Qdrant Cache Collection: {settings.qdrant_cache_collection}")
    print(f"  Log Level: {settings.log_level}")
    print(f"  Allowed Origins: {settings.cors_allowed_origins}")