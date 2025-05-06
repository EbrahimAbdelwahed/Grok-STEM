import os
import json
import logging
import asyncio
from typing import List, Dict, Any, Optional

# ---- Third‑party -----------------------------------------------------------
from dotenv import load_dotenv
from httpx import Timeout, AsyncClient
# Import specific errors we might catch or want to reference
from openai import OpenAI, AsyncOpenAI, APIConnectionError, RateLimitError, APIStatusError, AuthenticationError
from openai._exceptions import NotFoundError
from openai.types.chat import ChatCompletion

# ---- Internal --------------------------------------------------------------
from backend.config import settings
from backend.observability.http_logging import get_async_http_client

# ----------------------------------------------------------------------------
# Environment bootstrap
# ----------------------------------------------------------------------------
load_dotenv()

if not getattr(settings, "OPENAI_API_KEY", None):
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
        base=str(settings.XAI_BASE_URL).rstrip("/")
        logger.info("Initialising Grok client for %s", settings.XAI_BASE_URL)
        grok_client = AsyncOpenAI(
            base_url=f"{base}/v1",
            api_key=settings.XAI_API_KEY,
            timeout=GROK_TIMEOUT,
            max_retries=2,
            http_client=get_async_http_client(timeout=GROK_TIMEOUT),
        )
    else:
        logger.warning("XAI_API_KEY or XAI_BASE_URL not set. Grok client will not be initialised.")
except Exception as exc:  # pragma: no cover
    logger.error("Failed to initialise Grok client: %s", exc, exc_info=True)
    grok_client = None

# ----------------------------------------------------------------------------
# Lazy OpenAI (plotting) client
# ----------------------------------------------------------------------------
_openai_plot_client: Optional[AsyncOpenAI] = None


def _create_openai_client() -> AsyncOpenAI:
    kwargs: Dict[str, Any] = {
        "api_key": settings.OPENAI_API_KEY,
        "timeout": PLOTTING_TIMEOUT,
        "max_retries": 2,
        "http_client": get_async_http_client(timeout=PLOTTING_TIMEOUT),
    }
    if settings.OPENAI_BASE_URL:
        kwargs["base_url"] = str(settings.OPENAI_BASE_URL)

    logger.info("Initialising OpenAI client (plotting)…")
    return AsyncOpenAI(**kwargs)


async def _validate_plot_model(client: AsyncOpenAI, model_name: str) -> bool:
    try:
        await client.models.retrieve(model_name)
        return True
    except NotFoundError:
        return False
    except Exception as exc:
        logger.warning("Unexpected error while validating plot model: %s", exc)
        return True


async def get_openai_plot_client() -> AsyncOpenAI:
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

    Returns:
        Dict containing the response message content and other details,
        or an empty Dict {} if the API returns an empty/unexpected structure
        after a successful call (e.g., due to content filtering).

    Raises:
        ConnectionError: If there's an issue connecting to the API, an authentication
                         failure (detected via embedded code), or other non-2xx API error.
    """
    if not grok_client:
        raise ConnectionError("Grok client is not initialised. Check API key and base URL.")

    logger.debug(
        "Sending %d messages to Grok model '%s' with effort '%s'. First message: %s",
        len(messages),
        settings.REASONING_MODEL_NAME,
        effort,
        messages[0]['content'][:50] + "..." if messages else "N/A"
    )

    try:
        completion: ChatCompletion = await grok_client.chat.completions.create(
            model=settings.REASONING_MODEL_NAME,
            messages=messages, # type: ignore
            temperature=0.6,
            stream=False,
            extra_body={"reasoning_effort": effort},
        )

        completion_dict = completion.model_dump()

        # --- **CORRECTED ERROR HANDLING for embedded 401** ---
        if completion_dict.get("code") == 401:
            error_msg = completion_dict.get("msg", "Authentication failed.")
            logger.error(
                "Grok API returned an authentication error embedded in the response: code=401, msg='%s'",
                error_msg
            )
            # Raise a standard ConnectionError with a specific message
            # This avoids the TypeError from the SDK's AuthenticationError constructor
            raise ConnectionError(f"Grok API Authentication Failed: {error_msg}")
        # --- **END CORRECTION** ---


        if not completion.choices or not completion.choices[0].message:
            logger.error(
                "Grok API returned an unexpected empty response structure (after passing auth check). Completion object: %s",
                 completion.model_dump_json(indent=2)
            )
            return {} # Return empty dict for unexpected structure

        response_message = completion.choices[0].message
        finish_reason = completion.choices[0].finish_reason

        logger.debug("Grok response message: %s", response_message.model_dump_json(indent=2))
        logger.debug("Grok finish reason: %s", finish_reason)

        if response_message.content is None:
             logger.warning("Grok response message content is None. Finish reason: '%s'. Returning empty response.", finish_reason)
             return {}

        if response_message.content == "":
             logger.warning("Grok response message content is an empty string. Finish reason: '%s'. Returning empty response.", finish_reason)
             return {}

        return response_message.model_dump()

    # Catch standard OpenAI SDK errors (including AuthenticationError if raised by SDK itself)
    # And catch the ConnectionError we raised manually above for the embedded 401
    except (APIConnectionError, RateLimitError, APIStatusError, AuthenticationError, ConnectionError) as api_err:
        # Log the specific type of error caught
        logger.error("Grok API error (%s): %s", type(api_err).__name__, api_err, exc_info=False) # exc_info=False is often cleaner here
        # Re-raise as a standard ConnectionError for chat_logic to handle generically
        # Include the original error type and message for context
        raise ConnectionError(f"Grok API Error ({type(api_err).__name__}): {api_err}") from api_err

    except Exception as exc:
        # Catch any other unexpected errors
        logger.error("Unexpected error calling Grok API: %s", exc, exc_info=True)
        raise # Re-raise the original unexpected error


async def get_plotly_json(messages: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
    # (No changes needed in this function from previous version)
    client = await get_openai_plot_client()
    # Add try-except around getting the client itself
    if not client:
         logger.error("Failed to get OpenAI plot client. Cannot generate plot.")
         return None

    try:
        completion = await client.chat.completions.create(
            model=settings.PLOTTING_MODEL_NAME,
            messages=messages, # type: ignore
            temperature=0.1,
            response_format={"type": "json_object"},
            seed=42,
        )

        content = (completion.choices[0].message.content or "").strip()

        if not content:
             logger.warning("Plotting LLM returned empty content.")
             return None

        if content.upper() == "NO_PLOT":
            logger.debug("Plotting LLM replied NO_PLOT.")
            return None

        plot_json = json.loads(content)
        if not isinstance(plot_json, dict) or "data" not in plot_json or "layout" not in plot_json:
            logger.error("Invalid Plotly JSON structure received: %s", content[:100])
            # Don't raise ValueError, just return None to avoid breaking chat flow
            return None

        logger.info("Successfully parsed Plotly JSON from LLM.")
        return plot_json

    except json.JSONDecodeError as jde:
        logger.error("Failed to decode Plotly JSON from LLM response: %s", jde)
    except AuthenticationError as auth_err:
         logger.error("Authentication failed with OpenAI plotting API: %s", auth_err)
    except (APIConnectionError, RateLimitError, APIStatusError) as api_err:
        logger.error("OpenAI plotting API error: %s", api_err)
    except Exception as exc:
        logger.error("Unexpected error during plotting call: %s", exc)

    return None # Return None on any error during plotting


# --- Convenience wrapper, Health check, Cleanup, and main test remain the same ---
# (rest of the file is unchanged from the previous version) ...

# ---------------------------------------------------------------------------
# Convenience wrapper (from the legacy file) - Remains the same
# ---------------------------------------------------------------------------
async def generate_plotly_json_from_conversation(
    conversation: List[Dict[str, str]],
) -> Optional[Dict[str, Any]]:
    prompt = (
        "Based on the conversation, produce a Plotly JSON for any required chart, "
        "or return the string NO_PLOT if no chart is needed."
    )
    full_messages = conversation + [{"role": "system", "content": prompt}]
    return await get_plotly_json(full_messages)

# ----------------------------------------------------------------------------
# Health‑check utilities - Remains the same
# ----------------------------------------------------------------------------
async def check_llm_api_status(client_type: str = "all") -> Dict[str, str]:
    status: Dict[str, str] = {}

    async def _check_client(name: str, client: Optional[AsyncOpenAI]) -> str:
        if not client:
            return f"{name} client not initialised."
        try:
            async with AsyncClient(base_url=str(client.base_url), timeout=10) as http_client:
                response = await http_client.head("/", follow_redirects=True)
                # Check for the specific embedded 401 if it's the Grok client being checked
                if name == "Grok" and response.status_code == 200:
                     try:
                          # Attempt to parse potential JSON error body even on 200 OK for Grok check
                          body = response.json()
                          if body.get("code") == 401:
                               return f"Authentication failed for {name} API (Embedded 401)."
                     except Exception:
                          pass # Ignore if body isn't JSON or doesn't have 'code'

                response.raise_for_status() # Raise for actual non-2xx/3xx HTTP status codes
            return "ok"
        except AuthenticationError:
             return f"Authentication failed for {name} API (HTTP 401)."
        except APIStatusError as e: # Catch specific status errors
             return f"API Error for {name}: Status {e.status_code}"
        except Exception as exc:
            logger.warning("Health‑check failed for %s client: %s", name, exc)
            return f"Error connecting to {name} API: {str(exc)[:100]}…"

    if client_type in ("all", "grok"):
        status["grok"] = await _check_client("Grok", grok_client)

    if client_type in ("all", "openai"):
        try:
            openai_client_instance = await get_openai_plot_client()
            status["openai_plotting"] = await _check_client("OpenAI Plotting", openai_client_instance)
        except Exception as init_err:
             logger.error("Failed to initialize OpenAI client for health check: %s", init_err)
             status["openai_plotting"] = "Client initialization failed."


    return status


# ----------------------------------------------------------------------------
# Cleanup helpers - Remains the same
# ----------------------------------------------------------------------------
async def close_openai_client() -> None:
    global _openai_plot_client
    if _openai_plot_client:
        logger.info("Closing OpenAI plotting client.")
        await _openai_plot_client.close()
        _openai_plot_client = None
        logger.info("OpenAI plotting client closed.")


async def close_grok_client() -> None:
    global grok_client
    if grok_client:
        logger.info("Closing Grok client.")
        await grok_client.close()
        grok_client = None
        logger.info("Grok client closed.")

# ----------------------------------------------------------------------------
# Quick manual test - Remains the same
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    # Set higher level for normal operation, DEBUG for testing details
    logging.basicConfig(level=logging.INFO)
    # Set specific loggers to DEBUG if needed
    logging.getLogger("backend.llm_clients").setLevel(logging.DEBUG)
    logging.getLogger("backend.observability.http_logging").setLevel(logging.INFO) # INFO for HTTP usually sufficient

    async def _test() -> None:
        print("\n--- LLM Client initialisation status ---")
        print(f"Grok Client initialised: {'Yes' if grok_client else 'No'}")
        try:
             await get_openai_plot_client()
             print(f"OpenAI Plotting Client initialised: {'Yes' if _openai_plot_client else 'No'}")
        except Exception as e:
             print(f"OpenAI Plotting Client initialization failed: {e}")


        print("\n--- Health check ---")
        api_status = await check_llm_api_status()
        for name, st in api_status.items():
            print(f"{name:>18}: {st}")

        # --- Example calls --- #
        print("\n--- Testing Grok Reasoning (ensure .env is correct!) ---")
        if grok_client:
            try:
                reasoning = await get_grok_reasoning([{"role": "user", "content": "What is 1+1?"}])
                print("\nGrok reasoning Raw →", reasoning)
                if reasoning and reasoning.get("content"):
                     print("\nGrok reasoning Content →", reasoning["content"])
                elif not reasoning:
                     print("\nGrok reasoning returned empty response (check logs for details).")
            except ConnectionError as e:
                print(f"\nCONNECTION ERROR during Grok test: {e}")
            except Exception as e:
                print(f"\nUNEXPECTED ERROR during Grok test: {e}")
        else:
             print("Grok client not available for test.")


        # Close clients after test
        await close_grok_client()
        await close_openai_client()

    asyncio.run(_test())