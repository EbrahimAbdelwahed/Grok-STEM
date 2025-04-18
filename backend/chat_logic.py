# backend/chat_logic.py

import logging
import uuid
import json
import re
import asyncio
from typing import List, Dict, Any, AsyncGenerator, Optional

# Import clients, settings, schemas, and utils
import config
import schemas
import llm_clients
import rag_utils

logger = logging.getLogger(__name__)

# --- Helper Functions (Keep _extract_steps and _decide_plot_needed as before) ---

def _extract_steps(text: Optional[str]) -> List[schemas.StepInfo]:
    if not text: return []
    steps = []
    pattern = re.compile(r"^\s*#{1,4}\s*Step\s+(\d+)\s*[:\-]?\s*(.*?)\s*$", re.MULTILINE | re.IGNORECASE)
    matches = pattern.finditer(text)
    found_steps = False
    processed_indices = set()
    for match in matches:
        if match.start() in processed_indices: continue
        found_steps = True
        step_num = match.group(1)
        step_title = match.group(2).strip()
        step_id = f"step-{step_num}"
        if step_title:
             display_title = step_title if step_title.lower().startswith("step") else f"Step {step_num}: {step_title}"
             steps.append(schemas.StepInfo(id=step_id, title=display_title))
        else:
             steps.append(schemas.StepInfo(id=step_id, title=f"Step {step_num}"))
        for i in range(match.start(), match.end()): processed_indices.add(i)
    if not found_steps: logger.debug("Did not find 'Step X:' markers in LLM response.")
    else: logger.info(f"Extracted {len(steps)} steps based on 'Step X:' markers.")
    return steps

async def _decide_plot_needed(query: str, reasoning_and_answer: Optional[str]) -> bool:
    if not reasoning_and_answer: return False
    keywords = ["plot", "graph", "visualize", "chart", "versus", " vs. ", "relationship between", "function of"]
    text_to_check = query.lower() + " " + reasoning_and_answer.lower()
    if any(keyword in text_to_check for keyword in keywords):
        logger.info("Plot keyword detected.")
        return True
    if re.search(r'([yY]|f\(x\))\s*=', reasoning_and_answer) or re.search(r'\(\s*[\d\.\-]+\s*,\s*[\d\.\-]+\s*\)', reasoning_and_answer):
        logger.info("Function definition or data points detected for plotting.")
        return True
    return False

# --- Main Processing Function ---

async def process_user_message(user_message: str, websocket) -> AsyncGenerator[Dict[str, Any], None]:
    message_stream_id = uuid.uuid4().hex
    # Store the final structured response parts for caching
    final_response_parts_for_cache: List[Dict[str, Any]] = []

    try:
        # 1. Check Semantic Cache
        logger.info(f"[ID: {message_stream_id}] Checking cache for: '{user_message[:50]}...'")
        cached_response = await rag_utils.search_semantic_cache(user_message)
        if cached_response:
            logger.info(f"[ID: {message_stream_id}] Cache hit! Streaming cached response.")
            for cached_part in cached_response:
                 part_copy = cached_part.copy()
                 part_copy['id'] = message_stream_id
                 yield part_copy
            yield schemas.EndMessage(id=message_stream_id).model_dump()
            return

        logger.info(f"[ID: {message_stream_id}] Cache miss. Generating response.")

        # 2. RAG - Retrieve Context
        logger.info(f"[ID: {message_stream_id}] Performing RAG search...")
        contexts = await rag_utils.search_rag_kb(user_message)
        rag_context = "\n\n---\n\n".join(contexts)
        if rag_context:
            logger.info(f"[ID: {message_stream_id}] RAG context retrieved ({len(contexts)} docs).")
            rag_context = rag_context[:3500]
        else:
            logger.info(f"[ID: {message_stream_id}] No relevant context found via RAG.")

        # 3. Prepare messages for Reasoning LLM (Grok)
        system_prompt = """You are GrokSTEM, an expert AI assistant specializing in Science, Technology, Engineering, and Mathematics (STEM). Your goal is to provide clear, accurate, and step-by-step reasoning to help users understand complex problems.
1. Analyze the user's question carefully.
2. If relevant context is provided below under <context>, use it to inform your reasoning. If not, rely on your internal knowledge.
3. Break down the solution into logical, numbered steps. Each step MUST start with '## Step X: Title', where X is the step number and Title is a brief, descriptive summary of the step (e.g., "## Step 1: Identify Given Variables", "## Step 2: Apply Formula Y").
4. Explain the concepts and calculations involved in each step clearly. Define variables and state assumptions.
5. If the question involves mathematical formulas, present them clearly using standard notation (LaTeX can be used within markdown $...$ for inline math and $$...$$ for block math).
6. Conclude with a concise final answer or summary directly addressing the user's original question after all steps.
7. If the question is outside your STEM expertise, too ambiguous, or cannot be answered reliably based on the context/knowledge, clearly state that you cannot provide an answer and explain why.
"""
        messages_for_grok = [{"role": "system", "content": system_prompt}]
        if rag_context:
             messages_for_grok.append({"role": "system", "content": f"Use the following context if relevant:\n<context>\n{rag_context}\n</context>"})
        messages_for_grok.append({"role": "user", "content": user_message})

        # 4. Call Reasoning LLM (Grok)
        logger.info(f"[ID: {message_stream_id}] Calling Grok for reasoning...")
        grok_response_dict = await get_grok_reasoning(messages_for_grok, effort="medium")

        # --- Process Grok Response ---
        # Simplified: Assume 'content' contains the full formatted text including steps.
        full_response_text = grok_response_dict.get("content")
        if not full_response_text:
             logger.error(f"[ID: {message_stream_id}] Grok response missing 'content'. Response: {grok_response_dict}")
             raise ValueError("Grok response did not contain expected content.")

        logger.info(f"[ID: {message_stream_id}] Grok response received ({len(full_response_text)} chars total).")

        # 5. Stream Text Content (Paragraph by Paragraph)
        logger.info(f"[ID: {message_stream_id}] Streaming text content...")
        paragraphs = full_response_text.split('\n\n')
        for paragraph in paragraphs:
            if paragraph.strip():
                chunk_content = paragraph + "\n\n"
                text_chunk_msg = schemas.TextChunk(id=message_stream_id, content=chunk_content)
                yield text_chunk_msg.model_dump()
                await asyncio.sleep(0.02)
        final_response_parts_for_cache.append(schemas.TextChunk(id=message_stream_id, content=full_response_text).model_dump(exclude_none=True))

        # 6. Extract and Send Steps (from the full processed text)
        logger.info(f"[ID: {message_stream_id}] Extracting steps from full text...")
        steps = _extract_steps(full_response_text)
        if steps:
            steps_list_msg = schemas.StepsList(id=message_stream_id, steps=steps)
            yield steps_list_msg.model_dump()
            final_response_parts_for_cache.append(steps_list_msg.model_dump(exclude_none=True)) # Add to cache list

        # 7. Generate and Send Plot (if needed)
        logger.info(f"[ID: {message_stream_id}] Checking if plot is needed...")
        if await _decide_plot_needed(user_message, full_response_text):
            logger.info(f"[ID: {message_stream_id}] Plot potentially needed. Preparing plot prompt...")
            plot_prompt = f"""Analyze the following STEM problem and its reasoning/solution context. If the context contains sufficient data or a clearly defined mathematical function suitable for visualization, generate a Plotly JSON object for a relevant plot (e.g., line, scatter).

Problem:
{user_message}

Reasoning/Solution context:
{full_response_text[:2500]} # Provide substantial context

Instructions:
- First, determine if a meaningful plot can be generated from the context. If not, respond with only the single word "NO_PLOT".
- If a plot IS possible, output ONLY the Plotly JSON object (starting with {{{{ and ending with }}}}).
- Ensure the JSON includes 'data' (an array of traces) and 'layout' objects.
- Choose an appropriate plot type. Infer data points if a function and range are clearly implied (e.g., plot y=sin(x) from -pi to pi). Use a reasonable number of points (e.g., 50-100).
- Label axes clearly and provide a concise, relevant title for the plot.
- Do NOT include explanations, code fences (```json), or any text outside the JSON object or the "NO_PLOT" response.
"""
            plot_messages = [{"role": "user", "content": plot_prompt}]
            try:
                logger.info(f"[ID: {message_stream_id}] Calling GPT-4o-mini for plot JSON...")
                plotly_json = await llm_clients.get_plotly_json(plot_messages) # Use the helper which includes parsing
                if plotly_json:
                    plot_msg = schemas.PlotData(id=message_stream_id, plotly_json=plotly_json)
                    yield plot_msg.model_dump()
                    final_response_parts_for_cache.append(plot_msg.model_dump(exclude_none=True)) # Add to cache list
                    logger.info(f"[ID: {message_stream_id}] Plot JSON generated and yielded.")
                else:
                     logger.info(f"[ID: {message_stream_id}] Plotting LLM indicated no plot possible or returned invalid data.")
            except ValueError as json_parse_error: # Catch specific JSON errors from get_plotly_json
                 logger.warning(f"[ID: {message_stream_id}] Failed to get valid Plotly JSON: {json_parse_error}")
            except Exception as plot_e:
                logger.error(f"[ID: {message_stream_id}] Error during plot generation: {plot_e}", exc_info=False)

        # 8. Send End Message
        logger.info(f"[ID: {message_stream_id}] Sending end message.")
        yield schemas.EndMessage(id=message_stream_id).model_dump()

        # 9. Add successful result to cache
        # The final_response_parts_for_cache list now contains the full text, steps (if any), plot (if any)
        logger.info(f"[ID: {message_stream_id}] Adding response to cache ({len(final_response_parts_for_cache)} parts).")
        await rag_utils.add_to_semantic_cache(user_message, final_response_parts_for_cache)

    except ConnectionError as e:
         logger.error(f"[ID: {message_stream_id}] LLM or Qdrant client connection error: {e}")
         yield schemas.ErrorMessage(id=message_stream_id, content=f"Connection error: {e}").model_dump()
         yield schemas.EndMessage(id=message_stream_id).model_dump()
    except ValueError as e: # Catch specific errors like missing content
         logger.error(f"[ID: {message_stream_id}] Value error during processing: {e}")
         yield schemas.ErrorMessage(id=message_stream_id, content=f"Processing error: {e}").model_dump()
         yield schemas.EndMessage(id=message_stream_id).model_dump()
    except Exception as e:
        logger.error(f"[ID: {message_stream_id}] Unexpected error processing message: {e}", exc_info=True)
        yield schemas.ErrorMessage(id=message_stream_id, content="An unexpected internal error occurred.").model_dump()
        yield schemas.EndMessage(id=message_stream_id).model_dump()
    finally:
        # Ensure logger indicates processing completion for this stream ID
        logger.info(f"[ID: {message_stream_id}] Processing complete.")