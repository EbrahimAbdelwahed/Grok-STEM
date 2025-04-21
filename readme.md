# GrokSTEM: An Interactive STEM Learning Assistant

GrokSTEM is an AI-powered chatbot designed to assist users with STEM (Science, Technology, Engineering, Mathematics) problems. It provides step-by-step reasoning, generates relevant visualizations, and helps users understand complex concepts interactively.

## Core Features

*   **STEM Problem Solving:** Understands and provides reasoned solutions to problems across various STEM domains (Physics, Chemistry, Math, Engineering etc.). Powered by Grok-3-mini Beta for detailed reasoning.
*   **Step-by-Step Breakdown:** Deconstructs solutions into manageable, numbered steps for easier understanding.
*   **Interactive Step Navigation:** Allows users to click on specific steps in the solution to navigate the explanation.
*   **Plot Generation:** Dynamically generates relevant plots (using Plotly) based on the problem context, powered by GPT-4o-mini.
*   **Vector Database Integration (Qdrant):**
    *   Utilizes Retrieval-Augmented Generation (RAG) to fetch relevant context from a knowledge base (e.g., STEM documents).
    *   Implements semantic caching to quickly retrieve answers for similar past questions, including associated plots.
*   **WebSocket Communication:** Real-time, interactive chat experience.
*   **Theming:** Supports Light and Dark modes.

## Technology Stack

*   **Frontend:**
    *   React (Vite build tool)
    *   TypeScript
    *   Tailwind CSS
    *   shadcn/ui (for UI components)
    *   Plotly.js (for rendering plots)
    *   React Router (for navigation)
*   **Backend:**
    *   Python 3.11+
    *   FastAPI (for web framework and WebSocket handling)
    *   Pydantic & Pydantic-Settings (for data validation and config)
    *   Uvicorn (ASGI server)
    *   Qdrant Client (for vector DB interaction)
    *   OpenAI Python Client (for Grok-3-mini Beta and GPT-4o-mini)
    *   Sentence-Transformers (for generating text embeddings - e.g., `all-MiniLM-L6-v2`)
*   **Database:**
    *   Qdrant (Vector Database)
*   **LLMs:**
    *   **Reasoning:** Grok-3-mini Beta (via x.ai API using OpenAI SDK compatibility)
    *   **Plotting:** GPT-4o-mini (via OpenAI API)
*   **Containerization:**
    *   Docker
    *   Docker Compose

## Architecture Overview

The application uses a containerized microservice architecture orchestrated by Docker Compose:

1.  **`frontend` Service:** A React application providing the user interface. It communicates with the backend via WebSockets.
2.  **`backend` Service:** A Python FastAPI application handling WebSocket connections, processing user queries (using RAG, LLMs, Caching), and streaming structured responses back to the frontend. It connects to the Qdrant service.
3.  **`qdrant` Service:** A Qdrant vector database instance used for storing RAG context embeddings and semantic cache entries.

**(Diagram placeholder - A visual diagram would be ideally added here)**

## Project Structure
ebrahimabdelwahed-grok-stem/
├── readme.md
├── docker-compose.yml
├── LICENSE.md
├── backend/
│ ├── .env.example # Example environment variables
│ ├── Dockerfile
│ ├── requirements.txt
│ ├── config.py # Settings management
│ ├── main.py # FastAPI app, WebSocket endpoint
│ ├── schemas.py # Pydantic models for messages & data
│ ├── llm_clients.py # Initializes Grok & OpenAI clients
│ ├── qdrant_service.py # Initializes Qdrant client, connection helpers
│ ├── rag_utils.py # RAG search, semantic cache logic, embedding models
│ └── chat_logic.py # Core message processing pipeline
├── data_pipeline/
│ ├── create_collections.py # Script to setup Qdrant collections
│ ├── ingest_placeholder_data.py # Script to add sample RAG data
│ └── ingest_real_data.py # (TODO) Script for ingesting actual dataset
└── frontend/
├── Dockerfile
├── index.html
├── package.json
├── vite.config.ts
├── tailwind.config.js
├── postcss.config.js
├── tsconfig.json
└── src/
├── App.tsx # Main app component with routing & theme
├── main.tsx # Entry point
├── index.css # Global styles & Tailwind directives
├── components/ # UI components (custom & shadcn/ui)
├── context/ # React contexts (e.g., ThemeContext)
├── hooks/ # Custom React hooks (e.g., useScrollToBottom)
├── interfaces/ # TypeScript interfaces
├── lib/ # Utility functions (e.g., cn)
└── pages/ # Page components (LandingPage, ChatPage)


## Setup and Running the Application

**(Instructions placeholder - Detailed steps would be added here)**

1.  **Prerequisites:**
    *   Docker & Docker Compose installed.
    *   Git installed.
    *   API Keys (OpenAI, x.ai/Grok).

2.  **Clone the Repository:**
    ```bash
    git clone <repository-url>
    cd ebrahimabdelwahed-grok-stem
    ```

3.  **Configure Environment Variables:**
    *   Copy the example environment file: `cp backend/.env.example backend/.env`
    *   Edit `backend/.env` and fill in your `XAI_API_KEY`, `OPENAI_API_KEY`, and `XAI_BASE_URL`. Adjust other settings like `CORS_ALLOWED_ORIGINS` if necessary.

4.  **Build and Run with Docker Compose:**
    ```bash
    docker-compose up --build -d
    ```
    *   The `--build` flag ensures images are built initially or when Dockerfiles change.
    *   The `-d` flag runs the containers in detached mode.

5.  **Create Qdrant Collections and Ingest Data:**
    *   Once the containers are running (especially `qdrant` and `backend`), run the data pipeline scripts:
    ```bash
    docker-compose exec backend python data_pipeline/create_collections.py
    docker-compose exec backend python data_pipeline/ingest_placeholder_data.py
    # Optional: Run ingest_real_data.py when implemented
    # docker-compose exec backend python data_pipeline/ingest_real_data.py
    ```
    *   *Note:* The Sentence Transformer models will be downloaded by the `backend` container the first time `rag_utils.py` is imported (e.g., during script execution or app startup). This might take a few minutes.

6.  **Access the Frontend:**
    *   Open your web browser and navigate to `http://localhost:5173` (or the port mapped in `docker-compose.yml`).

7.  **Stopping the Application:**
    ```bash
    docker-compose down
    ```

## Development Notes

*   **Hot Reloading:** Both frontend and backend containers are configured with volume mounts for hot reloading during development. Changes in the `frontend/src` or `backend/` directories should trigger automatic rebuilds/restarts.
*   **Logs:** View logs using `docker-compose logs -f <service_name>` (e.g., `docker-compose logs -f backend`).
*   **Accessing Containers:** Use `docker-compose exec <service_name> bash` (e.g., `docker-compose exec backend bash`) to get a shell inside a running container.

## Future Enhancements (TODO)

*   Implement robust ingestion pipeline for a large STEM dataset (`ingest_real_data.py`).
*   Refine Grok API response parsing based on actual API behavior (`chat_logic.py`, `llm_clients.py`).
*   Enhance UI error display (`ChatPage.tsx`).
*   Add more sophisticated health checks (`main.py`).
*   Implement optional UI features (e.g., reasoning effort selector).
*   Add comprehensive unit and integration tests.