# backend/config.py

import json
import logging
from pydantic_settings import BaseSettings
from pydantic import Field, HttpUrl, validator
from typing import Optional, List, Union

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # --- LLM API Keys & Config ---
    XAI_API_KEY: str = Field(..., validation_alias='XAI_API_KEY')
    XAI_BASE_URL: HttpUrl = Field(..., env='XAI_BASE_URL')
    OPENAI_API_KEY: str = Field(..., validation_alias='OPENAI_API_KEY')
    OPENAI_BASE_URL: Optional[HttpUrl] = Field(
        None,
        validation_alias="OPENAI_BASE_URL",
        description="Optional override (e.g. proxy) for the OpenAI REST endpoint; DO NOT include /v1."
    )

    # Model names (allow overriding via env vars)
    REASONING_MODEL_NAME: str = Field(
        "grok-3-mini-beta", validation_alias='REASONING_MODEL_NAME'
    )
    PLOTTING_MODEL_NAME: str = Field(
        "gpt-4o-mini", validation_alias='PLOTTING_MODEL_NAME'
    )
    # NEW: Model for generating image prompts from user queries
    IMAGE_PROMPT_GEN_MODEL_NAME: str = Field(
        "gpt-4o-mini", validation_alias='IMAGE_PROMPT_GEN_MODEL_NAME'
    )
    # NEW: Model for actual image generation
    IMAGE_MODEL_NAME: str = Field(
        "dall-e-3", validation_alias='IMAGE_MODEL_NAME' # Using DALL-E 3 as placeholder
    )


    # --- Embedding Model Configuration ---
    EMBEDDING_MODEL_NAME: str = Field(
        "sentence-transformers/all-MiniLM-L6-v2", validation_alias='EMBEDDING_MODEL_NAME'
    )

    # --- Qdrant Configuration ---
    QDRANT_URL: str = Field("http://qdrant:6333", validation_alias='QDRANT_URL')
    QDRANT_API_KEY: Optional[str] = Field(None, validation_alias='QDRANT_API_KEY')
    QDRANT_RAG_COLLECTION: str = Field(
        "stem_rag_kb", validation_alias='QDRANT_RAG_COLLECTION'
    )
    QDRANT_CACHE_COLLECTION: str = Field( # Semantic (LLM response) Cache
        "semantic_cache", validation_alias='QDRANT_CACHE_COLLECTION'
    )
    QDRANT_IMAGE_CACHE_COLLECTION: str = Field( # NEW: Image Cache
        "image_cache", validation_alias='QDRANT_IMAGE_CACHE_COLLECTION'
    )


    # --- RAG & Cache Settings ---
    RAG_NUM_RESULTS: int = Field(3, validation_alias='RAG_NUM_RESULTS')
    CACHE_THRESHOLD: float = Field( # Semantic (LLM response) Cache
        0.92, validation_alias='CACHE_THRESHOLD'
    )
    IMAGE_CACHE_THRESHOLD: float = Field( # NEW: Image Cache Threshold
        0.95, validation_alias='IMAGE_CACHE_THRESHOLD' # Higher threshold often desired for images
    )
    # IMAGE_CACHE_TTL_DAYS: Optional[int] = Field( # NEW: Optional TTL (Not implemented yet)
    #     None, validation_alias='IMAGE_CACHE_TTL_DAYS', description="Optional: Days until image cache entries expire (requires separate cleanup process)"
    # )

    # --- Backend Settings ---
    LOG_LEVEL: str = Field("INFO", validation_alias='LOG_LEVEL')
    # --- Observability ------------------------------------------------------- #
    VERBOSE_TRACE: bool = Field(
        False,
        validation_alias="VERBOSE_TRACE",
        description="Emit entry/exit logs for each @trace-decorated function."
    )
    HTTP_LOG_BODY: bool = Field(
        False,
        validation_alias="HTTP_LOG_BODY",
        description="Log request/response bodies for outbound HTTP when True."
    )
    TRACE_ID_HEADER: str = Field(
        "x-request-id",
        validation_alias="TRACE_ID_HEADER",
        description="Header used to propagate correlation IDs."
    )
    LOG_JSON: bool = Field(
        False,
        validation_alias="LOG_JSON",
        description="Emit logs in JSON format instead of plain text."
    )

    # --- CORS Origins ---
    CORS_ALLOWED_ORIGINS: Union[str, List[str]] = Field(
        '["http://localhost:5173", "http://127.0.0.1:5173"]',
        validation_alias='CORS_ALLOWED_ORIGINS',
    )

    # ------------------------------------------------------------------ #
    # Validators
    # ------------------------------------------------------------------ #

    @validator("OPENAI_BASE_URL", pre=True, always=True)
    def normalise_openai_base(cls, v: Optional[str]) -> Optional[str]:
        """
        Ensure we do not keep an erroneous '/v1' at the end of the custom
        base URL – the OpenAI Python SDK appends '/v1' automatically.
        """
        if not v:
            return v
        v = v.rstrip("/")  # remove trailing slash
        if v.endswith("/v1"):
            logger.debug("Trimming surplus '/v1' from OPENAI_BASE_URL.")
            v = v[: -len("/v1")]
        return v

    @validator('CORS_ALLOWED_ORIGINS', pre=True, always=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, list):
            return [str(origin).strip() for origin in v if str(origin).strip()]
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            if v.startswith('[') and v.endswith(']'):
                try:
                    parsed_list = json.loads(v)
                    if isinstance(parsed_list, list):
                        return [str(origin).strip() for origin in parsed_list if str(origin).strip()]
                    logger.warning("CORS_ALLOWED_ORIGINS JSON did not decode to a list.")
                    return []
                except json.JSONDecodeError:
                    logger.warning("Failed to parse CORS_ALLOWED_ORIGINS JSON; falling back to comma-sep list.")
            return [origin.strip() for origin in v.split(',') if origin.strip()]
        logger.warning("Invalid type for CORS_ALLOWED_ORIGINS. Returning empty list.")
        return []

    @validator("TRACE_ID_HEADER", pre=True, always=True)
    def lower_header(cls, v: str) -> str:
        return v.lower().strip()

    # Convenience property
    @property
    def cors_allowed_origins_list(self) -> List[str]:
        # This handles the case where it might already be a list or needs parsing
        if isinstance(self.CORS_ALLOWED_ORIGINS, list):
            return self.CORS_ALLOWED_ORIGINS
        else:
            # Re-run parsing logic if accessed as property and wasn't list initially
            return self.parse_cors_origins(self.CORS_ALLOWED_ORIGINS)


    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'
        # Allow extra fields if needed, though usually better to define all explicitly
        # extra = 'ignore'


# Create a single instance for import elsewhere
settings = Settings()

# Optional: Log loaded settings on startup (e.g., in main.py)
# Example logging in main.py:
# logger.info("GrokSTEM Backend Settings Loaded:")
# logger.info(f"  - Reasoning Model: {settings.REASONING_MODEL_NAME}")
# logger.info(f"  - Plotting Model: {settings.PLOTTING_MODEL_NAME}")
# logger.info(f"  - Image Prompt Gen Model: {settings.IMAGE_PROMPT_GEN_MODEL_NAME}") # NEW
# logger.info(f"  - Image Gen Model: {settings.IMAGE_MODEL_NAME}") # NEW
# logger.info(f"  - Qdrant URL: {settings.QDRANT_URL}")
# logger.info(f"  - RAG Collection: {settings.QDRANT_RAG_COLLECTION}")
# logger.info(f"  - Cache Collection: {settings.QDRANT_CACHE_COLLECTION}")
# logger.info(f"  - Image Cache Collection: {settings.QDRANT_IMAGE_CACHE_COLLECTION}") # NEW
# logger.info(f"  - CORS Origins: {settings.cors_allowed_origins_list}")
# logger.info(f"  - Log Level: {settings.LOG_LEVEL}")