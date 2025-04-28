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
from backend.observability import trace  # Ensure import is available

logger = logging.getLogger(__name__)


def _extract_steps(text: Optional[str]) -> List[schemas.StepInfo]:
    """Extract steps marked with '## Step X:' from the text returned by Grok."""
    if not text:
        return []

    steps: List[schemas.StepInfo] = []
    pattern = re.compile(
        r"^\s*#{1,4}\s*Step\s+(\d+)\s*(?:[:\-–—]\s*)?(.*?)\s*$",
        re.MULTILINE | re.IGNORECASE,
    )
    processed_indices = set()

    for match in pattern.finditer(text):
        if any(i in processed_indices for i in range(match.start(), match.end())):
            continue

        step_num_str = match.group(1)
        step_title = match.group(2).strip()
        step_id = f"step-{step_num_str}"

        if step_title and not re.match(
            rf"Step\s+{step_num_str}\s*[:\-–—]", step_title, re.IGNORECASE
        ):
            display_title = f"Step {step_num_str}: {step_title}"
        elif step_title:
            display_title = step_title
        else:
            display_title = f"Step {step_num_str}"

        steps.append(schemas.StepInfo(id=step_id, title=display_title))
        processed_indices.update(range(match.start(), match.end()))

    if not steps:
        logger.debug("Did not find '## Step X:' markers in LLM response.")
    else:
        logger.info("Extracted %d steps based on '## Step X:' markers.", len(steps))

    return steps


async def _decide_plot_needed(query: str, reasoning_and_answer: Optional[str]) -> bool:
    """Heuristic check to determine if a plot might be relevant."""
    if not reasoning_and_answer:
        return False

    text_to_check = (query + " " + reasoning_and_answer).lower()
    strong_keywords = ["plot", "graph", "visualize", "chart", "draw"]
    if any(keyword in text_to_check for keyword in strong_keywords):
        logger.info("Strong plot keyword detected.")
        return True

    relation_keywords = ["versus", " vs ", "relationship between", "function of", "over time"]
    if any(keyword in text_to_check for keyword in relation_keywords):
        logger.info("Relationship/function keyword detected.")
        return True

    if (
        re.search(r'([yY]|f\(x\))\s*=', reasoning_and_answer)
        or re.search(r'\(\s*[\d.\-+]+\s*,\s*[\d.\-+]+\s*\)', reasoning_and_answer)
    ):
        logger.info("Function definition or data points detected.")
        return True

    logger.debug("No strong indicators for plotting found.")
    return False


async def process_user_message(user_message: str, websocket) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Pipeline:
        1. Check semantic cache.
        2. RAG retrieval.
        3. Reasoning LLM (Grok).
        4. Stream text to UI.
        5. Extract steps.
        6. Decide if a plot is needed -> Plotting LLM.
        7. Stream plot (if any).
        8. Send end message.
        9. Cache successful response.
    """
    message_stream_id = uuid.uuid4().hex
    logger.info("[ID: %s] Processing message: '%s...'", message_stream_id, user_message[:100])

    final_response_parts_for_cache: List[Dict[str, Any]] = []
    plotly_json_data: Optional[Dict[str, Any]] = None

    try:
        # 1. Semantic Cache
        cached_response_list = await rag_utils.search_semantic_cache(user_message)
        if cached_response_list:
            logger.info("[ID: %s] Cache hit! Streaming cached response.", message_stream_id)
            for cached_part in cached_response_list:
                part_copy = cached_part.copy()
                part_copy["id"] = message_stream_id
                yield part_copy
            yield schemas.EndMessage(id=message_stream_id).model_dump()
            logger.info("[ID: %s] Finished streaming cached response.", message_stream_id)
            return

        # 2. RAG – instrument the retrieval stage
        @trace("rag_context")  # NEW
        async def retrieve_rag_context(query: str):
            return await rag_utils.search_rag_kb(query)
        rag_contexts = await retrieve_rag_context(user_message)
        formatted_rag_context = ""
        if rag_contexts:
            formatted_rag_context = "Relevant Context:\n" + "\n\n---\n\n".join(
                f"Document {i + 1}:\n{context}" for i, context in enumerate(rag_contexts)
            )
            max_context_chars = 3800
            if len(formatted_rag_context) > max_context_chars:
                formatted_rag_context = (
                    formatted_rag_context[:max_context_chars] + "\n... (context truncated)"
                )
            logger.info(
                "[ID: %s] RAG context retrieved (%d docs, %d chars).",
                message_stream_id,
                len(rag_contexts),
                len(formatted_rag_context),
            )
        else:
            logger.info("[ID: %s] No relevant context found via RAG.", message_stream_id)

        # 3. Prepare messages for Grok
        system_prompt = (
            "You are GrokSTEM, an expert AI assistant specializing in Science, "
            "Technology, Engineering, and Mathematics (STEM). Your primary goal is to "
            "provide clear, accurate, and step-by-step reasoning to help users understand "
            "complex problems.\n\n"
            "Instructions:\n"
            "1. Analyze the user's question carefully.\n"
            "2. If relevant context is provided below under \"Relevant Context:\", integrate "
            "it naturally into your explanation. If no context is provided, rely solely on "
            "your internal knowledge.\n"
            "3. Structure your response logically. Start with a brief restatement or "
            "clarification of the problem if helpful.\n"
            "4. Break down the solution into numbered steps. Each step MUST start exactly on "
            "a new line with the format `## Step X: Title`, where X is the step number "
            "(1, 2, 3...) and Title is a concise description of that step.\n"
            "5. Within each step, explain the concepts, formulas, and calculations clearly "
            "and concisely.\n"
            "6. Use Markdown for formatting.\n"
            "7. After all steps, provide a concluding summary or the final answer.\n"
            "8. If the question is ambiguous or cannot be answered reliably, state this "
            "clearly and explain why.\n"
            "9. Ensure the response is well‑organized and easy to follow."
        )

        messages_for_grok: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
        if formatted_rag_context:
            messages_for_grok.append({"role": "system", "content": formatted_rag_context})
        messages_for_grok.append({"role": "user", "content": user_message})

        # 4. Call Reasoning LLM
        logger.info(
            "[ID: %s] Calling Grok reasoning model (%s)...",
            message_stream_id,
            settings.REASONING_MODEL_NAME,
        )
        grok_response_dict = await llm_clients.get_grok_reasoning(
            messages_for_grok, effort="medium"
        )
        full_response_text = grok_response_dict.get("content", "").strip()
        if not full_response_text:
            raise ValueError("Reasoning model returned empty content.")

        final_response_parts_for_cache.append(
            schemas.TextChunk(id=message_stream_id, content=full_response_text).model_dump(
                exclude_none=True
            )
        )

        # 5. Stream text paragraph by paragraph
        paragraphs = full_response_text.split("\n\n")
        accumulated_text = ""
        for i, paragraph in enumerate(paragraphs):
            trimmed = paragraph.strip()
            if not trimmed:
                continue
            chunk_content = trimmed + ("\n\n" if i < len(paragraphs) - 1 else "")
            accumulated_text += chunk_content
            yield schemas.TextChunk(id=message_stream_id, content=chunk_content).model_dump()
            await asyncio.sleep(0.05)

        # 6. Extract and stream steps
        steps = _extract_steps(accumulated_text)
        if steps:
            steps_msg = schemas.StepsList(id=message_stream_id, steps=steps)
            yield steps_msg.model_dump()
            final_response_parts_for_cache.append(steps_msg.model_dump(exclude_none=True))

        # 7. Plot generation
        if await _decide_plot_needed(user_message, accumulated_text):
            logger.info("[ID: %s] Plot deemed potentially necessary.", message_stream_id)
            plot_prompt = f"""
Analyze the following STEM problem and its reasoning/solution context. Your task is to generate a Plotly
JSON object for a relevant and informative plot IF AND ONLY IF the context provides sufficient data or a
clearly defined mathematical function suitable for visualization.

Problem:
{user_message}

Reasoning/Solution Context:
{accumulated_text[:3000]}
(Context is truncated if too long)

Instructions:
1. Feasibility Check: determine if a plot can and should be generated based *only* on the provided
   problem and context.
2. Response Format:
   - If no plot is appropriate: respond with ONLY the exact text `NO_PLOT`.
   - If a plot is possible: output ONLY the Plotly JSON object (starting with `{{` and ending with `}}`).
3. Plotly JSON Requirements:
   - Must contain `data` and `layout` keys.
   - Choose an appropriate plot type; default to scatter lines+markers if unsure.
   - Label axes and title clearly.
""".strip()
            plot_messages = [{"role": "user", "content": plot_prompt}]
            logger.info(
                "[ID: %s] Calling plotting model (%s)...",
                message_stream_id,
                settings.PLOTTING_MODEL_NAME,
            )
            plotly_json_data = await llm_clients.get_plotly_json(plot_messages)

        if plotly_json_data and isinstance(plotly_json_data, dict):
            plot_msg = schemas.PlotData(id=message_stream_id, plotly_json=plotly_json_data)
            yield plot_msg.model_dump()
            final_response_parts_for_cache.append(plot_msg.model_dump(exclude_none=True))
            logger.info("[ID: %s] Plot JSON generated and yielded.", message_stream_id)
        else:
            logger.info("[ID: %s] No valid plot generated.", message_stream_id)

        # 8. Send End Message
        logger.info("[ID: %s] Sending end message.", message_stream_id)
        yield schemas.EndMessage(id=message_stream_id).model_dump()

        # 9. Add successful result to cache
        if final_response_parts_for_cache:
            logger.info(
                "[ID: %s] Adding response (%d parts) to semantic cache.",
                message_stream_id,
                len(final_response_parts_for_cache),
            )
            await rag_utils.add_to_semantic_cache(user_message, final_response_parts_for_cache)
        else:
            logger.warning(
                "[ID: %s] No response parts generated, skipping caching.",
                message_stream_id,
            )

    except ConnectionError as e:
        error_content = (
            f"Connection error: Could not connect to required service. Please try again later. ({e})"
        )
        logger.error(f"[ID: {message_stream_id}] {error_content}", exc_info=False)
        yield schemas.ErrorMessage(id=message_stream_id, content=error_content).model_dump()
        yield schemas.EndMessage(id=message_stream_id).model_dump()

    except ValueError as e:
        error_content = f"Processing error: {e}"
        logger.error(f"[ID: {message_stream_id}] {error_content}", exc_info=True)
        yield schemas.ErrorMessage(id=message_stream_id, content=error_content).model_dump()
        yield schemas.EndMessage(id=message_stream_id).model_dump()

    except Exception as e:
        error_content = "An unexpected internal error occurred while processing your request."
        logger.error(f"[ID: {message_stream_id}] Unexpected error: {e}", exc_info=True)
        yield schemas.ErrorMessage(id=message_stream_id, content=error_content).model_dump()
        yield schemas.EndMessage(id=message_stream_id).model_dump()

    finally:
        logger.info(f"[ID: {message_stream_id}] Processing complete.")



