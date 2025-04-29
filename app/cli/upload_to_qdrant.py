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
import fitz
import typer
import uuid
from core.config import RAW_DATA_DIR

app = typer.Typer()

project_dir = os.path.join(os.path.dirname(__file__), os.pardir)
dotenv_path = os.path.join(project_dir, '.env')
dotenv.load_dotenv(dotenv_path)

raw_path = Path(RAW_DATA_DIR)

qdrant_key = os.getenv('QDRANT_CLOUD_KEY')
qdrant_url = os.getenv('QDRANT_CLOUD_URL')

env_var = ['QDRANT_CLOUD_KEY', 'QDRANT_CLOUD_URL']
missing_env = [var for var in env_var if os.getenv(var) is None]
if missing_env:
    logger.error(f"Missing enviroment variables : {', '.join(missing_env)}")
    raise SystemExit(1)

qdrant_client = QdrantClient(url=qdrant_url,
                        api_key=qdrant_key)

def extract_text_from_pdf(path: Path):
    try:
        with fitz.open(path) as doc:
            return "\n".join(page.get_text() for page in doc)
    except Exception as e:
        logger.error(f"Error during opening {path}: {e}")
        return None
    
def load_question_from_json(json_path: Path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [entry['text'] for entry in data if 'text' in entry]

def load_all_documents(folder: Path):
    texts = []
    for pdf in folder.glob("*.pdf"):
        text = extract_text_from_pdf(pdf)
        if text and text.strip():
            texts.append(text)

    for js in folder.glob("*.json"):
        try:
            questions = load_question_from_json(js)
            texts.extend(questions)
        except Exception as e:
            logger.warning(f"Could not load {js.name}: {e}")

    return texts

def prepare_points(documents, embeddings):
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

@app.command(help="Upload the database to Qdrant")
def main():
    model = SentenceTransformer('BAAI/bge-base-en-v1.5')

    documents = load_all_documents(raw_path)
    embeddings = model.encode(documents, show_progress_bar=True)

    points = prepare_points(documents, embeddings)

    qdrant_client.upload_points(collection_name='docs', points=points)

    logger.success(f"Uploaded {len(points)} documents to qdrant successfully.")

if __name__ == "__main__":
    app()