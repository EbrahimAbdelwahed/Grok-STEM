import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, HttpUrl, field_validator  # Added field_validator
from typing import Optional, List

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # --- LLM API Keys & Config ---
    xai_api_key: str = Field(..., validation_alias='XAI_API_KEY')
    xai_base_url: HttpUrl = Field(..., validation_alias='XAI_BASE_URL')
    openai_api_key: str = Field(..., validation_alias='OPENAI_API_KEY')

    # Model names (allow overriding via env vars)
    reasoning_model_name: str = Field(
        "grok-3-mini-beta", validation_alias='REASONING_MODEL_NAME'
    )
    plotting_model_name: str = Field(
        "gpt-4o-mini", validation_alias='PLOTTING_MODEL_NAME'
    )

    # --- Qdrant Configuration ---
    qdrant_url: str = Field("http://qdrant:6333", validation_alias='QDRANT_URL')
    qdrant_api_key: Optional[str] = Field(None, validation_alias='QDRANT_API_KEY')
    qdrant_rag_collection: str = Field(
        "stem_rag_kb", validation_alias='QDRANT_RAG_COLLECTION'
    )
    qdrant_cache_collection: str = Field(
        "semantic_cache", validation_alias='QDRANT_CACHE_COLLECTION'
    )

    # --- RAG & Cache Settings ---
    rag_num_results: int = Field(2, validation_alias='RAG_NUM_RESULTS')
    cache_threshold: float = Field(
        0.90, validation_alias='CACHE_THRESHOLD'
    )

    # --- Backend Settings ---
    log_level: str = Field("INFO", validation_alias='LOG_LEVEL')

    # Define CORS origins (example, adjust as needed)
        # Raw CORS origins from env var (JSON list or comma-separated)
    cors_allowed_origins_raw: Optional[str] = Field(
        None,
        validation_alias='CORS_ALLOWED_ORIGINS',
    )

    @property
    def cors_allowed_origins(self) -> List[str]:
        """
        Parsed CORS origins as a list of strings. Supports JSON lists or comma-separated values.
        """
        raw = self.cors_allowed_origins_raw
        # Use default if not set
        if not raw:
            return ["http://localhost", "http://localhost:5173"]
        # Try JSON list
        try:
            import json
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except Exception:
            pass
        # Fallback: comma-separated
        return [orig.strip() for orig in raw.split(',') if orig.strip()]

# Create a single instance for import elsewhere
settings = Settings()

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=settings.log_level.upper())
    logger = logging.getLogger(__name__)

    logger.info("Loaded Settings:")
    logger.info(f"  Allowed Origins: {settings.cors_allowed_origins}")
