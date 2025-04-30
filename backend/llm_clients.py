
import os
import json
import logging
import asyncio
from typing import List, Dict, Any, Optional

# ---- Third‑party -----------------------------------------------------------
from dotenv import load_dotenv
from httpx import Timeout, AsyncClient
from openai import OpenAI, AsyncOpenAI, APIConnectionError, RateLimitError, APIStatusError
from openai._exceptions import NotFoundError

# ---- Internal --------------------------------------------------------------
from backend.config import settings
from backend.observability.http_logging import get_async_http_client

# ----------------------------------------------------------------------------
# Environment bootstrap
# ----------------------------------------------------------------------------
#
#   • Allows local development by reading .env but does not interfere with
#     production (where ENV‑vars will already be present).
#   • We *only* set OPENAI_API_KEY if it is missing in settings.
#
load_dotenv()

if not getattr(settings, "OPENAI_API_KEY", None):
    # Falls back to raw env variable so settings can still override.
    settings.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not getattr(settings, "XAI_API_KEY", None):
    settings.XAI_API_KEY = os.getenv("XAI_API_KEY")

# ----------------------------------------------------------------------------
# Logging
# ----------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------------
# Timeout / Retry configuration
# ----------------------------------------------------------------------------
GROK_TIMEOUT = Timeout(450.0, connect=15.0)  # reasoning tasks
PLOTTING_TIMEOUT = 60  # seconds for plotting tasks

# ----------------------------------------------------------------------------
# Grok client (AsyncOpenAI‑compatible)
# ----------------------------------------------------------------------------
grok_client: Optional[AsyncOpenAI] = None
try:
    if settings.XAI_API_KEY and settings.XAI_BASE_URL:
        logger.info("Initialising Grok client for %s", settings.XAI_BASE_URL)
        grok_client = AsyncOpenAI(
            base_url=str(settings.XAI_BASE_URL),
            api_key=settings.XAI_API_KEY,
            timeout=GROK_TIMEOUT,
            max_retries=2,
        )
    else:
        logger.warning("XAI_API_KEY or XAI_BASE_URL not set. Grok client will not be initialised.")
except Exception as exc:  # pragma: no cover
    # Should never blow‑up on import – just log & continue
    logger.error("Failed to initialise Grok client: %s", exc, exc_info=True)
    grok_client = None

# ----------------------------------------------------------------------------
# Lazy OpenAI (plotting) client
# ----------------------------------------------------------------------------
_openai_plot_client: Optional[AsyncOpenAI] = None


def _create_openai_client() -> AsyncOpenAI:
    """
    Internal helper to build a fully‑configured AsyncOpenAI instance for the
    plotting model. We wrap it so we can unit‑test w/out hitting the network.
    """
    kwargs: Dict[str, Any] = {
        "api_key": settings.OPENAI_API_KEY,
        "timeout": PLOTTING_TIMEOUT,
        "max_retries": 2,
        # Inject our HTTPX client with extra logging
        "http_client": get_async_http_client(timeout=PLOTTING_TIMEOUT),
    }
    if settings.OPENAI_BASE_URL:
        kwargs["base_url"] = str(settings.OPENAI_BASE_URL)

    logger.info("Initialising OpenAI client (plotting)…")
    return AsyncOpenAI(**kwargs)


async def _validate_plot_model(client: AsyncOpenAI, model_name: str) -> bool:
    """
    Quick HEAD‑style check to see if the chosen model is accessible.
    We do this once on first demand; it's *not* fatal to start‑up if it fails.
    """
    try:
        await client.models.retrieve(model_name)
        return True
    except NotFoundError:
        return False
    except Exception as exc:
        logger.warning("Unexpected error while validating plot model: %s", exc)
        return True  # Don't block on transient issues


async def get_openai_plot_client() -> AsyncOpenAI:
    """
    Lazily build / cache the plotting AsyncOpenAI client.
    """
    global _openai_plot_client
    if _openai_plot_client:
        return _openai_plot_client

    client = _create_openai_client()
    if not await _validate_plot_model(client, settings.PLOTTING_MODEL_NAME):
        logger.warning(
            "The plotting model '%s' is not available for this API key.",
            settings.PLOTTING_MODEL_NAME,
        )
    _openai_plot_client = client
    return _openai_plot_client

# ----------------------------------------------------------------------------
# High‑level helper functions
# ----------------------------------------------------------------------------
async def get_grok_reasoning(
    messages: List[Dict[str, str]],
    effort: str = "medium",
) -> Dict[str, Any]:
    """
    Fire a chat completion against the Grok reasoning model.
    """
    if not grok_client:
        raise ConnectionError("Grok client is not initialised. Check API key and base URL.")

    logger.debug(
        "Sending %d messages to Grok model '%s' with effort '%s'.",
        len(messages),
        settings.REASONING_MODEL_NAME,
        effort,
    )

    try:
        completion = await grok_client.chat.completions.create(
            model=settings.REASONING_MODEL_NAME,
            messages=messages,
            temperature=0.6,
            stream=False,
            extra_body={"reasoning_effort": effort},
        )

        if not completion.choices or not completion.choices[0].message:
            raise ValueError("Grok API returned an unexpected empty response structure.")

        response_message = completion.choices[0].message
        logger.debug("Grok response message: %s", response_message.model_dump_json(indent=2))

        if not response_message.content:
            logger.warning("Grok response message content is empty or None.")

        return response_message.model_dump()

    except (APIConnectionError, RateLimitError, APIStatusError) as api_err:
        logger.error("Grok API error: %s", api_err, exc_info=True)
        raise ConnectionError(f"Grok API error: {api_err}") from api_err
    except Exception as exc:
        logger.error("Unexpected error calling Grok API: %s", exc, exc_info=True)
        raise


async def get_plotly_json(messages: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
    """
    Call the plotting model and parse a valid Plotly spec, or return None.

    Parameters
    ----------
    messages : List[dict]
        A standard OpenAI Chat API messages list.
    """
    client = await get_openai_plot_client()

    try:
        completion = await client.chat.completions.create(
            model=settings.PLOTTING_MODEL_NAME,
            messages=messages,
            temperature=0.1,
            response_format={"type": "json_object"},
            seed=42,
        )

        content = (completion.choices[0].message.content or "").strip()

        if content.upper() == "NO_PLOT":
            logger.debug("Plotting LLM replied NO_PLOT.")
            return None

        plot_json = json.loads(content)
        if not isinstance(plot_json, dict) or "data" not in plot_json or "layout" not in plot_json:
            raise ValueError("Invalid Plotly JSON structure.")

        logger.info("Successfully parsed Plotly JSON from LLM.")
        return plot_json

    except json.JSONDecodeError as jde:
        logger.error("Failed to decode Plotly JSON: %s", jde)
    except (APIConnectionError, RateLimitError, APIStatusError) as api_err:
        logger.error("OpenAI plotting API error: %s", api_err)
    except Exception as exc:
        logger.error("Unexpected error during plotting call: %s", exc)

    return None


# ---------------------------------------------------------------------------
# Convenience wrapper (from the legacy file)
# ---------------------------------------------------------------------------
async def generate_plotly_json_from_conversation(
    conversation: List[Dict[str, str]],
) -> Optional[Dict[str, Any]]:
    """
    Legacy‑friendly helper that takes a *conversation* (user/assistant messages)
    and appends a system prompt asking for a Plotly spec.

    This mirrors the behaviour found in the now‑removed implementation so that
    existing callers continue to work.
    """
    prompt = (
        "Based on the conversation, produce a Plotly JSON for any required chart, "
        "or return the string NO_PLOT if no chart is needed."
    )
    full_messages = conversation + [{"role": "system", "content": prompt}]
    return await get_plotly_json(full_messages)

# ----------------------------------------------------------------------------
# Health‑check utilities
# ----------------------------------------------------------------------------
async def check_llm_api_status(client_type: str = "all") -> Dict[str, str]:
    """
    Minimal connectivity test for each LLM backend. Avoids expensive completions.
    """
    status: Dict[str, str] = {}

    async def _check_client(name: str, client: Optional[AsyncOpenAI]) -> str:
        if not client:
            return f"{name} client not initialised."
        try:
            async with AsyncClient(base_url=str(client.base_url), timeout=10) as http_client:
                response = await http_client.head("/")
                response.raise_for_status()
            return "ok"
        except Exception as exc:
            logger.warning("Health‑check failed for %s client: %s", name, exc)
            return f"Error connecting to {name} API: {str(exc)[:100]}…"

    if client_type in ("all", "grok"):
        status["grok"] = await _check_client("Grok", grok_client)

    if client_type in ("all", "openai"):
        openai_client = _openai_plot_client or None
        status["openai_plotting"] = await _check_client("OpenAI Plotting", openai_client)

    return status

# ----------------------------------------------------------------------------
# Cleanup helpers (to be called on app shutdown)
# ----------------------------------------------------------------------------
async def close_openai_client() -> None:
    """Close and release the plotting client."""
    global _openai_plot_client
    if _openai_plot_client:
        logger.info("Closing OpenAI plotting client.")
        await _openai_plot_client.close()
        _openai_plot_client = None
        logger.info("OpenAI plotting client closed.")


async def close_grok_client() -> None:
    """Close and release the Grok client."""
    global grok_client
    if grok_client:
        logger.info("Closing Grok client.")
        await grok_client.close()
        grok_client = None
        logger.info("Grok client closed.")

# ----------------------------------------------------------------------------
# Quick manual test (run with: `python -m backend.llm_clients`)
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    async def _test() -> None:
        print("\n--- LLM Client initialisation status ---")
        print(f"Grok Client initialised: {'Yes' if grok_client else 'No'}")
        print(f"OpenAI Plotting Client initialised: {'Yes' if _openai_plot_client else 'No'}")

        print("\n--- Health check ---")
        api_status = await check_llm_api_status()
        for name, st in api_status.items():
            print(f"{name:>18}: {st}")

        # Example calls (commented out to save tokens)
        # if grok_client:
        #     reasoning = await get_grok_reasoning([{"role": "user", "content": "Explain entropy in one sentence."}])
        #     print("\nGrok reasoning →", reasoning)
        #
        # plot = await generate_plotly_json_from_conversation(
        #     [{"role": "user", "content": "Please chart y = x^2 from -3 to 3."}]
        # )
        # print("\nPlot JSON →", plot)

    asyncio.run(_test())
