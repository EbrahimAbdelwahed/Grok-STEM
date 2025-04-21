import logging
import json
import asyncio
from openai import OpenAI, AsyncOpenAI, APIConnectionError, RateLimitError, APIStatusError
from httpx import Timeout, AsyncClient # AsyncClient can be useful for health checks
from typing import Optional # Added Optional for type hinting

from config import settings

logger = logging.getLogger(__name__)

# --- Configure Timeouts ---
# Increased timeout for potentially long reasoning or plotting tasks
LLM_TIMEOUT = Timeout(450.0, connect=15.0) # 7.5 minutes total, 15s connect

# --- Grok Client (using OpenAI SDK structure) ---
grok_client: Optional[AsyncOpenAI] = None
try:
    if settings.XAI_API_KEY and settings.XAI_BASE_URL:
        logger.info(f"Initializing Grok client for: {settings.XAI_BASE_URL}")
        grok_client = AsyncOpenAI(
            base_url=str(settings.XAI_BASE_URL), # Pydantic v2 returns HttpUrl, needs str()
            api_key=settings.XAI_API_KEY,
            timeout=LLM_TIMEOUT,
            max_retries=2, # Add basic retries
        )
        logger.info("Grok client initialized.")
    else:
        logger.warning("XAI_API_KEY or XAI_BASE_URL not set. Grok client will not be initialized.")
except Exception as e:
    logger.error(f"Failed to initialize Grok client: {e}", exc_info=True)
    grok_client = None

# --- OpenAI Client (for plotting model) ---
openai_plotting_client: Optional[AsyncOpenAI] = None
try:
    if settings.OPENAI_API_KEY:
        logger.info("Initializing OpenAI client for plotting.")
        openai_plotting_client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=LLM_TIMEOUT,
            max_retries=2, # Add basic retries
        )
        logger.info("OpenAI plotting client initialized.")
    else:
        logger.warning("OPENAI_API_KEY not set. OpenAI plotting client will not be initialized.")
except Exception as e:
    logger.error(f"Failed to initialize OpenAI plotting client: {e}", exc_info=True)
    openai_plotting_client = None


# --- Helper Functions ---

async def get_grok_reasoning(messages: list, effort: str = "medium") -> dict:
    """Calls the Grok reasoning model using the OpenAI SDK compatibility."""
    if not grok_client:
        raise ConnectionError("Grok client is not initialized. Check API key and base URL.")

    logger.debug(f"Sending {len(messages)} messages to Grok model '{settings.REASONING_MODEL_NAME}' with effort '{effort}'.")
    try:
        completion = await grok_client.chat.completions.create(
            model=settings.REASONING_MODEL_NAME,
            messages=messages,
            temperature=0.6, # Slightly lower temp for more focused STEM reasoning
            stream=False, # We handle streaming paragraph-by-paragraph in chat_logic
            # Add the reasoning_effort parameter specific to Grok via extra_body
            extra_body={"reasoning_effort": effort}
        )

        if not completion.choices or not completion.choices[0].message:
             raise ValueError("Grok API returned an unexpected empty response structure.")

        response_message = completion.choices[0].message

        # *** IMPORTANT ***
        # Log the structure of the received message for verification
        # This helps confirm if 'content' holds the reasoning as expected
        # or if a custom field like 'reasoning_content' needs explicit access.
        logger.debug(f"Grok response message object: {response_message.model_dump_json(indent=2)}")

        # Assume the main text is in 'content' based on standard OpenAI structure.
        # If testing reveals 'reasoning_content' or another field holds the steps,
        # you'll need to adjust the parsing here or in chat_logic.py.
        if not response_message.content:
            logger.warning("Grok response message content is empty or None.")
            # Fallback or raise error depending on expected behavior
            # return {"role": "assistant", "content": "[Grok returned empty content]"}

        return response_message.model_dump() # Return the Pydantic model as a dict

    except (APIConnectionError, RateLimitError, APIStatusError) as api_err:
         logger.error(f"Grok API Error: {api_err}", exc_info=True)
         raise ConnectionError(f"Grok API Error: {api_err}") from api_err
    except Exception as e:
        logger.error(f"Unexpected error calling Grok API: {e}", exc_info=True)
        raise # Re-raise the exception to be handled upstream


async def get_plotly_json(messages: list) -> Optional[dict]:
    """
    Calls the OpenAI plotting model, expects Plotly JSON or "NO_PLOT".
    Returns the parsed JSON dict or None if no plot is generated or error occurs.
    """
    if not openai_plotting_client:
        raise ConnectionError("OpenAI plotting client is not initialized. Check API key.")

    logger.debug(f"Sending prompt to plotting model '{settings.PLOTTING_MODEL_NAME}'.")
    try:
        completion = await openai_plotting_client.chat.completions.create(
            model=settings.PLOTTING_MODEL_NAME,
            messages=messages,
            temperature=0.1, # Low temp for deterministic JSON/keyword output
            # Consider response_format for models supporting JSON mode explicitly
            # response_format={ "type": "json_object" },
            stream=False,
        )

        if not completion.choices or not completion.choices[0].message or not completion.choices[0].message.content:
             logger.warning("Plotting LLM returned empty response.")
             return None

        content = completion.choices[0].message.content.strip()

        # Check for explicit "NO_PLOT" response
        if content.upper() == "NO_PLOT":
            logger.info("Plotting LLM indicated NO_PLOT.")
            return None

        # Try parsing the content as JSON
        try:
            # Clean potential markdown code fences if present
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip() # Remove extra whitespace

            plotly_json = json.loads(content)

            # Basic validation
            if not isinstance(plotly_json, dict) or "data" not in plotly_json or "layout" not in plotly_json:
                 logger.warning(f"Invalid Plotly JSON structure received: {content[:100]}...")
                 raise ValueError("Invalid Plotly JSON structure received.")

            logger.info("Successfully parsed Plotly JSON from LLM.")
            return plotly_json

        except json.JSONDecodeError as json_e:
             logger.error(f"Failed to parse Plotly JSON from LLM: {json_e}\nRaw content: {content[:500]}...")
             # Don't raise here, just return None as we couldn't get a valid plot
             return None

    except (APIConnectionError, RateLimitError, APIStatusError) as api_err:
         logger.error(f"OpenAI Plotting API Error: {api_err}", exc_info=True)
         # Don't raise ConnectionError here, just return None (plot failed)
         return None
    except Exception as e:
        logger.error(f"Unexpected error calling OpenAI plotting API: {e}", exc_info=True)
        return None # Return None on unexpected errors


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
            # Use a lightweight endpoint if available, otherwise a simple, cheap call
            # Example: List models (might require different permissions/costs)
            # await client.models.list(timeout=10)
            # As a fallback, perform a HEAD request to the base URL if possible
            # For now, assume client initialization implies basic connectivity
            # We could add a minimal API call here if needed, e.g., a health check endpoint if x.ai/OpenAI provide one.
            async with AsyncClient(base_url=str(client.base_url), timeout=10) as http_client:
                response = await http_client.head("/") # Simple HEAD request to base URL
                response.raise_for_status() # Check if status code is ok (2xx)
            return "ok"
        except Exception as e:
            logger.warning(f"Health check failed for {name} client: {e}")
            return f"Error connecting to {name} API: {str(e)[:100]}..." # Truncate long errors

    if client_type == "all" or client_type == "grok":
        status["grok"] = await _check_client("Grok", grok_client)

    if client_type == "all" or client_type == "openai":
        status["openai_plotting"] = await _check_client("OpenAI Plotting", openai_plotting_client)

    return status

# --- Simple Test (Commented out actual API calls) ---
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO) # Set log level for testing

    async def test_clients():
        print("\n--- LLM Client Initialization Status ---")
        print(f"Grok Client Initialized: {'Yes' if grok_client else 'No'}")
        print(f"OpenAI Plotting Client Initialized: {'Yes' if openai_plotting_client else 'No'}")

        print("\n--- LLM API Status Check ---")
        api_status = await check_llm_api_status()
        print(f"Grok Status: {api_status.get('grok', 'Not Checked')}")
        print(f"OpenAI Plotting Status: {api_status.get('openai_plotting', 'Not Checked')}")

        # print("\n--- Attempting Simple Queries (Commented Out) ---")
        # if grok_client:
        #     try:
        #         test_msg = [{"role": "user", "content": "Explain entropy briefly."}]
        #         # response = await get_grok_reasoning(test_msg)
        #         # print("Grok Test Response:", response)
        #         print("Grok test call commented out.")
        #     except Exception as e:
        #          print(f"Grok test call failed: {e}")

        # if openai_plotting_client:
        #      try:
        #          test_msg = [{"role": "user", "content": "Generate Plotly JSON for y=x^2 from -2 to 2"}]
        #          # response = await get_plotly_json(test_msg)
        #          # print("OpenAI Plotting Test Response:", response)
        #          print("OpenAI Plotting test call commented out.")
        #      except Exception as e:
        #          print(f"OpenAI Plotting test call failed: {e}")

    asyncio.run(test_clients())

# --- Added functions for potential explicit cleanup ---
async def close_openai_client():
    """Closes the OpenAI plotting client."""
    if openai_plotting_client:
        logger.info("Closing OpenAI plotting client.")
        await openai_plotting_client.close()
        logger.info("OpenAI plotting client closed.")

async def close_grok_client():
    """Closes the Grok client."""
    if grok_client:
        logger.info("Closing Grok client.")
        await grok_client.close()
        logger.info("Grok client closed.")