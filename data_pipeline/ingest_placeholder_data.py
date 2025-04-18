
# data_pipeline/ingest_placeholder_data.py

import sys
import os
import logging
import uuid

# Add backend directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from backend.config import settings
    from backend.qdrant_client import qdrant_client
    # Import the RAG encoder *directly* from rag_utils to generate embeddings
    from backend.rag_utils import rag_encoder, RAG_VECTOR_DIM
    from qdrant_client import models
    from qdrant_client.http.models import PointStruct
except ImportError as e:
    print(f"Error importing backend modules. Run from project root.")
    print(f"ImportError: {e}")
    sys.exit(1)
except AttributeError as e:
     print(f"Error accessing RAG encoder or dimension. Ensure rag_utils.py defines them.")
     print(f"AttributeError: {e}")
     sys.exit(1)


logging.basicConfig(level=settings.log_level.upper(), format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Placeholder Data ---
# Simple examples covering different potential STEM topics
PLACEHOLDER_DOCUMENTS = [
    {
        "id": str(uuid.uuid4()),
        "text_content": "Newton's second law of motion states that the acceleration of an object is directly proportional to the net force acting on it and inversely proportional to its mass. The formula is F = ma, where F is the net force, m is the mass, and a is the acceleration.",
        "metadata": {"domain": "Physics", "topic": "Mechanics", "source": "placeholder"},
    },
    {
        "id": str(uuid.uuid4()),
        "text_content": "Kinetic energy is the energy an object possesses due to its motion. It is calculated using the formula KE = 1/2 * m * v^2, where m is the mass of the object and v is its velocity.",
        "metadata": {"domain": "Physics", "topic": "Energy", "source": "placeholder"},
    },
    {
        "id": str(uuid.uuid4()),
        "text_content": "The ideal gas law relates the pressure (P), volume (V), number of moles (n), and temperature (T) of an ideal gas through the equation PV = nRT, where R is the ideal gas constant.",
        "metadata": {"domain": "Chemistry", "topic": "Gases", "source": "placeholder"},
    },
    {
        "id": str(uuid.uuid4()),
        "text_content": "The derivative of a function measures the sensitivity to change of the function value (output value) with respect to a change in its argument (input value). For f(x) = x^2, the derivative f'(x) = 2x.",
        "metadata": {"domain": "Mathematics", "topic": "Calculus", "source": "placeholder"},
    },
     {
        "id": str(uuid.uuid4()),
        "text_content": "Plotting a function like y = sin(x) involves calculating y for various x values within a given range and then drawing points (x, y) on a graph, often connecting them with a line.",
        "metadata": {"domain": "Mathematics", "topic": "Plotting", "source": "placeholder"},
    },
]

def ingest_data():
    """Ingests the placeholder documents into the Qdrant RAG collection."""
    if not qdrant_client or not rag_encoder:
        logger.error("Qdrant client or RAG encoder not initialized. Cannot ingest data.")
        return

    collection_name = settings.qdrant_rag_collection
    logger.info(f"Starting ingestion into collection '{collection_name}'...")

    try:
        # Prepare data for Qdrant
        points_to_upsert = []
        texts_to_embed = [doc["text_content"] for doc in PLACEHOLDER_DOCUMENTS]

        logger.info(f"Generating embeddings for {len(texts_to_embed)} documents...")
        # Generate embeddings in batch
        embeddings = rag_encoder.encode(texts_to_embed).tolist()
        logger.info("Embeddings generated.")

        for i, doc in enumerate(PLACEHOLDER_DOCUMENTS):
            point = PointStruct(
                id=doc["id"],
                vector=embeddings[i],
                payload={ # Payload contains the original text and metadata
                    "text_content": doc["text_content"],
                    "metadata": doc["metadata"]
                }
            )
            points_to_upsert.append(point)

        logger.info(f"Upserting {len(points_to_upsert)} points into Qdrant...")
        # Upsert points in batch
        qdrant_client.upsert(
            collection_name=collection_name,
            points=points_to_upsert,
            wait=True # Wait for operation to complete for setup scripts
        )
        logger.info("Ingestion complete.")

    except Exception as e:
        logger.error(f"Error during data ingestion: {e}", exc_info=True)

if __name__ == "__main__":
    # Optional: Add a check or prompt before running to avoid accidental re-ingestion
    # confirm = input(f"Ingest placeholder data into '{settings.qdrant_rag_collection}'? (y/N): ")
    # if confirm.lower() == 'y':
    #     ingest_data()
    # else:
    #     print("Ingestion cancelled.")
    ingest_data() # Run directly for now