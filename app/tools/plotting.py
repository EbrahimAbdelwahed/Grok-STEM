"""
Plotting module for GROK-STEM project.
Generates matplotlib plots based on text prompts using Grok's code generation.
"""

import io
import os
import base64
import warnings
from typing import Optional, Tuple

import openai
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def load_template() -> str:
    """
    Loads the plot template from the prompts/plot_template.txt file.
    If the file doesn't exist, returns a default template.
    
    Returns:
        The plot template as a string
    """
    template_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                                "prompts", "plot_template.txt")
    
    # Default template in case the file doesn't exist
    default_template = """You are a data visualization expert who generates Python code for matplotlib plots.
Your task is to create a visualization based on the user's request.

Guidelines:
1. Generate Python code that produces the requested plot.
2. Use numpy and pandas for data generation and manipulation.
3. Use matplotlib for visualization.
4. Make the plot visually appealing with proper labels, titles, and colors.
5. Save the plot to a BytesIO object named 'buf' using plt.savefig(buf, format='png').
6. Do not include code for displaying the plot (plt.show()).
7. Always include code to close the figure (plt.close()) to avoid memory leaks.

The code must follow this structure:
```python
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import io
import base64

# Create figure and axes
fig, ax = plt.subplots(figsize=(10, 6))

# Generate or load data
# ... data generation code ...

# Create the plot
# ... plotting code ...

# Add labels, title, legend, etc.
ax.set_xlabel('X Label')
ax.set_ylabel('Y Label')
ax.set_title('Title')

# Save to BytesIO object
buf = io.BytesIO()
plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
buf.seek(0)
plt.close()
```

Only respond with the Python code without any explanation or markdown formatting.

{{user_prompt}}"""
    
    try:
        with open(template_path, 'r') as file:
            return file.read()
    except FileNotFoundError:
        # If the template file doesn't exist, use the default template
        warnings.warn(f"Template file not found at {template_path}. Using default template.")
        return default_template


def generate_plot_code(prompt: str) -> str:
    """
    Generates Python code for a matplotlib plot based on the given prompt.
    
    Args:
        prompt: The text prompt describing the plot to generate
        
    Returns:
        Python code that generates the requested plot
        
    Raises:
        RuntimeError: If the API call fails or returns invalid code
    """
    # Load the template and substitute the user prompt
    template = load_template()
    system_message = template.replace("{{user_prompt}}", "")
    
    try:
        # Call the Grok API to generate the plot code
        response = openai.chat.completions.create(
            model="grok-3-mini",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ]
        )
        
        # Extract the code from the response
        code = response.choices[0].message.content
        
        # Clean up the code (remove markdown code blocks if present)
        if code.startswith("```python"):
            code = code.split("```python", 1)[1]
        if code.endswith("```"):
            code = code.rsplit("```", 1)[0]
        
        code = code.strip()
        return code
        
    except Exception as e:
        raise RuntimeError(f"Failed to generate plot code: {str(e)}") from e


def execute_plot_code(code: str) -> Tuple[bytes, str]:
    """
    Executes the generated plotting code in a controlled environment.
    
    Args:
        code: The Python code to execute
        
    Returns:
        A tuple containing:
        - The raw bytes of the generated plot image
        - The code that was executed (for debugging/logging)
        
    Raises:
        RuntimeError: If the code execution fails or doesn't produce a plot
    """
    # Create a restricted namespace for execution
    namespace = {
        'plt': plt,
        'np': np,
        'pd': pd,
        'io': io,
        'base64': base64,
    }
    
    try:
        # Execute the code in the controlled namespace
        exec(code, namespace)
        
        # Retrieve the buffer from the namespace
        buf = namespace.get('buf')
        if buf is None:
            raise RuntimeError("The generated code did not create a 'buf' variable")
        
        # Get the plot bytes
        plot_bytes = buf.getvalue()
        if not plot_bytes:
            raise RuntimeError("The plot buffer is empty")
            
        return plot_bytes, code
        
    except Exception as e:
        raise RuntimeError(f"Error executing plot code: {str(e)}\n\nCode:\n{code}") from e


def generate_plot(prompt: str) -> Tuple[bytes, str]:
    """
    Generates a matplotlib plot based on the given prompt.
    
    Args:
        prompt: The text prompt describing the plot to generate
        
    Returns:
        A tuple containing:
        - The raw bytes of the generated plot image
        - The code that was used to generate the plot
        
    Raises:
        RuntimeError: If plot generation fails
    """
    try:
        # Generate the plotting code
        plot_code = generate_plot_code(prompt)
        
        # Execute the code to create the plot
        plot_bytes, executed_code = execute_plot_code(plot_code)
        
        return plot_bytes, executed_code
        
    except Exception as e:
        # Ensure we close any open matplotlib figures in case of error
        plt.close('all')
        raise RuntimeError(f"Failed to generate plot: {str(e)}") from e


def save_generated_plot(prompt: str, output_path: str) -> Optional[str]:
    """
    Generates a plot from a prompt and saves it to the specified path.
    
    Args:
        prompt: The text prompt describing the plot to generate
        output_path: The file path where the plot should be saved
        
    Returns:
        The path to the saved plot if successful, None otherwise
    """
    try:
        # Generate the plot
        plot_bytes, _ = generate_plot(prompt)
        
        # Save the bytes to the output file
        with open(output_path, 'wb') as f:
            f.write(plot_bytes)
            
        return output_path
        
    except Exception as e:
        print(f"Failed to save generated plot: {str(e)}")
        return None