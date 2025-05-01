import logging
import uuid
import re
import json
from typing import AsyncGenerator, Dict, Any, List

from backend.config import settings
from backend.llm_clients import get_grok_reasoning, get_plotly_json
from backend.rag_utils import search_semantic_cache, add_to_semantic_cache
# Correct import for StepInfo from schemas
from backend.schemas import StepInfo

logger = logging.getLogger(__name__)

# Regex to find steps like "## Step 1: ..." or "# Step 1 - ..." etc.
STEP_PATTERN = re.compile(r"^\s*#{1,4}\s*Step\s+(\d+)\s*[:\-–—]\s*(.+)$", re.MULTILINE | re.IGNORECASE)

async def process_user_message(user_message: str, chat_id: str) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Processes a user message through the RAG, Cache, and LLM pipeline.

    Yields:
        Dict[str, Any]: Chunks of the response (text, steps, plot, error, end).
    """
    message_id = uuid.uuid4().hex
    logger.info(f"[{chat_id}][{message_id}] Processing message: '{user_message[:50]}...'")

    # --- 1. Semantic Cache Lookup ---
    try:
        cached_response = await search_semantic_cache(user_message)
        if cached_response:
            logger.info(f"[{chat_id}][{message_id}] Cache hit found. Returning cached response.")
            # Stream out the cached parts
            for part in cached_response:
                # Ensure the base fields are present in cached data
                yield {
                    "type": part.get("type", "unknown"), # Default to unknown if missing
                    "id": message_id, # Use current message ID
                    "chat_id": chat_id,
                    **part # Spread the rest of the cached part (content, steps, plotly_json)
                }
            # Send end-of-stream signal after cached response
            yield {"type": "end", "id": message_id, "chat_id": chat_id}
            return # Stop processing if cache hit
    except Exception as e:
        logger.error(f"[{chat_id}][{message_id}] Error during semantic cache lookup: {e}", exc_info=True)
        # Proceed without cache, maybe yield an internal error later if needed

    # --- 2. RAG Retrieval (Optional - Placeholder) ---
    # rag_context = await search_rag_kb(user_message)
    # combined_prompt = f"Context:\n{rag_context}\n\nQuestion: {user_message}"
    # Use user_message directly for now
    llm_input_messages = [{"role": "user", "content": user_message}]

    # --- 3. LLM Reasoning Call ---
    full_response_text = ""
    response_parts_for_cache: List[Dict[str, Any]] = []

    try:
        grok_resp_data = await get_grok_reasoning(llm_input_messages, effort="medium")

        # --- **MODIFIED HANDLING for empty Grok response** ---
        if not grok_resp_data or not grok_resp_data.get("content"):
            logger.warning(f"[{chat_id}][{message_id}] Grok reasoning returned empty or invalid content.")
            yield {
                "type": "error",
                "id": message_id,
                "chat_id": chat_id,
                "content": "Sorry, I could not generate a reasoned response for that request. Please try rephrasing."
            }
            # Still yield 'end' signal
            yield {"type": "end", "id": message_id, "chat_id": chat_id}
            return # Stop processing if reasoning failed

        full_response_text = grok_resp_data.get("content", "")
        if not full_response_text: # Double check if content became empty somehow
             raise ValueError("Grok response data was present but content was empty.")

        # Yield the main text content
        text_chunk = {"type": "text", "id": message_id, "chat_id": chat_id, "content": full_response_text}
        yield text_chunk
        response_parts_for_cache.append({"type": "text", "content": full_response_text}) # Add to cache list


    except ConnectionError as e:
         logger.error(f"[{chat_id}][{message_id}] Connection error during Grok call: {e}", exc_info=True)
         yield {"type": "error", "id": message_id, "chat_id": chat_id, "content": f"Error communicating with reasoning service: {e}"}
         yield {"type": "end", "id": message_id, "chat_id": chat_id}
         return # Stop processing on connection error
    except Exception as e:
        logger.exception(f"[{chat_id}][{message_id}] Unexpected error during Grok reasoning: {e}")
        yield {"type": "error", "id": message_id, "chat_id": chat_id, "content": "An unexpected error occurred while generating the response."}
        yield {"type": "end", "id": message_id, "chat_id": chat_id}
        return # Stop processing on unexpected error

    # --- 4. Extract Steps from Text ---
    extracted_steps: List[StepInfo] = []
    try:
        for match in STEP_PATTERN.finditer(full_response_text):
            step_num = match.group(1)
            step_title = match.group(2).strip()
            extracted_steps.append({"id": f"step-{step_num}", "title": step_title})

        if extracted_steps:
            logger.info(f"[{chat_id}][{message_id}] Extracted {len(extracted_steps)} steps.")
            steps_chunk = {"type": "steps", "id": message_id, "chat_id": chat_id, "steps": extracted_steps}
            yield steps_chunk
            response_parts_for_cache.append({"type": "steps", "steps": extracted_steps}) # Add to cache list
        else:
             logger.info(f"[{chat_id}][{message_id}] No steps found in the response.")

    except Exception as e:
        logger.error(f"[{chat_id}][{message_id}] Error parsing steps: {e}", exc_info=True)
        # Continue processing, step parsing is non-critical

    # --- 5. Generate Plot if needed ---
    plotly_spec = None
    try:
        # Create conversation context for plotting LLM
        plot_context_messages = [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": full_response_text} # Provide the full reasoning text
        ]
        plotly_spec = await get_plotly_json(plot_context_messages)

        if plotly_spec:
            logger.info(f"[{chat_id}][{message_id}] Plot generated successfully.")
            plot_chunk = {"type": "plot", "id": message_id, "chat_id": chat_id, "plotly_json": plotly_spec}
            yield plot_chunk
            response_parts_for_cache.append({"type": "plot", "plotly_json": plotly_spec}) # Add to cache list
        else:
            logger.info(f"[{chat_id}][{message_id}] No plot needed or generated.")

    except Exception as e:
        logger.error(f"[{chat_id}][{message_id}] Error during plot generation: {e}", exc_info=True)
        # Yield an error specific to plotting? Optional.
        # yield {"type": "error", "id": message_id, "chat_id": chat_id, "content": "Failed to generate plot."}
        # Continue processing without plot

    # --- 6. Cache the Full Response ---
    if response_parts_for_cache: # Only cache if we have something to cache
        try:
            await add_to_semantic_cache(user_message, response_parts_for_cache)
            logger.info(f"[{chat_id}][{message_id}] Response added to semantic cache.")
        except Exception as e:
            logger.error(f"[{chat_id}][{message_id}] Failed to add response to semantic cache: {e}", exc_info=True)
            # Non-fatal error, don't yield to client

    # --- 7. End of Stream ---
    yield {"type": "end", "id": message_id, "chat_id": chat_id}
    logger.info(f"[{chat_id}][{message_id}] Finished processing message.")