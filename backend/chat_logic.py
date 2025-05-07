# backend/chat_logic.py
import logging
import uuid
import re
import json
import asyncio # Import asyncio
from typing import AsyncGenerator, Dict, Any, List, Optional # Import Optional

from backend.config import settings
from backend.llm_clients import (
    get_grok_reasoning,
    get_plotly_json,
    generate_image_from_prompt, # NEW import
)
from backend.rag_utils import (
    search_semantic_cache,
    add_to_semantic_cache,
    search_rag_kb,
    search_image_cache, # NEW import
    add_to_image_cache  # NEW import
)
from backend.schemas import StepInfo # Import specific types if needed

logger = logging.getLogger(__name__)

# Regex to find steps like "## Step 1: ..."
STEP_PATTERN = re.compile(r"^\s*#{1,4}\s*Step\s+(\d+)\s*[:\-–—]\s*(.+)$", re.MULTILINE | re.IGNORECASE)
# NEW Regex to find and extract image request marker
IMAGE_REQUEST_PATTERN = re.compile(r"^\s*\[REQUEST_IMAGE:\s*<<<(.+?)>>>\s*\]\s*$", re.MULTILINE | re.DOTALL)

# --- NEW: Helper for Image Generation Flow ---
async def handle_image_generation(
    image_prompt: str,
    message_id: str,
    chat_id: str
) -> AsyncGenerator[Dict[str, Any], None]:
    """Handles image caching, generation with retries, and yielding results."""
    if not image_prompt:
        logger.warning(f"[{chat_id}][{message_id}] Image generation requested but prompt is empty.")
        return

    logger.info(f"[{chat_id}][{message_id}] Handling image generation for prompt: '{image_prompt[:50]}...'")
    yield {"type": "progress", "phase": "image_generation", "id": message_id, "chat_id": chat_id}

    try:
        # 1. Check cache
        cached_url = await search_image_cache(image_prompt)
        if cached_url:
            logger.info(f"[{chat_id}][{message_id}] Found cached image: {cached_url}")
            yield {"type": "image", "image_url": cached_url, "id": message_id, "chat_id": chat_id}
            return # Found in cache, we are done

        # 2. Generate if not cached (with retries)
        logger.info(f"[{chat_id}][{message_id}] No cached image found. Generating new image...")
        retry_count = 0
        max_retries = 3
        image_url: Optional[str] = None

        while retry_count < max_retries and not image_url:
            if retry_count > 0:
                logger.info(f"[{chat_id}][{message_id}] Retrying image generation (Attempt {retry_count + 1}/{max_retries})")
                yield {"type": "image_retry", "attempt": retry_count + 1, "max_attempts": max_retries, "id": message_id, "chat_id": chat_id}
                await asyncio.sleep(1.5) # Small delay before retry

            generated_url = await generate_image_from_prompt(image_prompt)

            if generated_url:
                image_url = generated_url
                logger.info(f"[{chat_id}][{message_id}] Image generated successfully: {image_url}")
                # Add to cache (fire and forget)
                asyncio.create_task(
                    add_to_image_cache(image_prompt, image_url, generating_model=settings.IMAGE_MODEL_NAME)
                )
                # Yield success
                yield {"type": "image", "image_url": image_url, "id": message_id, "chat_id": chat_id}
                break # Exit loop on success
            else:
                retry_count += 1
                logger.warning(f"[{chat_id}][{message_id}] Image generation attempt {retry_count} failed.")

        # 3. Handle final failure after retries
        if not image_url:
            logger.error(f"[{chat_id}][{message_id}] Image generation failed after {max_retries} attempts.")
            yield {"type": "image_error", "content": f"Sorry, no image could be generated after {max_retries} attempts.", "id": message_id, "chat_id": chat_id}

    except Exception as e:
        logger.error(f"[{chat_id}][{message_id}] Unexpected error during image handling: {e}", exc_info=True)
        # Yield a generic error if something unexpected happened during the process
        yield {"type": "image_error", "content": "An unexpected error occurred during image generation.", "id": message_id, "chat_id": chat_id}


# --- Main Message Processing Function ---
async def process_user_message(user_message: str, chat_id: str, original_message_id: Optional[str] = None) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Processes a user message through the RAG, Cache, and LLM pipeline.
    Yields chunks of the response (progress, text, steps, plot, image, error, end).
    """
    # Use provided message ID if available (for user-triggered actions), else generate new
    message_id = original_message_id or uuid.uuid4().hex
    logger.info(f"[{chat_id}][{message_id}] Processing message: '{user_message[:50]}...'")

    # Keep track of the full response for caching
    response_parts_for_cache: List[Dict[str, Any]] = []

    # --- 1. Semantic Cache Lookup ---
    yield {"type": "progress", "phase": "cache_check", "id": message_id, "chat_id": chat_id}
    try:
        cached_response = await search_semantic_cache(user_message)
        if cached_response:
            logger.info(f"[{chat_id}][{message_id}] Semantic cache hit found. Returning cached response.")
            for part in cached_response:
                # Add IDs back for consistency before yielding
                yield {"id": message_id, "chat_id": chat_id, **part}
            yield {"type": "end", "id": message_id, "chat_id": chat_id}
            return
    except Exception as e:
        logger.error(f"[{chat_id}][{message_id}] Error during semantic cache lookup: {e}", exc_info=True)

    # --- 2. RAG Retrieval ---
    logger.info(f"[{chat_id}][{message_id}] Cache miss. Performing RAG search...")
    yield {"type": "progress", "phase": "retrieval", "id": message_id, "chat_id": chat_id}
    contexts = []
    context_str = "No relevant context found."
    final_prompt_content = "" # Initialize

    try:
        contexts = await search_rag_kb(user_message)
        if contexts:
            logger.info(f"[{chat_id}][{message_id}] RAG search retrieved {len(contexts)} contexts.")
            formatted_contexts = [f"Context Document {i+1}:\n{ctx}" for i, ctx in enumerate(contexts)]
            context_str = "\n\n---\n\n".join(formatted_contexts)
        else:
            logger.info(f"[{chat_id}][{message_id}] RAG search found no relevant contexts.")

    except Exception as e:
        logger.error(f"[{chat_id}][{message_id}] Error during RAG search: {e}", exc_info=True)
        context_str = "Error retrieving context."

    # Construct the final prompt including RAG context and image request instruction
    final_prompt_content = f"""You are a helpful STEM assistant. Use the following context, if relevant, to answer the user's question accurately and provide step-by-step reasoning. Ensure steps are clearly marked like '## Step 1: Title'.

    If you determine that a visual illustration (that is not a plottable graph) would significantly aid understanding based on your reasoning, include a special marker at the VERY END of your response on its own line: `[REQUEST_IMAGE: <<<Detailed prompt for the image generation model goes here>>>]`. Do *not* mention this marker instruction in your user-facing text. Base the image prompt on the core visual concept.

    Provided Context:
    ---
    {context_str}
    ---

    User's Question:
    {user_message}

    Answer:"""

    # --- 3. LLM Reasoning Call ---
    yield {"type": "progress", "phase": "reasoning", "id": message_id, "chat_id": chat_id}
    full_response_text = ""
    grok_image_prompt: Optional[str] = None

    try:
        grok_resp_data = await get_grok_reasoning([{"role": "user", "content": final_prompt_content}], effort="medium")

        if not grok_resp_data or not grok_resp_data.get("content"):
            logger.warning(f"[{chat_id}][{message_id}] Grok reasoning returned empty content.")
            yield {"type": "error", "id": message_id, "chat_id": chat_id, "content": "Sorry, I could not generate a reasoned response."}
            yield {"type": "end", "id": message_id, "chat_id": chat_id}
            return

        raw_response_text = grok_resp_data.get("content", "")

        # Check for and extract image request marker
        image_match = IMAGE_REQUEST_PATTERN.search(raw_response_text)
        if image_match:
            grok_image_prompt = image_match.group(1).strip()
            logger.info(f"[{chat_id}][{message_id}] Grok requested image generation with prompt: '{grok_image_prompt[:50]}...'")
            # Remove the marker from the text sent to the user
            full_response_text = IMAGE_REQUEST_PATTERN.sub("", raw_response_text).strip()
        else:
            full_response_text = raw_response_text.strip() # No marker found

        # Stream text chunk
        if full_response_text:
             text_chunk = {"type": "text", "content": full_response_text}
             yield {**text_chunk, "id": message_id, "chat_id": chat_id}
             response_parts_for_cache.append(text_chunk)
        elif not grok_image_prompt: # If response is empty AND no image was requested, it's likely an issue
             logger.warning(f"[{chat_id}][{message_id}] Grok response empty after potential marker removal.")
             # Optionally yield an error or just proceed

    except Exception as e:
        logger.exception(f"[{chat_id}][{message_id}] Error during Grok reasoning: {e}")
        yield {"type": "error", "id": message_id, "chat_id": chat_id, "content": "An error occurred while generating the response."}
        yield {"type": "end", "id": message_id, "chat_id": chat_id}
        return

    # --- 4. Extract Steps ---
    yield {"type": "progress", "phase": "steps", "id": message_id, "chat_id": chat_id}
    extracted_steps: List[StepInfo] = []
    try:
        # Use the potentially cleaned full_response_text
        for match in STEP_PATTERN.finditer(full_response_text):
            step_num_str = match.group(1)
            step_title = match.group(2).strip()
            try:
                step_num = int(step_num_str)
                extracted_steps.append({"id": f"step-{step_num}", "title": step_title})
            except ValueError:
                 logger.warning(f"[{chat_id}][{message_id}] Could not parse step number: {step_num_str}")

        if extracted_steps:
            steps_chunk = {"type": "steps", "steps": extracted_steps}
            yield {**steps_chunk, "id": message_id, "chat_id": chat_id}
            response_parts_for_cache.append(steps_chunk)
    except Exception as e:
        logger.error(f"[{chat_id}][{message_id}] Error parsing steps: {e}", exc_info=True)

    # --- 5. Plot Generation ---
    yield {"type": "progress", "phase": "plotting", "id": message_id, "chat_id": chat_id}
    plot_prompt_messages = [
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": full_response_text}
    ]
    try:
        plotly_spec = await get_plotly_json(plot_prompt_messages)
        if plotly_spec:
            plot_chunk = {"type": "plot", "plotly_json": plotly_spec}
            yield {**plot_chunk, "id": message_id, "chat_id": chat_id}
            response_parts_for_cache.append(plot_chunk)
    except Exception as e:
        logger.error(f"[{chat_id}][{message_id}] Error generating plot: {e}", exc_info=True)

    # --- 6. Image Generation (If Grok Requested) ---
    if grok_image_prompt:
        # Use the helper function to handle generation, caching, and yielding
        async for image_chunk in handle_image_generation(grok_image_prompt, message_id, chat_id):
            # Add the image URL to the cache list if successful
            if image_chunk.get("type") == "image":
                 # Cache the prompt used and the resulting URL
                 response_parts_for_cache.append({
                     "type": "image",
                     "image_url": image_chunk["image_url"],
                     "image_prompt": grok_image_prompt # Store prompt for context
                 })
            yield image_chunk # Forward the chunk (image, retry, or error)

    # --- 7. Cache Final Response ---
    # Only cache if there was some meaningful content generated
    if response_parts_for_cache:
        try:
            # Cache based on the *original* user message
            await add_to_semantic_cache(user_message, response_parts_for_cache)
        except Exception as e:
            logger.error(f"[{chat_id}][{message_id}] Failed to cache response: {e}", exc_info=True)

    # Finalize
    yield {"type": "end", "id": message_id, "chat_id": chat_id}
    logger.info(f"[{chat_id}][{message_id}] Completed processing for message.")