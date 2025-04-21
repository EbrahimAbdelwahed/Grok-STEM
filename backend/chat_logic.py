import logging
import uuid
import json
import re
import asyncio
from typing import List, Dict, Any, AsyncGenerator, Optional

# Import clients, settings, schemas, and utils
from config import settings
import schemas
import llm_clients
import rag_utils

logger = logging.getLogger(__name__)

# --- Helper Functions ---

def _extract_steps(text: Optional[str]) -> List[schemas.StepInfo]:
    """Extracts steps marked with '## Step X:' from the text."""
    if not text:
        return []
    steps = []
    # More robust pattern: allows optional punctuation after number, captures title until newline
    # Handles potential whitespace variations. Uses non-capturing group for optional colon/hyphen.
    pattern = re.compile(r"^\s*#{1,4}\s*Step\s+(\d+)\s*(?:[:\-–—]\s*)?(.*?)\s*$", re.MULTILINE | re.IGNORECASE)
    found_steps = False
    processed_indices = set() # Avoid double-counting overlapping matches if pattern allows

    for match in pattern.finditer(text):
        # Check if this match starts within an already processed range
        if any(i in processed_indices for i in range(match.start(), match.end())):
            continue

        found_steps = True
        step_num_str = match.group(1)
        step_title = match.group(2).strip()
        step_id = f"step-{step_num_str}" # Consistent ID format

        # Create display title: If title doesn't start with Step X, prepend it.
        if step_title and not re.match(rf"Step\s+{step_num_str}\s*[:\-–—]", step_title, re.IGNORECASE):
            display_title = f"Step {step_num_str}: {step_title}"
        elif step_title:
            display_title = step_title # Title already includes "Step X:" correctly
        else:
            display_title = f"Step {step_num_str}" # Fallback if title is somehow empty

        steps.append(schemas.StepInfo(id=step_id, title=display_title))

        # Mark indices as processed
        for i in range(match.start(), match.end()):
            processed_indices.add(i)

    if not found_steps:
        logger.debug("Did not find '## Step X:' markers in LLM response.")
    else:
        logger.info(f"Extracted {len(steps)} steps based on '## Step X:' markers.")
    return steps


async def _decide_plot_needed(query: str, reasoning_and_answer: Optional[str]) -> bool:
    """Heuristic check to determine if a plot might be relevant."""
    if not reasoning_and_answer:
        return False

    text_to_check = (query + " " + reasoning_and_answer).lower()

    # Keywords strongly suggesting a plot
    strong_keywords = ["plot", "graph", "visualize", "chart", "draw"]
    if any(keyword in text_to_check for keyword in strong_keywords):
        logger.info("Strong plot keyword detected.")
        return True

    # Keywords suggesting relationships or functions
    relation_keywords = ["versus", " vs ", "relationship between", "function of", "over time"]
    if any(keyword in text_to_check for keyword in relation_keywords):
        logger.info("Relationship/function keyword detected.")
        return True

    # Patterns suggesting mathematical functions or data points
    # Looks for y=..., f(x)=... or coordinate pairs like (1, 2), (3.1, -4.5)
    if re.search(r'([yY]|f\(x\))\s*=', reasoning_and_answer) or \
       re.search(r'\(\s*[\d.\-+]+\s*,\s*[\d.\-+]+\s*\)', reasoning_and_answer):
        logger.info("Function definition or data points detected.")
        return True

    # Add more sophisticated checks if needed (e.g., NLP analysis)
    logger.debug("No strong indicators for plotting found.")
    return False

# --- Main Processing Function ---

async def process_user_message(user_message: str, websocket) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Processes a user message: Cache check -> RAG -> Reasoning LLM -> Plot LLM -> Stream response.
    Yields structured messages (text, steps, plot, end, error) via WebSocket.
    """
    message_stream_id = uuid.uuid4().hex
    logger.info(f"[ID: {message_stream_id}] Processing message: '{user_message[:100]}...'")

    # Accumulate response parts for caching at the end
    final_response_parts_for_cache: List[Dict[str, Any]] = []

    try:
        # 1. Check Semantic Cache
        logger.debug(f"[ID: {message_stream_id}] Checking semantic cache.")
        cached_response_list = await rag_utils.search_semantic_cache(user_message)
        if cached_response_list:
            logger.info(f"[ID: {message_stream_id}] Cache hit! Streaming {len(cached_response_list)} cached parts.")
            for cached_part in cached_response_list:
                 # Ensure the message ID is updated for the current stream
                 part_copy = cached_part.copy()
                 part_copy['id'] = message_stream_id
                 yield part_copy
            # Yield the final end message for the cached stream
            yield schemas.EndMessage(id=message_stream_id).model_dump()
            logger.info(f"[ID: {message_stream_id}] Finished streaming cached response.")
            return # Exit processing early

        logger.info(f"[ID: {message_stream_id}] Cache miss. Generating new response.")

        # 2. RAG - Retrieve Context
        logger.debug(f"[ID: {message_stream_id}] Performing RAG search.")
        rag_contexts = await rag_utils.search_rag_kb(user_message)
        # Format context clearly for the LLM
        formatted_rag_context = ""
        if rag_contexts:
            formatted_rag_context = "Relevant Context:\n" + "\n\n---\n\n".join(
                f"Document {i+1}:\n{context}" for i, context in enumerate(rag_contexts)
            )
            # Limit context length to avoid exceeding LLM limits (adjust as needed)
            max_context_chars = 3800
            if len(formatted_rag_context) > max_context_chars:
                formatted_rag_context = formatted_rag_context[:max_context_chars] + "\n... (context truncated)"
            logger.info(f"[ID: {message_stream_id}] RAG context retrieved ({len(rag_contexts)} docs, {len(formatted_rag_context)} chars).")
        else:
            logger.info(f"[ID: {message_stream_id}] No relevant context found via RAG.")

        # 3. Prepare messages for Reasoning LLM (Grok)
        # Refined system prompt for clarity and structure enforcement
        system_prompt = """You are GrokSTEM, an expert AI assistant specializing in Science, Technology, Engineering, and Mathematics (STEM). Your primary goal is to provide clear, accurate, and step-by-step reasoning to help users understand complex problems.

Instructions:
1.  Analyze the user's question carefully.
2.  If relevant context is provided below under "Relevant Context:", integrate it naturally into your explanation. If no context is provided, rely solely on your internal knowledge.
3.  Structure your response logically. Start with a brief restatement or clarification of the problem if helpful.
4.  Break down the solution into **numbered steps**. Each step **MUST** start *exactly* on a new line with the format `## Step X: Title`, where X is the step number (1, 2, 3...) and Title is a concise description of that step (e.g., `## Step 1: Identify Given Variables`, `## Step 2: Apply Formula Y`).
5.  Within each step, explain the concepts, formulas, and calculations clearly and concisely. Define variables and state any assumptions made.
6.  Use Markdown for formatting:
    *   Use **bold** for emphasis.
    *   Use `inline code` for variables or brief code snippets.
    *   Use code blocks (```) for multi-line code or detailed formulas if necessary.
    *   Use LaTeX notation within single dollar signs (`$...$`) for inline math (e.g., `$E = mc^2$`) and double dollar signs (`$$...$$`) for block math equations.
7.  After all steps, provide a **concluding summary** or the final answer, clearly addressing the user's original question.
8.  If the question is ambiguous, outside your STEM expertise, or cannot be answered reliably, state this clearly and explain why. Do not invent information.
9.  Ensure the response is well-organized and easy to follow. Use paragraphs effectively.
"""
        messages_for_grok = [{"role": "system", "content": system_prompt}]
        if formatted_rag_context:
             # Add context as a separate system message for clarity
             messages_for_grok.append({"role": "system", "content": formatted_rag_context})
        messages_for_grok.append({"role": "user", "content": user_message})

        # 4. Call Reasoning LLM (Grok)
        logger.info(f"[ID: {message_stream_id}] Calling Grok for reasoning (model: {settings.REASONING_MODEL_NAME})...")
        # TODO: Add reasoning_effort selection if UI implements it
        grok_response_dict = await llm_clients.get_grok_reasoning(messages_for_grok, effort="medium")

        # --- Process Grok Response ---
        # Expecting the full formatted text in the 'content' field based on OpenAI SDK structure
        full_response_text = grok_response_dict.get("content")

        if not full_response_text or not full_response_text.strip():
             logger.error(f"[ID: {message_stream_id}] Grok response missing or empty 'content'. Full response dict: {grok_response_dict}")
             raise ValueError("Reasoning model returned empty content.")

        logger.info(f"[ID: {message_stream_id}] Grok response received ({len(full_response_text)} chars).")
        final_response_parts_for_cache.append(schemas.TextChunk(id=message_stream_id, content=full_response_text).model_dump(exclude_none=True))


        # 5. Stream Text Content (Paragraph by Paragraph)
        logger.debug(f"[ID: {message_stream_id}] Streaming text content...")
        paragraphs = full_response_text.split('\n\n')
        accumulated_text = ""
        for i, paragraph in enumerate(paragraphs):
            trimmed_paragraph = paragraph.strip()
            if trimmed_paragraph:
                # Add back double newline for separation, except for the last paragraph
                chunk_content = trimmed_paragraph + ("\n\n" if i < len(paragraphs) - 1 else "")
                accumulated_text += chunk_content # Keep track for step extraction later
                text_chunk_msg = schemas.TextChunk(id=message_stream_id, content=chunk_content)
                yield text_chunk_msg.model_dump()
                await asyncio.sleep(0.05) # Small delay for smoother streaming perception

        # 6. Extract and Send Steps (from the full accumulated text)
        logger.debug(f"[ID: {message_stream_id}] Extracting steps from full text...")
        steps = _extract_steps(accumulated_text) # Use the re-assembled text
        if steps:
            logger.info(f"[ID: {message_stream_id}] Found {len(steps)} steps. Yielding steps list.")
            steps_list_msg = schemas.StepsList(id=message_stream_id, steps=steps)
            yield steps_list_msg.model_dump()
            final_response_parts_for_cache.append(steps_list_msg.model_dump(exclude_none=True)) # Add steps to cache list

        # 7. Generate and Send Plot (if needed)
        logger.debug(f"[ID: {message_stream_id}] Checking if plot is needed...")
        if await _decide_plot_needed(user_message, accumulated_text):
            logger.info(f"[ID: {message_stream_id}] Plot potentially needed. Preparing plot prompt...")
            # Refined plot prompt
            plot_prompt = f"""Analyze the following STEM problem and its reasoning/solution context. Your task is to generate a Plotly JSON object for a relevant and informative plot IF AND ONLY IF the context provides sufficient data or a clearly defined mathematical function suitable for visualization.

**Problem:**
{user_message}

**Reasoning/Solution Context:**
{accumulated_text[:3000]}
(Context is truncated if too long)

**Instructions:**

1.  **Feasibility Check:** First, critically assess if a meaningful plot *can and should* be generated based *only* on the provided Problem and Context. Consider:
    *   Is there explicit numerical data (e.g., lists of numbers, table data)?
    *   Is a specific mathematical function clearly defined (e.g., y = ..., f(x) = ...)?
    *   Is a standard plot type implied (e.g., "plot X vs Y", "show the trend")?
    *   Is there enough information to define axes and trace data?
2.  **Response Format:**
    *   **If NO PLOT is possible or appropriate:** Respond with ONLY the exact text `NO_PLOT`. Do not include any other text, explanation, or formatting.
    *   **If a PLOT IS possible:** Output ONLY the Plotly JSON object. It MUST start with `{{` and end with `}}`. Do not include ```json code fences or any other text.
3.  **Plotly JSON Requirements (if generating plot):**
    *   The JSON MUST contain `data` (an array, usually with one trace object) and `layout` objects.
    *   Choose an appropriate plot type (e.g., `scatter`, `line`, `bar`). Default to `scatter` with `mode: 'lines+markers'` if unsure.
    *   Infer data points if a function and range are clearly implied (e.g., plot y=sin(x) from -pi to pi). Use a reasonable number of points (e.g., 50-100).
    *   Label axes clearly (`xaxis.title`, `yaxis.title`).
    *   Provide a concise and relevant plot title (`layout.title`).
    *   Ensure data traces have appropriate keys (e.g., `x`, `y`, `type`).

**Example JSON Structure:**
```json
{{
  "data": [{{ "x": [1, 2, 3], "y": [2, 4, 9], "type": "scatter", "mode": "lines+markers", "name": "Example" }}],
  "layout": {{ "title": "Example Plot", "xaxis": {{"title": "X Axis"}}, "yaxis": {{"title": "Y Axis"}} }}
}}
"""
plot_messages = [{"role": "user", "content": plot_prompt}]

        logger.info(f"[ID: {message_stream_id}] Calling plotting model ({settings.PLOTTING_MODEL_NAME})...")
        plotly_json_data = await llm_clients.get_plotly_json(plot_messages)

        if plotly_json_data:
            plot_msg = schemas.PlotData(id=message_stream_id, plotly_json=plotly_json_data)
            yield plot_msg.model_dump()
            final_response_parts_for_cache.append(plot_msg.model_dump(exclude_none=True)) # Add plot to cache list
            logger.info(f"[ID: {message_stream_id}] Plot JSON generated and yielded.")
        else:
             logger.info(f"[ID: {message_stream_id}] Plotting LLM indicated no plot possible or returned invalid data.")
    else:
         logger.debug(f"[ID: {message_stream_id}] Plot not deemed necessary.")

    # 8. Send End Message
    logger.info(f"[ID: {message_stream_id}] Sending end message.")
    yield schemas.EndMessage(id=message_stream_id).model_dump()

    # 9. Add successful result to cache
    if final_response_parts_for_cache:
        logger.info(f"[ID: {message_stream_id}] Adding response ({len(final_response_parts_for_cache)} parts) to semantic cache.")
        await rag_utils.add_to_semantic_cache(user_message, final_response_parts_for_cache)
    else:
        logger.warning(f"[ID: {message_stream_id}] No response parts generated, skipping caching.")

# --- Exception Handling ---
except ConnectionError as e:
     # Handles LLM/Qdrant connection issues raised from helpers
     error_content = f"Connection error: Could not connect to required service. Please try again later. ({e})"
     logger.error(f"[ID: {message_stream_id}] {error_content}", exc_info=False) # Don't need full trace for simple connection errors
     yield schemas.ErrorMessage(id=message_stream_id, content=error_content).model_dump()
     yield schemas.EndMessage(id=message_stream_id).model_dump()
except ValueError as e:
     # Handles specific value errors (e.g., empty LLM response)
     error_content = f"Processing error: {e}"
     logger.error(f"[ID: {message_stream_id}] {error_content}", exc_info=True) # Include trace for value errors
     yield schemas.ErrorMessage(id=message_stream_id, content=error_content).model_dump()
     yield schemas.EndMessage(id=message_stream_id).model_dump()
except Exception as e:
    # Catch-all for unexpected errors
    error_content = "An unexpected internal error occurred while processing your request."
    logger.error(f"[ID: {message_stream_id}] Unexpected error: {e}", exc_info=True)
    yield schemas.ErrorMessage(id=message_stream_id, content=error_content).model_dump()
    yield schemas.EndMessage(id=message_stream_id).model_dump()
finally:
    # Ensure logger indicates processing completion for this stream ID, regardless of outcome
    logger.info(f"[ID: {message_stream_id}] Processing complete.")

    