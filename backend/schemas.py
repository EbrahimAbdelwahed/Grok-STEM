# backend/schemas.py

from pydantic import BaseModel, Field, HttpUrl
from typing import List, Dict, Any, Literal, Optional
from datetime import datetime, timezone # Import datetime and timezone

# --- WebSocket Message Schemas ---

class WebSocketMessageBase(BaseModel):
    """Base model for WebSocket messages, includes the message ID."""
    id: str = Field(..., description="Unique identifier for the message stream")
    chat_id: str = Field(..., description="Identifier for the chat session") # Add chat_id here

class InitMessage(BaseModel):
    """Initial message sent from backend to client on connection."""
    type: Literal['init'] = 'init'
    chat_id: str = Field(..., description="Unique identifier assigned to this chat session")

class ProgressChunk(WebSocketMessageBase):
    """Message indicating current processing phase."""
    type: Literal['progress'] = 'progress'
    phase: Literal[
        'cache_check', 'retrieval', 'refining', 'reasoning',
        'steps', 'plotting', 'image_generation' # Added phases
    ] = Field(
        ..., description="Current processing phase"
    )

class TextChunk(WebSocketMessageBase):
    """Message containing a chunk of text content."""
    type: Literal['text'] = 'text'
    content: str = Field(..., description="The text content chunk")

class StepInfo(BaseModel):
    """Structure for a single reasoning step."""
    id: str = Field(..., description="Unique ID for the step (e.g., 'step-1')")
    title: str = Field(..., description="Short title/summary of the step")

class StepsList(WebSocketMessageBase):
    """Message containing the list of reasoning steps."""
    type: Literal['steps'] = 'steps'
    steps: List[StepInfo] = Field(..., description="List of reasoning steps")

class PlotData(WebSocketMessageBase):
    """Message containing Plotly JSON data."""
    type: Literal['plot'] = 'plot'
    plotly_json: Dict[str, Any] = Field(
        ..., description="Plotly JSON object (data and layout)"
    )

# --- NEW: Image Related Chunks ---
class ImageChunk(WebSocketMessageBase):
    """Message containing the URL of a generated/cached image."""
    type: Literal['image'] = 'image'
    image_url: HttpUrl = Field(..., description="URL of the generated or cached image")
    # Optional: Include the prompt that generated it for context/alt text?
    # image_prompt: Optional[str] = Field(None, description="The prompt used for this image")

class ImageRetryChunk(WebSocketMessageBase):
    """Message indicating an image generation attempt failed and is retrying."""
    type: Literal['image_retry'] = 'image_retry'
    attempt: int = Field(..., description="Current retry attempt number")
    max_attempts: int = Field(..., description="Maximum number of retry attempts")

class ImageErrorChunk(WebSocketMessageBase):
    """Message indicating image generation failed permanently."""
    type: Literal['image_error'] = 'image_error'
    content: str = Field(..., description="Error message explaining why image generation failed")

# --- General Error / End ---
class ErrorMessage(WebSocketMessageBase):
    """Message containing a general error detail."""
    type: Literal['error'] = 'error'
    content: str = Field(..., description="Error message description")

class EndMessage(WebSocketMessageBase):
    """Signals the end of a multi-part response stream."""
    type: Literal['end'] = 'end'

# --- HTTP Response Models ---

class HealthResponse(BaseModel):
    """Response model for the /health endpoint."""
    status: Literal['ok', 'error'] = Field(..., description="Overall health status")
    dependencies: Dict[str, Any] = Field(
        ..., description="Status of dependencies like Qdrant and LLMs"
    )

# --- Data Models for RAG/Cache ---

class RAGDocumentPayload(BaseModel):
    """Payload structure for points in the RAG collection."""
    text_content: str = Field(..., description="Document text content")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (e.g., source, domain)"
    )
    # Used by placeholder ingestion script - can be removed if not needed elsewhere
    # id: Optional[str] = Field(None) # Placeholder script adds ID here

class DocumentToIngest(BaseModel):
    """Model used by placeholder ingestion script."""
    id: str
    text_content: str
    metadata: Dict[str, Any]


class SemanticCachePayload(BaseModel):
    """Payload structure for points in the semantic cache collection."""
    question_text: str = Field(..., description="The original user query")
    response_data: List[Dict[str, Any]] = Field(
        ..., description="Structured response parts cached (list of WS chunks)"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (e.g., cached_at timestamp)"
    )

class ImageCachePayload(BaseModel):
    """Payload structure for points in the image cache collection."""
    prompt_text: str = Field(..., description="The prompt used for image generation")
    image_url: HttpUrl = Field(..., description="The URL of the cached image")
    cached_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp when the entry was cached")
    generating_model: Optional[str] = Field(None, description="Identifier of the model that generated the image")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata if needed"
    )

# --- Models for User-Triggered Actions (if using HTTP endpoint or specific WS message) ---
class GenerateImageRequest(BaseModel):
     """Request model for user-triggered image generation."""
     chat_id: str
     # ID of the assistant message this request relates to
     assistant_message_id: str
     # The original user query that led to the assistant message
     original_user_query: str