from pathlib import Path
from app.loaders.pdf_loader import PDFLoader
from app.loaders.json_loader import JsonLoader
from app.embedding.sentence_transformer_embedder import SentenceTransformerEmbedder
from app.models.embedded import EmbeddedChunk
from app.models.text_chunk import TextChunk
from app.vector_store.qdrant_vector_store import QdrantVectorStore
from app.logging.logger import logger
from app.config.path_config import RAW_DATA_DIR
from app.config.qdrant_config import QdrantSetting

path_raw = Path(RAW_DATA_DIR)
embedder = SentenceTransformerEmbedder()
vector_store = QdrantVectorStore(QdrantSetting())
pdf_loader = PDFLoader()
json_loader = JsonLoader()

def load_files(path: Path):
    text_chunks = pdf_loader.load(path) + json_loader.load(path)
    embedded_chunks = embedder.embed_text(text_chunks)
    return embedded_chunks

embed_chunks = load_files(path_raw)
vector_store.upsert(embed_chunks)

    

