import logging
import json
import asyncio
from typing import List, Optional

from httpx import Timeout, AsyncClient
from openai import OpenAI, AsyncOpenAI, APIConnectionError, RateLimitError, APIStatusError
from openai._exceptions import NotFoundError

from config import settings
from observability.http_logging import get_async_http_client  # FIX: use absolute import from package root
from observability import trace  # FIX: use absolute import for trace

logger = logging.getLogger(__name__)

# --- Configure Timeouts ---
GROK_TIMEOUT = Timeout(450.0, connect=15.0)  # For reasoning tasks
PLOTTING_TIMEOUT = 60  # seconds for plotting tasks

# --- Grok Client (using OpenAI SDK structure) ---
grok_client: Optional[AsyncOpenAI] = None
try:
    if settings.XAI_API_KEY and settings.XAI_BASE_URL:
        logger.info(f"Initializing Grok client for: {settings.XAI_BASE_URL}")
        grok_client = AsyncOpenAI(
            base_url=str(settings.XAI_BASE_URL),
            api_key=settings.XAI_API_KEY,
            timeout=GROK_TIMEOUT,
            max_retries=2,
        )
        logger.info("Grok client initialized.")
    else:
        logger.warning("XAI_API_KEY or XAI_BASE_URL not set. Grok client will not be initialized.")
except Exception as e:
    logger.error(f"Failed to initialize Grok client: {e}", exc_info=True)
    grok_client = None

# --- Lazy OpenAI Client for Plotting ---
_openai_plot_client: Optional[AsyncOpenAI] = None


def _create_openai_client() -> AsyncOpenAI:
    kwargs = {
        "api_key": settings.OPENAI_API_KEY,
        "timeout": PLOTTING_TIMEOUT,
        "max_retries": 2,
        "http_client": get_async_http_client(timeout=PLOTTING_TIMEOUT)  # NEW
    }
    if settings.OPENAI_BASE_URL:
        kwargs["base_url"] = str(settings.OPENAI_BASE_URL)
    logger.info("Initialising OpenAI client (plotting)…")
    return AsyncOpenAI(**kwargs)


@trace("llm_reasoning")  # NEW
async def _validate_plot_model(client: AsyncOpenAI, model_name: str) -> bool:
    """
    Returns True if the given model is available to this API key, False otherwise.
    """
    try:
        await client.models.retrieve(model_name)
        return True
    except NotFoundError:
        return False
    except Exception as exc:
        logger.warning("Unexpected error while validating plot model: %s", exc)
        return True  # don't block start-up on transient issues


async def get_openai_plot_client() -> AsyncOpenAI:
    """
    Lazily (async) initialises and validates the plotting OpenAI client.
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
        # Optionally raise or switch model dynamically.
    _openai_plot_client = client
    return _openai_plot_client

# --- High-level Helper Functions ---


async def get_grok_reasoning(messages: list, effort: str = "medium") -> dict:
    """Calls the Grok reasoning model using the OpenAI SDK compatibility."""
    if not grok_client:
        raise ConnectionError("Grok client is not initialized. Check API key and base URL.")

    logger.debug(f"Sending {len(messages)} messages to Grok model '{settings.REASONING_MODEL_NAME}' with effort '{effort}'.")
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
        logger.debug(f"Grok response message object: {response_message.model_dump_json(indent=2)}")

        if not response_message.content:
            logger.warning("Grok response message content is empty or None.")

        return response_message.model_dump()

    except (APIConnectionError, RateLimitError, APIStatusError) as api_err:
        logger.error(f"Grok API Error: {api_err}", exc_info=True)
        raise ConnectionError(f"Grok API Error: {api_err}") from api_err
    except Exception as e:
        logger.error(f"Unexpected error calling Grok API: {e}", exc_info=True)
        raise


async def get_plotly_json(messages: List[dict]) -> Optional[dict]:
    """
    Calls the OpenAI plotting model, expecting a valid Plotly JSON object
    or the literal string "NO_PLOT".

    Parameters
    ----------
    messages : List[dict]
        A standard OpenAI Chat API messages list.

    Returns
    -------
    dict | None
        Parsed Plotly spec or None if the model says "NO_PLOT" or an error occurs.
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


async def check_llm_api_status(client_type: str = "all") -> dict:
    """
    Performs a basic check of the LLM API connectivity.
    Avoids making actual completion calls if possible to save cost/tokens.
    Returns a dictionary with the status of each checked client.
    """
    status = {}

    async def _check_client(name: str, client: Optional[AsyncOpenAI]):
        if not client:
            return f"{name} client not initialized."
        try:
            async with AsyncClient(base_url=str(client.base_url), timeout=10) as http_client:
                response = await http_client.head("/")
                response.raise_for_status()
            return "ok"
        except Exception as e:
            logger.warning(f"Health check failed for {name} client: {e}")
            return f"Error connecting to {name} API: {str(e)[:100]}..."

    if client_type == "all" or client_type == "grok":
        status["grok"] = await _check_client("Grok", grok_client)

    if client_type == "all" or client_type == "openai":
        # Note: Use _openai_plot_client if already initialised; otherwise lazy initialization will occur later.
        openai_client = _openai_plot_client or None
        status["openai_plotting"] = await _check_client("OpenAI Plotting", openai_client)

    return status


# --- Cleanup Functions ---


async def close_openai_client():
    """Closes the OpenAI plotting client."""
    global _openai_plot_client
    if _openai_plot_client:
        logger.info("Closing OpenAI plotting client.")
        await _openai_plot_client.close()
        logger.info("OpenAI plotting client closed.")
        _openai_plot_client = None


async def close_grok_client():
    """Closes the Grok client."""
    global grok_client
    if grok_client:
        logger.info("Closing Grok client.")
        await grok_client.close()
        logger.info("Grok client closed.")
        grok_client = None


# --- Simple Test (Commented out actual API calls) ---
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    async def test_clients():
        print("\n--- LLM Client Initialization Status ---")
        print(f"Grok Client Initialized: {'Yes' if grok_client else 'No'}")
        print(f"OpenAI Plotting Client Initialized: {'Yes' if _openai_plot_client else 'No'}")

        print("\n--- LLM API Status Check ---")
        api_status = await check_llm_api_status()
        print(f"Grok Status: {api_status.get('grok', 'Not Checked')}")
        print(f"OpenAI Plotting Status: {api_status.get('openai_plotting', 'Not Checked')}")

        # Uncomment below to test API calls
        # if grok_client:
        #     try:
        #         test_msg = [{"role": "user", "content": "Explain entropy briefly."}]
        #         response = await get_grok_reasoning(test_msg)
        #         print("Grok Test Response:", response)
        #     except Exception as e:
        #         print(f"Grok test call failed: {e}")

        # if _openai_plot_client:
        #     try:
        #         test_msg = [{"role": "user", "content": "Generate Plotly JSON for y=x^2 from -2 to 2"}]
        #         response = await get_plotly_json(test_msg)
        #         print("OpenAI Plotting Test Response:", response)
        #     except Exception as e:
        #         print(f"OpenAI Plotting test call failed: {e}")

    asyncio.run(test_clients())