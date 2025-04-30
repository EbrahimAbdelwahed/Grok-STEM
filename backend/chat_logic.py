import logging
import uuid
import re
import json
from typing import AsyncGenerator, Dict, Any, List

from backend.config import settings
from backend.llm_clients import get_grok_reasoning, get_plotly_json
from backend.rag_utils import search_semantic_cache, add_to_semantic_cache

logger = logging.getLogger(__name__)

STEP_PATTERN = re.compile(r"^\s*#{1,4}\s*Step\s+(\d+)\s*[:\-–—]\s*(.+)$", re.MULTILINE | re.IGNORECASE)

async def process_user_message(user_message: str, chat_id: str) -> AsyncGenerator[Dict[str, Any], None]:
    """
    1) Semantic cache lookup
    2) RAG retrieval (omitted for brevity)
    3) Reasoning call
    4) Stream text
    5) Extract steps
    6) Plot if needed
    7) Cache final result
    """
    message_id = uuid.uuid4().hex
    logger.info(f"[{chat_id}][{message_id}] processing: {user_message[:50]}")

    # 1) Cache?
    # old signature: search_semantic_cache(user_query)
    cached = await search_semantic_cache(user_message)
    if cached:
        for part in cached:
            part["type"] = "text"
            part["id"] = message_id
            yield part
        return

    # 3) Reasoning
    grok_resp = await get_grok_reasoning(
        [{"role": "user", "content": user_message}], effort="medium"
    )
    text = grok_resp.get("content", "")
    # Stream as a single chunk (you can split for streaming if desired)
    yield {"type": "text", "id": message_id, "content": text}

    # 4) Steps
    steps: List[StepInfo] = []
    for m in STEP_PATTERN.finditer(text):
        steps.append({"id": f"step-{m.group(1)}", "title": m.group(2).strip()})
    if steps:
        yield {"type": "steps", "id": message_id, "steps": steps}

    # 5) Plot?
    plot = await get_plotly_json([
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": text}
    ])
    if plot:
        yield {"type": "plot", "id": message_id, "plotly_json": plot}

    # 6) Cache full response
    # old signature: add_to_semantic_cache(query, response_parts)
    await add_to_semantic_cache(user_message, [
        {"type": "text", "id": message_id, "content": text},
        *([{"type": "steps", "id": message_id, "steps": steps}] if steps else []),
        *([{"type": "plot", "id": message_id, "plotly_json": plot}] if plot else [])
    ])