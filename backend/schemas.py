# backend/schemas.py

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal

# --- WebSocket Message Schemas ---

class WebSocketMessageBase(BaseModel):
    """Base model for WebSocket messages, includes the message ID."""
    id: str = Field(..., description="Unique identifier for the message stream")

class TextChunk(WebSocketMessageBase):
    """Message containing a chunk of text content."""
    type: Literal['text'] = "text"
    content: str = Field(..., description="The text content chunk")

class PlotData(WebSocketMessageBase):
    """Message containing Plotly JSON data."""
    type: Literal['plot'] = "plot"
    # Use Dict[str, Any] for flexibility, or define more specific Plotly types if needed
    plotly_json: Dict[str, Any] = Field(..., description="Plotly JSON object (data and layout)")

class StepInfo(BaseModel):
    """Structure for a single reasoning step."""
    id: str = Field(..., description="Unique ID for the step (e.g., 'step-1')")
    title: str = Field(..., description="Short title/summary of the step")

class StepsList(WebSocketMessageBase):
    """Message containing the list of reasoning steps."""
    type: Literal['steps'] = "steps"
    steps: List[StepInfo] = Field(..., description="List of reasoning steps")

class EndMessage(WebSocketMessageBase):
    """Signals the end of a multi-part response stream."""
    type: Literal['end'] = "end"

class ErrorMessage(WebSocketMessageBase):
    """Message containing an error detail."""
    type: Literal['error'] = "error"
    content: str = Field(..., description="Error message description")

# --- Request/Response Models (for potential future HTTP routes) ---

class HealthResponse(BaseModel):
    """Response model for the /health endpoint."""
    status: Literal['ok', 'error']
    dependencies: Dict[str, Any] # Contains status of Qdrant, LLMs, etc.

# --- Data Models for RAG/Cache ---

class RAGDocumentPayload(BaseModel):
    """Payload structure for points in the RAG collection."""
    text_content: str
    metadata: Dict[str, Any] = Field(default_factory=dict) # e.g., {"source": "...", "domain": "Physics"}

class SemanticCachePayload(BaseModel):
    """Payload structure for points in the semantic cache collection."""
    question_text: str
    # Store the full structured response that was sent as a list of dicts
    response_data: List[Dict[str, Any]]
    metadata: Dict[str, Any] = Field(default_factory=dict) # e.g., {"cached_at": "...", "query_count": 1}

# Example model for a document to be ingested (could be used in data pipeline)
class DocumentToIngest(BaseModel):
     id: str
     text_content: str
     metadata: Dict[str, Any] = Field(default_factory=dict)