# data_pipeline/ingest_real_data.py

import sys
import os
import logging
import uuid
import asyncio
from typing import List, Dict, Any, Generator
from datasets import load_dataset # Example library for loading HF datasets
from qdrant_client import models

# Add backend directory to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from backend.config import settings
    from backend.qdrant_service import qdrant_client
    from backend.rag_utils import rag_encoder, RAG_VECTOR_DIM
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

# --- Configuration ---
# Hugging Face dataset name (e.g., the SCP-116K dataset mentioned)
DATASET_NAME = "EricLu/SCP-116K"
# Which split to use (e.g., 'train', 'test') - check dataset structure
DATASET_SPLIT = "train"
# Field containing the text content in the dataset
TEXT_FIELD = "content" # Adjust based on dataset inspection (might be 'text', 'document', etc.)
# Optional: Field containing metadata (if available)
METADATA_FIELDS = ["discipline", "subdiscipline", "id"] # Example fields, adjust based on dataset
# Batch size for embedding generation and Qdrant upsert
BATCH_SIZE = 64 # Adjust based on available memory and desired speed
# Max documents to ingest (set to None for all)
MAX_DOCUMENTS_TO_INGEST = None # Or e.g., 10000 for testing

# --- Helper Functions ---

def preprocess_text(text: str) -> str:
    """Basic text cleaning (add more steps as needed)."""
    if not isinstance(text, str):
        return ""
    # Example: Remove excessive whitespace
    text = ' '.join(text.split())
    # Add more cleaning steps: remove specific characters, normalize case, etc.
    return text.strip()

def chunk_text(text: str, chunk_size: int = 512, overlap: int = 64) -> List[str]:
    """
    Simple text chunking strategy (consider more advanced methods like recursive splitting).
    This basic version just splits by tokens/words which might not be ideal.
    """
    # This is a very basic example. Using libraries like Langchain's text_splitters
    # or sentence-transformers' own utils might be better.
    words = text.split()
    if len(words) <= chunk_size:
        return [text]

    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk_words = words[i : i + chunk_size]
        chunks.append(" ".join(chunk_words))
    return chunks

def yield_batches(data_generator: Generator[Dict[str, Any], None, None], batch_size: int) -> Generator[List[Dict[str, Any]], None, None]:
    """Yields batches of items from a generator."""
    batch = []
    for item in data_generator:
        batch.append(item)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch: # Yield any remaining items
        yield batch

# --- Main Ingestion Logic ---

async def ingest_real_data():
    """Loads, preprocesses, embeds, and upserts data into Qdrant."""
    if not qdrant_client or not rag_encoder or RAG_VECTOR_DIM is None:
        logger.error("Qdrant client, RAG encoder, or vector dimension not initialized. Cannot ingest data.")
        return

    collection_name = settings.QDRANT_RAG_COLLECTION
    logger.info(f"Starting ingestion of real data from '{DATASET_NAME}' into collection '{collection_name}'...")

    try:
        logger.info(f"Loading dataset '{DATASET_NAME}', split '{DATASET_SPLIT}'...")
        # Use streaming=True for large datasets to avoid loading all into memory
        dataset = load_dataset(DATASET_NAME, split=DATASET_SPLIT, streaming=True)
        logger.info("Dataset loaded.")

        processed_count = 0

        # Define a generator for processed documents
        def process_documents_generator():
            nonlocal processed_count
            for doc in dataset:
                if MAX_DOCUMENTS_TO_INGEST is not None and processed_count >= MAX_DOCUMENTS_TO_INGEST:
                    logger.info(f"Reached MAX_DOCUMENTS_TO_INGEST limit ({MAX_DOCUMENTS_TO_INGEST}). Stopping.")
                    break

                raw_text = doc.get(TEXT_FIELD)
                if not raw_text or not isinstance(raw_text, str):
                    logger.warning(f"Skipping document due to missing or invalid text field: {doc.get('id', 'Unknown ID')}")
                    continue

                processed_text = preprocess_text(raw_text)
                if not processed_text:
                     logger.warning(f"Skipping document after preprocessing yielded empty text: {doc.get('id', 'Unknown ID')}")
                     continue

                # --- Text Chunking (Optional but recommended) ---
                # text_chunks = chunk_text(processed_text) # Use chunking if needed
                text_chunks = [processed_text] # No chunking for now

                for i, chunk in enumerate(text_chunks):
                    doc_id = str(doc.get('id', uuid.uuid4())) # Use dataset ID if available
                    point_id = f"{doc_id}_chunk_{i}" if len(text_chunks) > 1 else doc_id

                    metadata = {
                        "original_doc_id": doc_id,
                        "chunk_index": i if len(text_chunks) > 1 else 0,
                        "source_dataset": DATASET_NAME,
                    }
                    # Add other metadata fields if they exist
                    for field in METADATA_FIELDS:
                         if field in doc and doc[field] is not None:
                              metadata[field] = doc[field]

                    yield {
                        "id": point_id,
                        "text_content": chunk,
                        "metadata": metadata
                    }
                    processed_count += 1
                    if processed_count % 1000 == 0: # Log progress periodically
                         logger.info(f"Processed {processed_count} document chunks...")


        # Process and upsert in batches
        for batch in yield_batches(process_documents_generator(), BATCH_SIZE):
            if not batch: break # Stop if the generator is exhausted

            logger.debug(f"Processing batch of {len(batch)} chunks...")
            texts = [item["text_content"] for item in batch]
            embeddings = rag_encoder.encode(texts, show_progress_bar=False) # No progress bar for inner loop

            points_to_upsert = [
                models.PointStruct(
                    id=item["id"],
                    vector=embeddings[j].tolist(),
                    payload={"text_content": item["text_content"], "metadata": item["metadata"]}
                ) for j, item in enumerate(batch)
            ]

            try:
                await qdrant_client.upsert(
                    collection_name=collection_name,
                    points=points_to_upsert,
                    wait=False # Upsert asynchronously for better performance
                )
                logger.debug(f"Upserted batch of {len(points_to_upsert)} points.")
            except Exception as upsert_err:
                 logger.error(f"Failed to upsert batch: {upsert_err}", exc_info=True)
                 # Optional: Add retry logic here

        logger.info(f"Finished ingestion. Total chunks processed: {processed_count}")

    except Exception as e:
        logger.error(f"Error during real data ingestion: {e}", exc_info=True)

if __name__ == "__main__":
    # Optional: Confirmation prompt
    # confirm = input(f"Ingest data from '{DATASET_NAME}' into '{settings.QDRANT_RAG_COLLECTION}'? This may take time and resources. (y/N): ")
    # if confirm.lower() == 'y':
    #      asyncio.run(ingest_real_data())
    # else:
    #      print("Ingestion cancelled.")
    logger.warning("Running real data ingestion. Ensure the target dataset is appropriate and you have sufficient resources.")
    asyncio.run(ingest_real_data())