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
    status: Literal['ok'] = "ok"

# Example for a potential future HTTP chat endpoint
class ChatRequest(BaseModel):
    message: str
    user_id: Optional[str] = None # Optional user identifier
    reasoning_effort: Optional[Literal['low', 'medium', 'high']] = 'medium' # Example

class ChatResponse(BaseModel):
    response_id: str
    reply: str
    # Add other fields if needed for HTTP responses

# --- Data Models for RAG/Cache ---

class RAGDocument(BaseModel):
    """Represents a document stored for RAG."""
    id: str # Or UUID
    text_content: str
    metadata: Dict[str, Any] = {} # e.g., {"source": "...", "domain": "Physics"}

class SemanticCacheItem(BaseModel):
    """Represents an item in the semantic cache."""
    id: str # Or UUID
    question_embedding: Optional[List[float]] = None # Embedding stored separately usually
    question_text: str
    # Store the full structured response that was sent
    response_data: List[Dict[str, Any]] # List of serialized WebSocket messages
    metadata: Dict[str, Any] = {}