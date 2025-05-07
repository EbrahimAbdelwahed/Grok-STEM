# backend/llm_clients.py

import os
import json
import logging
import asyncio
from typing import List, Dict, Any, Optional

# ---- Third‑party -----------------------------------------------------------
from dotenv import load_dotenv
from httpx import Timeout, AsyncClient
from openai import OpenAI, AsyncOpenAI, APIConnectionError, RateLimitError, APIStatusError, AuthenticationError, BadRequestError
from openai._exceptions import NotFoundError, APIResponseValidationError
from openai.types.chat import ChatCompletion
# CORRECTED IMPORT: Import Image and ImagesResponse separately
from openai.types import ImagesResponse # Import directly from openai.types
from openai.types.image import Image     # Image type is likely here

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
IMAGE_GEN_TIMEOUT = 120 # Allow more time for image generation

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
except Exception as exc:
    logger.error("Failed to initialise Grok client: %s", exc, exc_info=True)
    grok_client = None

# ----------------------------------------------------------------------------
# OpenAI client factory (can be reused for plotting and image gen)
# ----------------------------------------------------------------------------
_openai_client: Optional[AsyncOpenAI] = None

async def get_openai_client() -> Optional[AsyncOpenAI]:
    """Gets or creates the shared OpenAI client instance."""
    global _openai_client
    if _openai_client:
        return _openai_client

    if not settings.OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not configured. Cannot initialize OpenAI client.")
        return None

    kwargs: Dict[str, Any] = {
        "api_key": settings.OPENAI_API_KEY,
        # Use a reasonable default timeout, can be overridden per-request if needed
        "timeout": max(PLOTTING_TIMEOUT, IMAGE_GEN_TIMEOUT),
        "max_retries": 2,
        "http_client": get_async_http_client(timeout=max(PLOTTING_TIMEOUT, IMAGE_GEN_TIMEOUT)),
    }
    if settings.OPENAI_BASE_URL:
        kwargs["base_url"] = str(settings.OPENAI_BASE_URL)

    logger.info("Initialising shared OpenAI client...")
    try:
        client = AsyncOpenAI(**kwargs)
        # Optional: Validate connection or a specific model availability on first creation
        # await client.models.list() # Example validation
        _openai_client = client
        logger.info("Shared OpenAI client initialized successfully.")
        return _openai_client
    except Exception as exc:
        logger.error("Failed to initialise shared OpenAI client: %s", exc, exc_info=True)
        return None


async def close_openai_client() -> None:
    """Closes the shared OpenAI client."""
    global _openai_client
    if _openai_client:
        logger.info("Closing shared OpenAI client.")
        await _openai_client.close()
        _openai_client = None
        logger.info("Shared OpenAI client closed.")

# ----------------------------------------------------------------------------
# High‑level helper functions
# ----------------------------------------------------------------------------
async def get_grok_reasoning(
    messages: List[Dict[str, str]],
    effort: str = "medium",
) -> Dict[str, Any]:
    """Fires a chat completion against the Grok reasoning model."""
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
            temperature=0.6, # Keep temperature moderate for reasoning
            stream=False,
            # Grok-specific parameter
            extra_body={"reasoning_effort": effort} if effort else {},
        )

        completion_dict = completion.model_dump()

        # Handle embedded Grok 401 error
        if completion_dict.get("code") == 401:
            error_msg = completion_dict.get("msg", "Authentication failed.")
            logger.error(f"Grok API returned embedded authentication error: {error_msg}")
            raise ConnectionError(f"Grok API Authentication Failed: {error_msg}")

        if not completion.choices or not completion.choices[0].message:
            logger.error("Grok API returned unexpected empty response. Completion: %s", completion_dict)
            return {}

        response_message = completion.choices[0].message
        if response_message.content is None:
             logger.warning("Grok response message content is None. Finish reason: '%s'.", completion.choices[0].finish_reason)
             return {} # Treat as empty

        return response_message.model_dump()

    except (APIConnectionError, RateLimitError, APIStatusError, AuthenticationError, ConnectionError) as api_err:
        logger.error("Grok API error (%s): %s", type(api_err).__name__, api_err, exc_info=False)
        raise ConnectionError(f"Grok API Error ({type(api_err).__name__}): {api_err}") from api_err
    except Exception as exc:
        logger.error("Unexpected error calling Grok API: %s", exc, exc_info=True)
        raise


async def get_plotly_json(messages: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
    """Generates Plotly JSON using the configured plotting LLM."""
    client = await get_openai_client()
    if not client:
         logger.error("Failed to get OpenAI client for plotting.")
         return None

    # Add system message to guide the LLM for plotting
    system_prompt_plotting = f"""You are an expert data visualization assistant. Based on the conversation history, determine if a plot is appropriate and helpful.
- If a plot IS needed, generate ONLY the Plotly JSON (containing 'data' and 'layout' keys) for the chart. Use the model '{settings.PLOTTING_MODEL_NAME}'.
- If a plot is NOT needed or cannot be generated from the context, respond ONLY with the exact string: NO_PLOT"""

    plot_messages = messages + [{"role": "system", "content": system_prompt_plotting}]

    try:
        completion = await client.chat.completions.create(
            model=settings.PLOTTING_MODEL_NAME,
            messages=plot_messages, # type: ignore
            temperature=0.1, # Low temperature for deterministic plotting instructions
            response_format={"type": "json_object"}, # Request JSON output
            seed=42, # For reproducibility if supported
            timeout=PLOTTING_TIMEOUT, # Specific timeout for this call
        )

        content = (completion.choices[0].message.content or "").strip()

        if not content:
             logger.warning("Plotting LLM returned empty content.")
             return None

        # Check for explicit NO_PLOT signal before attempting JSON parse
        if content.strip().upper() == "NO_PLOT":
            logger.info("Plotting LLM indicated NO_PLOT needed.")
            return None

        try:
            plot_json = json.loads(content)
            if not isinstance(plot_json, dict) or "data" not in plot_json or "layout" not in plot_json:
                logger.error("Invalid Plotly JSON structure received: %s", content[:200])
                return None # Invalid structure, treat as no plot
            logger.info("Successfully parsed Plotly JSON from LLM.")
            return plot_json
        except json.JSONDecodeError as jde:
             # Handle case where response_format was requested but LLM didn't comply
             logger.error("Failed to decode Plotly JSON from LLM response (expected JSON object): %s\nResponse: %s", jde, content[:200])
             # Check if it accidentally returned "NO_PLOT" without JSON format
             if content.strip().upper() == "NO_PLOT":
                  logger.info("Plotting LLM indicated NO_PLOT needed (non-JSON format).")
                  return None
             return None # Failed to parse valid JSON

    except AuthenticationError as auth_err:
         logger.error("Authentication failed with OpenAI plotting API: %s", auth_err)
    except (APIConnectionError, RateLimitError, APIStatusError, BadRequestError) as api_err: # Added BadRequestError
        logger.error("OpenAI plotting API error: %s", api_err)
    except APIResponseValidationError as validation_err: # Handle cases where response doesn't match expected schema
         logger.error("OpenAI plotting API response validation error: %s", validation_err)
    except Exception as exc:
        logger.error("Unexpected error during plotting call: %s", exc, exc_info=True)

    return None # Return None on any error


# --- NEW: Image Generation ---
async def generate_image_from_prompt(prompt: str) -> Optional[str]:
    """Generates an image using the configured image generation model."""
    client = await get_openai_client()
    if not client:
        logger.error("Failed to get OpenAI client for image generation.")
        return None

    logger.info(f"Requesting image generation using model '{settings.IMAGE_MODEL_NAME}' for prompt: '{prompt[:75]}...'")
    try:
        # Use the correctly imported ImagesResponse type hint
        response: ImagesResponse = await client.images.generate(
            model=settings.IMAGE_MODEL_NAME,
            prompt=prompt,
            n=1,
            size="1024x1024",  # Adjust if different sizes are needed/supported
            response_format="url",  # Get URL directly
            quality="standard", # Or "hd" if desired and supported/needed
            # style="vivid", # Or "natural"
            timeout=IMAGE_GEN_TIMEOUT, # Specific timeout
        )

        if response.data and response.data[0].url:
            image_url = response.data[0].url
            logger.info(f"Image generated successfully: {image_url}")
            return image_url
        else:
            # This case should ideally be caught by SDK validation, but handle defensively
            logger.error("Image generation API response missing expected data or URL. Response: %s", response.model_dump_json())
            return None

    except AuthenticationError as auth_err:
         logger.error("Authentication failed with OpenAI image generation API: %s", auth_err)
    except BadRequestError as bad_req_err:
         # Specific handling for common errors like content policy violations
         if "content_policy_violation" in str(bad_req_err).lower():
              logger.warning(f"Image generation blocked due to content policy violation for prompt: '{prompt[:75]}...' Error: {bad_req_err}")
         elif "billing" in str(bad_req_err).lower():
              logger.error(f"Image generation failed due to billing issue: {bad_req_err}")
         else:
              logger.error(f"OpenAI image generation API bad request error: {bad_req_err}")
    except (APIConnectionError, RateLimitError, APIStatusError) as api_err:
        logger.error("OpenAI image generation API error: %s", api_err)
    except APIResponseValidationError as validation_err:
         logger.error("OpenAI image generation API response validation error: %s", validation_err)
    except Exception as exc:
        logger.error("Unexpected error during image generation call: %s", exc, exc_info=True)

    return None # Return None on any error


# --- NEW: Small LLM for Image Prompt Generation ---
async def generate_image_prompt_from_query(user_query: str) -> Optional[str]:
    """Uses a small LLM to generate an image prompt from a user query."""
    client = await get_openai_client()
    if not client:
        logger.error("Failed to get OpenAI client for image prompt generation.")
        return None

    system_prompt = "You are an assistant that creates concise, descriptive prompts suitable for an image generation model like DALL-E 3 based on a user's query. Focus on creating a helpful scientific illustration or diagram related to the query. Output ONLY the prompt text."
    prompt_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"User Query: {user_query}\nImage Prompt:"}
    ]

    logger.info(f"Generating image prompt using '{settings.IMAGE_PROMPT_GEN_MODEL_NAME}' for query: '{user_query[:75]}...'")
    try:
        completion = await client.chat.completions.create(
            model=settings.IMAGE_PROMPT_GEN_MODEL_NAME,
            messages=prompt_messages, # type: ignore
            temperature=0.3, # Lower temperature for focused prompts
            max_tokens=150, # Limit output length
            n=1,
            stop=None, # Let the model decide when to stop
            timeout=PLOTTING_TIMEOUT, # Reuse plotting timeout, usually sufficient
        )

        image_prompt = (completion.choices[0].message.content or "").strip()

        if not image_prompt:
            logger.warning("Image prompt generation LLM returned empty content.")
            return None

        # Basic cleanup: remove potential quotes or labels
        if image_prompt.lower().startswith("image prompt:"):
             image_prompt = image_prompt[len("image prompt:"):].strip()
        image_prompt = image_prompt.strip('"\'')

        logger.info(f"Generated image prompt: '{image_prompt[:100]}...'")
        return image_prompt

    except AuthenticationError as auth_err:
         logger.error("Authentication failed with OpenAI image prompt generation API: %s", auth_err)
    except (APIConnectionError, RateLimitError, APIStatusError, BadRequestError) as api_err:
        logger.error("OpenAI image prompt generation API error: %s", api_err)
    except Exception as exc:
        logger.error("Unexpected error during image prompt generation call: %s", exc, exc_info=True)

    return None


# ----------------------------------------------------------------------------
# Health‑check utilities
# ----------------------------------------------------------------------------
async def check_llm_api_status(client_type: str = "all") -> Dict[str, str]:
    status: Dict[str, str] = {}

    async def _check_grok() -> str:
        if not grok_client: return "Grok client not initialised."
        try:
            # Use a simple, low-effort call that should succeed if auth works
            await grok_client.chat.completions.create(
                model=settings.REASONING_MODEL_NAME,
                messages=[{"role": "user", "content": "Health check"}],
                max_tokens=1,
                extra_body={"reasoning_effort": "low"},
                timeout=15
            )
            return "ok"
        except AuthenticationError: return "Grok authentication failed (API Key/URL)."
        except ConnectionError as ce:
             # Catch the manually raised ConnectionError for embedded 401
             if "Grok API Authentication Failed" in str(ce):
                 return "Grok authentication failed (Embedded 401)."
             return f"Grok connection error: {str(ce)[:100]}…"
        except APIStatusError as e: return f"Grok API Error: Status {e.status_code}"
        except Exception as e: return f"Grok Error: {str(e)[:100]}…"

    async def _check_openai() -> str:
        openai_client = await get_openai_client()
        if not openai_client: return "OpenAI client failed to initialize."
        try:
            # Check if we can retrieve the plotting model details
            await openai_client.models.retrieve(settings.PLOTTING_MODEL_NAME, timeout=15)
            # Optionally, add a check for the image model too if crucial for startup
            # await openai_client.models.retrieve(settings.IMAGE_MODEL_NAME, timeout=15)
            return "ok"
        except NotFoundError as e: return f"OpenAI model not found: {e.model}"
        except AuthenticationError: return "OpenAI authentication failed."
        except APIStatusError as e: return f"OpenAI API Error: Status {e.status_code}"
        except Exception as e: return f"OpenAI Error: {str(e)[:100]}…"

    if client_type in ("all", "grok"):
        status["grok_reasoning"] = await _check_grok()

    if client_type in ("all", "openai"):
        status["openai_plotting_image"] = await _check_openai()

    return status

# ----------------------------------------------------------------------------
# Cleanup helpers - Close both clients now
# ----------------------------------------------------------------------------
async def close_clients() -> None:
    """Closes all initialized LLM clients."""
    await close_openai_client() # Close shared OpenAI client first
    if grok_client:
        logger.info("Closing Grok client.")
        await grok_client.close()
        grok_client = None # Reset global variable
        logger.info("Grok client closed.")

# ----------------------------------------------------------------------------
# Quick manual test ( остальное без изменений )
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    # ... (rest of the test code remains the same) ...
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("backend.llm_clients").setLevel(logging.DEBUG)
    logging.getLogger("backend.observability.http_logging").setLevel(logging.INFO)

    async def _test() -> None:
        print("\n--- LLM Client initialisation status ---")
        print(f"Grok Client initialised: {'Yes' if grok_client else 'No'}")
        openai_client = await get_openai_client()
        print(f"OpenAI Client initialised: {'Yes' if openai_client else 'No'}")

        print("\n--- Health check ---")
        api_status = await check_llm_api_status()
        for name, st in api_status.items():
            print(f"{name:>25}: {st}")

        # --- Example calls --- #
        print("\n--- Testing Grok Reasoning ---")
        if grok_client:
            try:
                reasoning = await get_grok_reasoning([{"role": "user", "content": "Explain Newton's first law briefly."}])
                print("Grok reasoning:", reasoning.get("content", "N/A")[:100] + "...")
            except Exception as e: print(f"ERROR during Grok test: {e}")

        print("\n--- Testing Plotting ---")
        if openai_client:
            try:
                plot_json = await get_plotly_json([{"role": "user", "content": "Plot y=x^2 from -5 to 5"}])
                print("Plotly JSON generated:", "Yes" if plot_json else "No (or NO_PLOT)")
                plot_json_no = await get_plotly_json([{"role": "user", "content": "What is the capital of France?"}])
                print("Plotly JSON not generated (expected):", "Yes" if not plot_json_no else "No")
            except Exception as e: print(f"ERROR during Plotting test: {e}")

        print("\n--- Testing Image Prompt Generation ---")
        if openai_client:
             try:
                  img_prompt = await generate_image_prompt_from_query("Show the process of photosynthesis")
                  print("Generated Image Prompt:", img_prompt)
             except Exception as e: print(f"ERROR during Image Prompt Gen test: {e}")

        print("\n--- Testing Image Generation ---")
        if openai_client and settings.OPENAI_API_KEY: # Only run if key is likely set
             try:
                  # Use a simple prompt known to be safe
                  image_url = await generate_image_from_prompt("A cute robot holding a beaker")
                  print("Image URL generated:", image_url if image_url else "No")
             except Exception as e: print(f"ERROR during Image Gen test: {e}")
        else:
             print("Skipping image generation test (OpenAI client or key missing).")


        # Close clients after test
        await close_clients()

    asyncio.run(_test())