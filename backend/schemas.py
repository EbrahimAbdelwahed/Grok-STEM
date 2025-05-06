# backend/schemas.py

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Literal

# --- WebSocket Message Schemas ---

class WebSocketMessageBase(BaseModel):
    """Base model for WebSocket messages, includes the message ID."""
    id: str = Field(..., description="Unique identifier for the message stream")

class ProgressChunk(WebSocketMessageBase):
    """Message indicating current processing phase."""
    type: Literal['progress'] = Field('progress', description="Chunk type")
    phase: Literal['reasoning', 'steps', 'plotting'] = Field(
        ..., description="Current processing phase (reasoning, steps, plotting)"
    )

class TextChunk(WebSocketMessageBase):
    """Message containing a chunk of text content."""
    type: Literal['text'] = Field('text', description="Chunk type")
    content: str = Field(..., description="The text content chunk")

class StepInfo(BaseModel):
    """Structure for a single reasoning step."""
    id: str = Field(..., description="Unique ID for the step (e.g., 'step-1')")
    title: str = Field(..., description="Short title/summary of the step")

class StepsList(WebSocketMessageBase):
    """Message containing the list of reasoning steps."""
    type: Literal['steps'] = Field('steps', description="Chunk type")
    steps: List[StepInfo] = Field(..., description="List of reasoning steps")

class PlotData(WebSocketMessageBase):
    """Message containing Plotly JSON data."""
    type: Literal['plot'] = Field('plot', description="Chunk type")
    plotly_json: Dict[str, Any] = Field(
        ..., description="Plotly JSON object (data and layout)"
    )

class ErrorMessage(WebSocketMessageBase):
    """Message containing an error detail."""
    type: Literal['error'] = Field('error', description="Chunk type")
    content: str = Field(..., description="Error message description")

class EndMessage(WebSocketMessageBase):
    """Signals the end of a multi-part response stream."""
    type: Literal['end'] = Field('end', description="Chunk type")

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

class SemanticCachePayload(BaseModel):
    """Payload structure for points in the semantic cache collection."""
    question_text: str = Field(..., description="The original user query")
    response_data: List[Dict[str, Any]] = Field(
        ..., description="Structured response parts cached"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (e.g., cached_at timestamp)"
    )
