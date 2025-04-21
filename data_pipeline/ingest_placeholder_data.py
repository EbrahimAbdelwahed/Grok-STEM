# data_pipeline/ingest_placeholder_data.py

import sys
import os
import logging
import uuid
import asyncio
from typing import List, Dict, Any

# Add backend directory to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from backend.config import settings
    from backend.qdrant_service import qdrant_client
    # Import the RAG encoder *directly* from rag_utils to generate embeddings
    from backend.rag_utils import rag_encoder, RAG_VECTOR_DIM
    from backend.schemas import DocumentToIngest # Use schema for structure
    from qdrant_client import models
    from qdrant_client.models import PointStruct
except ImportError as e:
    print(f"Error importing backend modules. Run from project root.")
    print(f"ImportError: {e}")
    sys.exit(1)
except AttributeError as e:
     print(f"Error accessing RAG encoder or dimension. Ensure rag_utils.py defines them and models loaded.")
     print(f"AttributeError: {e}")
     sys.exit(1)


logging.basicConfig(
    level=settings.LOG_LEVEL.upper(),
    format='%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Placeholder Data ---
# Simple examples covering different potential STEM topics
PLACEHOLDER_DOCUMENTS_DATA: List[Dict[str, Any]] = [
    {
        "id": str(uuid.uuid4()),
        "text_content": "Newton's second law of motion states that the acceleration of an object is directly proportional to the net force acting on it and inversely proportional to its mass. The formula is F = ma, where F is the net force, m is the mass, and a is the acceleration.",
        "metadata": {"domain": "Physics", "topic": "Mechanics", "source": "placeholder_physics_newton"},
    },
    {
        "id": str(uuid.uuid4()),
        "text_content": "Kinetic energy is the energy an object possesses due to its motion. It is calculated using the formula KE = 1/2 * m * v^2, where m is the mass of the object and v is its velocity.",
        "metadata": {"domain": "Physics", "topic": "Energy", "source": "placeholder_physics_energy"},
    },
    {
        "id": str(uuid.uuid4()),
        "text_content": "The ideal gas law relates the pressure (P), volume (V), number of moles (n), and temperature (T) of an ideal gas through the equation PV = nRT, where R is the ideal gas constant.",
        "metadata": {"domain": "Chemistry", "topic": "Gases", "source": "placeholder_chemistry_ideal_gas"},
    },
    {
        "id": str(uuid.uuid4()),
        "text_content": "The derivative of a function measures the sensitivity to change of the function value (output value) with respect to a change in its argument (input value). For f(x) = x^2, the derivative f'(x) = 2x.",
        "metadata": {"domain": "Mathematics", "topic": "Calculus", "source": "placeholder_math_calculus"},
    },
     {
        "id": str(uuid.uuid4()),
        "text_content": "Plotting a function like y = sin(x) involves calculating y for various x values within a given range and then drawing points (x, y) on a graph, often connecting them with a line.",
        "metadata": {"domain": "Mathematics", "topic": "Plotting", "source": "placeholder_math_plotting"},
    },
    {
        "id": str(uuid.uuid4()),
        "text_content": "Ohm's Law states that the current through a conductor between two points is directly proportional to the voltage across the two points and inversely proportional to the resistance between them. Formula: V = IR, where V is voltage, I is current, and R is resistance.",
        "metadata": {"domain": "Physics", "topic": "Electricity", "source": "placeholder_physics_ohm"},
    }
]

# Validate data against Pydantic model
PLACEHOLDER_DOCUMENTS: List[DocumentToIngest] = [DocumentToIngest(**doc) for doc in PLACEHOLDER_DOCUMENTS_DATA]

async def ingest_data():
    """Asynchronously ingests the placeholder documents into the Qdrant RAG collection."""
    if not qdrant_client or not rag_encoder or RAG_VECTOR_DIM is None:
        logger.error("Qdrant client, RAG encoder, or vector dimension not initialized. Cannot ingest data.")
        return

    collection_name = settings.QDRANT_RAG_COLLECTION
    logger.info(f"Starting ingestion of {len(PLACEHOLDER_DOCUMENTS)} placeholder documents into collection '{collection_name}'...")

    try:
        # Prepare data for Qdrant
        points_to_upsert: List[PointStruct] = []
        texts_to_embed: List[str] = [doc.text_content for doc in PLACEHOLDER_DOCUMENTS]

        logger.info(f"Generating embeddings for {len(texts_to_embed)} documents using '{settings.EMBEDDING_MODEL_NAME}'...")
        # Generate embeddings in batch (Sentence Transformers handles batching internally)
        embeddings = rag_encoder.encode(texts_to_embed, show_progress_bar=True) # Show progress for potentially longer operations
        logger.info("Embeddings generated.")

        for i, doc in enumerate(PLACEHOLDER_DOCUMENTS):
            # Ensure payload matches the RAGDocumentPayload schema (or just use dict directly)
            payload = {
                "text_content": doc.text_content,
                "metadata": doc.metadata
            }
            point = PointStruct(
                id=doc.id, # Use the pre-generated UUID
                vector=embeddings[i].tolist(), # Convert numpy array to list
                payload=payload
            )
            points_to_upsert.append(point)

        logger.info(f"Upserting {len(points_to_upsert)} points into Qdrant collection '{collection_name}'...")
        # Upsert points in batch using the async client
        await qdrant_client.upsert(
            collection_name=collection_name,
            points=points_to_upsert,
            wait=True # Wait for operation to complete for setup scripts
        )
        logger.info("Placeholder data ingestion complete.")

    except Exception as e:
        logger.error(f"Error during data ingestion: {e}", exc_info=True)

if __name__ == "__main__":
    # Optional: Add confirmation prompt
    # confirm = input(f"Ingest {len(PLACEHOLDER_DOCUMENTS)} placeholder documents into '{settings.QDRANT_RAG_COLLECTION}'? (y/N): ")
    # if confirm.lower() == 'y':
    #      asyncio.run(ingest_data())
    # else:
    #      print("Ingestion cancelled.")
    asyncio.run(ingest_data()) # Run directly for now