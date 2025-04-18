# backend/llm_clients.py

import logging
from openai import OpenAI, AsyncOpenAI # Use AsyncOpenAI for FastAPI compatibility
from httpx import Timeout # To potentially increase default timeout

# Import settings from the config module
from config import settings

logger = logging.getLogger(__name__)

# --- Configure Timeouts (Optional) ---
# Default timeout for OpenAI client might be too short for complex reasoning
# Adjust as needed based on observed API response times
DEFAULT_TIMEOUT = Timeout(300.0, connect=10.0) # 5 minutes total, 10s connect

# --- Grok Client (using OpenAI SDK structure) ---
try:
    logger.info(f"Initializing Grok client (via OpenAI SDK) for: {settings.xai_base_url}")
    # Use AsyncOpenAI for non-blocking calls in FastAPI endpoints/WebSockets
    grok_client = AsyncOpenAI(
        base_url=str(settings.xai_base_url), # Pydantic v2 returns HttpUrl, needs str()
        api_key=settings.xai_api_key,
        timeout=DEFAULT_TIMEOUT,
    )
    logger.info("Grok client initialized.")
except Exception as e:
    logger.error(f"Failed to initialize Grok client: {e}", exc_info=True)
    grok_client = None # Set to None on failure

# --- OpenAI Client (for plotting model) ---
try:
    logger.info("Initializing OpenAI client for plotting.")
    # Use AsyncOpenAI here as well for consistency and async compatibility
    openai_plotting_client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        timeout=DEFAULT_TIMEOUT, # Use the same timeout for now
    )
    logger.info("OpenAI plotting client initialized.")
except Exception as e:
    logger.error(f"Failed to initialize OpenAI plotting client: {e}", exc_info=True)
    openai_plotting_client = None # Set to None on failure


# --- Helper Functions (Optional but Recommended) ---
# You can add wrapper functions here later to standardize calling patterns,
# handle retries, or add specific logging/error handling for each model.

async def get_grok_reasoning(messages: list, effort: str = "medium") -> dict:
    """Placeholder for calling the Grok reasoning model."""
    if not grok_client:
        raise ConnectionError("Grok client is not initialized.")
    try:
        completion = await grok_client.chat.completions.create(
            model=settings.reasoning_model_name,
            messages=messages,
            temperature=0.7, # Adjust as needed
            # Add the reasoning_effort parameter specific to Grok
            extra_body={"reasoning_effort": effort} # Pass extra params this way
        )
        # Note: Accessing custom fields like 'reasoning_content' might require
        # careful handling or checking the raw response if the SDK doesn't map it directly.
        # For now, assume standard OpenAI response structure might be adapted.
        # We might need to inspect the actual response object structure from x.ai
        # and adjust how we extract 'reasoning_content' vs 'content'.

        # Example of potential structure (adjust based on actual Grok API response)
        # response_content = completion.choices[0].message.content
        # reasoning_content = getattr(completion.choices[0].message, 'reasoning_content', None)

        # Returning the whole choice message object for flexibility initially
        return completion.choices[0].message.model_dump() # Return Pydantic model as dict

    except Exception as e:
        logger.error(f"Error calling Grok API: {e}", exc_info=True)
        raise # Re-raise the exception to be handled upstream


async def get_plotly_json(messages: list) -> dict:
    """Placeholder for calling the OpenAI plotting model."""
    if not openai_plotting_client:
        raise ConnectionError("OpenAI plotting client is not initialized.")
    try:
        completion = await openai_plotting_client.chat.completions.create(
            model=settings.plotting_model_name,
            messages=messages,
            temperature=0.2, # Lower temp for more deterministic JSON output
            # Consider using response_format for explicit JSON mode if available/needed
            # response_format={ "type": "json_object" } # For models supporting JSON mode
        )
        # Assume the response content is the Plotly JSON string (may need parsing)
        content = completion.choices[0].message.content
        # TODO: Add JSON parsing and validation here
        import json
        try:
            plotly_json = json.loads(content)
            # Basic validation (can be more thorough)
            if not isinstance(plotly_json, dict) or "data" not in plotly_json or "layout" not in plotly_json:
                 raise ValueError("Invalid Plotly JSON structure received.")
            return plotly_json
        except json.JSONDecodeError as json_e:
             logger.error(f"Failed to parse Plotly JSON from LLM: {json_e}\nRaw content: {content}")
             raise ValueError("Failed to parse LLM response as valid JSON.") from json_e

    except Exception as e:
        logger.error(f"Error calling OpenAI plotting API: {e}", exc_info=True)
        raise


# --- Simple Test ---
if __name__ == "__main__":
    async def test_clients():
        if grok_client:
            print("\nGrok client initialized.")
            # Basic test - ping might not be available, use a simple query
            try:
                 print("Attempting simple Grok query (will consume tokens)...")
                 test_msg = [{"role": "user", "content": "Explain the concept of entropy briefly."}]
                 # response = await get_grok_reasoning(test_msg)
                 # print("Grok Test Response:", response)
                 print("Grok test call commented out to avoid cost during setup.")
            except Exception as e:
                 print(f"Grok test call failed: {e}")
        else:
            print("\nGrok client FAILED to initialize.")

        if openai_plotting_client:
            print("\nOpenAI plotting client initialized.")
            # Basic test
            try:
                print("Attempting simple OpenAI query (will consume tokens)...")
                test_msg = [{"role": "user", "content": "Say 'hello'."}]
                # response = await openai_plotting_client.chat.completions.create(
                #     model=settings.plotting_model_name, messages=test_msg
                # )
                # print("OpenAI Test Response:", response.choices[0].message.content)
                print("OpenAI test call commented out to avoid cost during setup.")
            except Exception as e:
                print(f"OpenAI test call failed: {e}")
        else:
            print("\nOpenAI plotting client FAILED to initialize.")

    import asyncio
    asyncio.run(test_clients())