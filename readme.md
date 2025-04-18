# PhiSTEM Chatbot: An Interactive STEM Learning Assistant

PhiSTEM is an AI-powered chatbot designed to assist users with STEM (Science, Technology, Engineering, Mathematics) problems. It provides step-by-step reasoning, generates relevant visualizations, and helps users understand complex concepts interactively.

## Core Features

*   **STEM Problem Solving:** Understands and provides reasoned solutions to problems across various STEM domains (Physics, Chemistry, Math, etc.).
*   **Step-by-Step Breakdown:** Deconstructs solutions into manageable steps for easier understanding.
*   **Interactive Step Navigation:** Allows users to click on specific steps in the solution to navigate the explanation.
*   **Plot Generation:** Dynamically generates relevant plots (using Plotly) based on the problem context, powered by GPT-4o-mini and potentially a cache.
*   **Vector Database Integration:** Leverages Qdrant for Retrieval-Augmented Generation (RAG) to enhance context and potentially cache common plots/solutions.
*   **WebSocket Communication:** Real-time, interactive chat experience.

## Technology Stack

*   **Frontend:**
    *   React (Vite build tool)
    *   TypeScript
    *   Tailwind CSS
    *   shadcn/ui (for UI components)
    *   Plotly.js (for rendering plots)
    *   Axios (for potential future REST calls)
*   **Backend:**
    *   Python 3.11+
    *   FastAPI (for web framework and WebSocket handling)
    *   Pydantic (for data validation)
    *   Uvicorn (ASGI server)
    *   Qdrant Client
    *   Langchain or direct SDK usage (for LLM interaction)
    *   OpenAI Python Client (for GPT-4o-mini)
    *   Anthropic Python Client / Google Generative AI Client (depending on reasoning LLM choice)
*   **Database:**
    *   Qdrant (Vector Database)
*   **LLMs:**
    *   **Reasoning:** Configurable - targeting Claude 3 Haiku / Gemini 1.5 Flash (via API)
    *   **Plotting:** GPT-4o-mini (via API)
*   **Containerization:**
    *   Docker
    *   Docker Compose

## Architecture Overview

The application follows a standard client-server architecture:

1.  **Frontend:** The React application serves the user interface. Users interact with the chat input. Messages are sent via a WebSocket connection to the backend. It receives text, steps, and Plotly JSON data from the backend and renders them appropriately.
2.  **Backend:** The FastAPI server listens for WebSocket connections. When a user message is received:
    *   It may first check a semantic cache (in Qdrant) for similar previous interactions.
    *   It uses RAG (querying the main `stem_qa` collection in Qdrant) to retrieve relevant context based on the user's query.
    *   It orchestrates calls to the primary reasoning LLM, providing the user query and retrieved context.
    *   It processes the LLM response to extract the textual answer and identify steps.
    *   It determines if a plot is needed. If so:
        *   (Optional) Checks a plot cache (in Qdrant).
        *   If no cache hit, it calls the GPT-4o-mini API to generate Plotly JSON.
    *   It streams the response (text chunks, step list, plot JSON) back to the frontend via WebSocket using a structured message format.
3.  **Qdrant:** Stores vector embeddings for STEM Q&A pairs (for RAG), semantic cache entries, and potentially pre-rendered Plotly JSON data.

**(Diagram placeholder - A visual diagram would be added here in a real README)**

## Project Structure