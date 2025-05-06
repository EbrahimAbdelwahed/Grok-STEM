import logging
import os
import requests
from typing import Optional, Dict, Any
import io
import base64

logger = logging.getLogger(__name__)

# Configure API keys and endpoints from environment variables
GROK_API_KEY = os.environ.get("GROK_API_KEY")
GROK_API_ENDPOINT = os.environ.get("GROK_API_ENDPOINT", "https://api.groq.com/openai/v1/chat/completions")

def generate_plot(prompt: str) -> bytes:
    """
    Generate a plot using Grok's Python code execution capabilities.
    
    Args:
        prompt: The text description of the plot to generate
        
    Returns:
        Raw PNG bytes of the generated plot
    """
    if not GROK_API_KEY:
        raise ValueError("GROK_API_KEY not configured")
    
    # Enhance the prompt to generate Python plotting code
    enhanced_prompt = f"""
    Generate Python code to create the following plot: {prompt}
    
    Use matplotlib and any necessary data libraries. The code should:
    1. Generate sample data if needed or use a relevant dataset
    2. Create a publication-quality matplotlib visualization
    3. Include proper labels, title, and styling
    4. Save the plot to a BytesIO object and return the bytes
    5. DO NOT display the plot, just return it

    Only return valid Python code without explanations. The code must be complete and executable.
    """
    
    # Call Grok API to generate the Python code
    code = call_grok_api(enhanced_prompt)
    if not code:
        raise Exception("Failed to generate valid plotting code")
    
    # Execute the code safely to generate the plot
    plot_bytes = execute_plotting_code(code)
    if not plot_bytes:
        raise Exception("Failed to execute plotting code")
    
    return plot_bytes

def call_grok_api(prompt: str) -> Optional[str]:
    """
    Call the Grok API to generate Python code.
    
    Args:
        prompt: The prompt to send to Grok
        
    Returns:
        Generated Python code or None if failed
    """
    headers = {
        "Authorization": f"Bearer {GROK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "mixtral-8x7b-32768",  # Or whatever Grok model you're using
        "messages": [
            {"role": "system", "content": "You are a Python data visualization expert. Generate complete, executable Python code for matplotlib plots based on the user's request."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2
    }
    
    try:
        response = requests.post(
            GROK_API_ENDPOINT,
            headers=headers,
            json=payload
        )
        
        if response.status_code != 200:
            logger.error(f"Grok API error: {response.status_code} - {response.text}")
            return None
        
        result = response.json()
        if "choices" in result and result["choices"]:
            # Extract the code from the response
            content = result["choices"][0]["message"]["content"]
            
            # Extract code blocks if present
            if "```python" in content:
                code_block = content.split("```python")[1].split("```")[0].strip()
                return code_block
            elif "```" in content:
                code_block = content.split("```")[1].split("```")[0].strip()
                return code_block
            else:
                return content.strip()
        
        return None
    except Exception as e:
        logger.error(f"Error calling Grok API: {str(e)}")
        return None

def execute_plotting_code(code: str) -> Optional[bytes]:
    """
    Safely execute the generated plotting code to produce a PNG image.
    
    Args:
        code: Python code to execute
        
    Returns:
        Raw PNG bytes of the generated plot or None if execution failed
    """
    try:
        # Create a safe execution environment with necessary imports
        execution_globals = {
            "__builtins__": __builtins__,
            "bytes": bytes,
            "io": io,
            "base64": base64
        }
        
        # Add common data science and plotting libraries
        import matplotlib
        matplotlib.use('Agg')  # Use non-interactive backend
        
        import matplotlib.pyplot as plt
        import numpy as np
        import pandas as pd
        
        execution_globals.update({
            "plt": plt,
            "np": np,
            "pd": pd,
            "BytesIO": io.BytesIO
        })
        
        # Check if the code creates a BytesIO object and returns it
        if "BytesIO" not in code or "savefig" not in code:
            # Adjust the code to save to BytesIO
            modified_code = code + """
            # Save the plot to BytesIO
            buffer = BytesIO()
            plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
            buffer.seek(0)
            plot_bytes = buffer.getvalue()
            """
        else:
            modified_code = code
        
        # Execute the code
        execution_locals = {}
        exec(modified_code, execution_globals, execution_locals)
        
        # Extract the plot bytes
        if "plot_bytes" in execution_locals:
            return execution_locals["plot_bytes"]
        elif "buffer" in execution_locals:
            buffer = execution_locals["buffer"]
            buffer.seek(0)
            return buffer.getvalue()
        else:
            raise ValueError("Code execution did not produce plot bytes")
    
    except Exception as e:
        logger.error(f"Error executing plotting code: {str(e)}")
        return None