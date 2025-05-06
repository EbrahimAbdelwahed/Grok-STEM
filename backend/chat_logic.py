import logging
import uuid
import re
import json
from typing import AsyncGenerator, Dict, Any, List

from backend.config import settings
from backend.llm_clients import get_grok_reasoning, get_plotly_json
from backend.rag_utils import search_semantic_cache, add_to_semantic_cache
from backend.schemas import StepInfo, ProgressChunk

logger = logging.getLogger(__name__)

# Regex to find steps like "## Step 1: ..." or "# Step 1 - ..." etc.
STEP_PATTERN = re.compile(r"^\s*#{1,4}\s*Step\s+(\d+)\s*[:\-–—]\s*(.+)$", re.MULTILINE | re.IGNORECASE)

async def process_user_message(user_message: str, chat_id: str) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Processes a user message through the RAG, Cache, and LLM pipeline.

    Yields:
        Dict[str, Any]: Chunks of the response (progress, text, steps, plot, error, end).
    """
    message_id = uuid.uuid4().hex
    logger.info(f"[{chat_id}][{message_id}] Processing message: '{user_message[:50]}...'")

    # Emit initial progress
    yield {"type": "progress", "phase": "reasoning", "id": message_id, "chat_id": chat_id}

    # --- 1. Semantic Cache Lookup ---
    try:
        cached_response = await search_semantic_cache(user_message)
        if cached_response:
            logger.info(f"[{chat_id}][{message_id}] Cache hit found. Returning cached response.")
            for part in cached_response:
                yield {"type": part.get("type", "unknown"), "id": message_id, "chat_id": chat_id, **part}
            yield {"type": "end", "id": message_id, "chat_id": chat_id}
            return
    except Exception as e:
        logger.error(f"[{chat_id}][{message_id}] Error during semantic cache lookup: {e}", exc_info=True)

    # --- 2. LLM Reasoning Call ---
    full_response_text = ""
    response_parts_for_cache: List[Dict[str, Any]] = []
    
    try:
        grok_resp_data = await get_grok_reasoning([{"role": "user", "content": user_message}], effort="medium")

        if not grok_resp_data or not grok_resp_data.get("content"):
            logger.warning(f"[{chat_id}][{message_id}] Grok reasoning returned empty content.")
            yield {"type": "error", "id": message_id, "chat_id": chat_id, "content": "Sorry, I could not generate a reasoned response. Please try again."}
            yield {"type": "end", "id": message_id, "chat_id": chat_id}
            return

        full_response_text = grok_resp_data.get("content", "")
        # Stream text
        yield {"type": "text", "id": message_id, "chat_id": chat_id, "content": full_response_text}
        response_parts_for_cache.append({"type": "text", "content": full_response_text})

    except Exception as e:
        logger.exception(f"[{chat_id}][{message_id}] Error during Grok reasoning: {e}")
        yield {"type": "error", "id": message_id, "chat_id": chat_id, "content": "An error occurred while generating the response."}
        yield {"type": "end", "id": message_id, "chat_id": chat_id}
        return

    # Update progress: steps
    yield {"type": "progress", "phase": "steps", "id": message_id, "chat_id": chat_id}

    # --- 3. Extract Steps ---
    extracted_steps: List[StepInfo] = []
    try:
        for match in STEP_PATTERN.finditer(full_response_text):
            step_num = match.group(1)
            step_title = match.group(2).strip()
            extracted_steps.append({"id": f"step-{step_num}", "title": step_title})

        if extracted_steps:
            yield {"type": "steps", "id": message_id, "chat_id": chat_id, "steps": extracted_steps}
            response_parts_for_cache.append({"type": "steps", "steps": extracted_steps})
    except Exception as e:
        logger.error(f"[{chat_id}][{message_id}] Error parsing steps: {e}", exc_info=True)

    # Update progress: plotting
    yield {"type": "progress", "phase": "plotting", "id": message_id, "chat_id": chat_id}

    # --- 4. Plot Generation ---
    try:
        plotly_spec = await get_plotly_json([
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": full_response_text}
        ])
        if plotly_spec:
            yield {"type": "plot", "id": message_id, "chat_id": chat_id, "plotly_json": plotly_spec}
            response_parts_for_cache.append({"type": "plot", "plotly_json": plotly_spec})
    except Exception as e:
        logger.error(f"[{chat_id}][{message_id}] Error generating plot: {e}", exc_info=True)

    # --- 5. Cache Response ---
    if response_parts_for_cache:
        try:
            await add_to_semantic_cache(user_message, response_parts_for_cache)
        except Exception as e:
            logger.error(f"[{chat_id}][{message_id}] Failed to cache response: {e}", exc_info=True)

    # Finalize
    yield {"type": "end", "id": message_id, "chat_id": chat_id}
    logger.info(f"[{chat_id}][{message_id}] Completed processing.")
