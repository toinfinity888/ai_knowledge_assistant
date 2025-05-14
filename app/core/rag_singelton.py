from app.core.rag_engine import RAGEngine
from app.llm.llm_mistral import OllamaLlm
from app.vector_store.qdrant_vector_store import QdrantVectorStore
from app.embedding.sentence_transformer_embedder import SentenceTransformerEmbedder
from app.search.search_engine import SemanticSearchEngine
from app.config.app_config import config

embedder = SentenceTransformerEmbedder()
vector_store = QdrantVectorStore(config.qdrant)
search_engine = SemanticSearchEngine(embedder, vector_store)
llm = OllamaLlm()

rag_engine = RAGEngine(search_engine, llm)