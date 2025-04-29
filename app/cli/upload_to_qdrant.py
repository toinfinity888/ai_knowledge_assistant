from sentence_transformers import SentenceTransformer
import dotenv
import json
from loguru import logger
import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct 
import fitz  # PyMuPDF for reading PDF files
import typer
import uuid

from core.config import RAW_DATA_DIR

app = typer.Typer()

# Load environment variables from .env file
project_dir = os.path.join(os.path.dirname(__file__), os.pardir)
dotenv_path = os.path.join(project_dir, '.env')
dotenv.load_dotenv(dotenv_path)

raw_path = Path(RAW_DATA_DIR)

# Get required Qdrant credentials from environment
qdrant_key = os.getenv('QDRANT_CLOUD_KEY')
qdrant_url = os.getenv('QDRANT_CLOUD_URL')

# Validate that required environment variables exist
env_var = ['QDRANT_CLOUD_KEY', 'QDRANT_CLOUD_URL']
missing_env = [var for var in env_var if os.getenv(var) is None]
if missing_env:
    logger.error(f"Missing environment variables: {', '.join(missing_env)}")
    raise SystemExit(1)

# Initialize Qdrant client
qdrant_client = QdrantClient(
    url=qdrant_url,
    api_key=qdrant_key
)

def extract_text_from_pdf(path: Path) -> str | None:
    """
    Extract text content from a PDF file.
    Returns None if an error occurs.
    """
    try:
        with fitz.open(path) as doc:
            return "\n".join(page.get_text() for page in doc)
    except Exception as e:
        logger.error(f"Error opening {path}: {e}")
        return None
    
def load_question_from_json(json_path: Path) -> list[str]:
    """
    Load a list of question strings from a JSON file.
    Assumes each item in JSON is a dict with a 'text' field.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [entry['text'] for entry in data if 'text' in entry]

def load_all_documents(folder: Path) -> list[str]:
    """
    Load text content from all supported documents (PDF and JSON).
    Returns a list of text strings ready for embedding.
    """
    texts = []

    # Load text from PDF files
    for pdf in folder.glob("*.pdf"):
        text = extract_text_from_pdf(pdf)
        if text and text.strip():
            texts.append(text)

    # Load questions from JSON files
    for js in folder.glob("*.json"):
        try:
            questions = load_question_from_json(js)
            texts.extend(questions)
        except Exception as e:
            logger.warning(f"Could not load {js.name}: {e}")

    return texts

def prepare_points(documents: list[str], embeddings) -> list[PointStruct]:
    """
    Prepare PointStruct objects for uploading to Qdrant.
    Also (re)creates the 'docs' collection if it does not exist.
    """
    if not qdrant_client.collection_exists('docs'):
        qdrant_client.recreate_collection(
            collection_name='docs',
            vectors_config=VectorParams(size=embeddings.shape[1], distance=Distance.COSINE)
        )

    points = [
        PointStruct(
            id=uuid.uuid4().int >> 64,
            vector=vector.tolist(),
            payload={"text": doc},
        )
        for doc, vector in zip(documents, embeddings)
    ]
    return points

@app.command(help="Upload the document database to Qdrant Cloud")
def main():
    # Load embedding model
    model = SentenceTransformer('BAAI/bge-base-en-v1.5')

    # Load all documents (PDF + JSON)
    documents = load_all_documents(raw_path)

    if not documents:
        logger.warning("No documents found to embed.")
        raise SystemExit(0)

    # Generate embeddings
    embeddings = model.encode(documents, show_progress_bar=True)

    if len(embeddings) == 0:
        logger.warning("No embeddings were generated.")
        raise SystemExit(0)

    # Prepare and upload points to Qdrant
    points = prepare_points(documents, embeddings)
    qdrant_client.upload_points(collection_name='docs', points=points)

    logger.success(f"Uploaded {len(points)} documents to Qdrant successfully.")

if __name__ == "__main__":
    app()