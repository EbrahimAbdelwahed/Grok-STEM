"""
Centralized logging configuration and correlation ID management.
"""
import contextvars
import logging
import uuid
from typing import Optional

# Create a context variable for correlation ID
correlation_id_var = contextvars.ContextVar("correlation_id", default=None)

def configure_logging():
    """Configure logging for the application."""
    # Basic configuration - customize as needed
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    """Set the correlation ID for the current context."""
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())
    correlation_id_var.set(correlation_id)
    return correlation_id

def get_correlation_id() -> Optional[str]:
    """Get the correlation ID for the current context."""
    return correlation_id_var.get()

def clear_correlation_id() -> None:
    """Clear the correlation ID for the current context."""
    correlation_id_var.set(None)