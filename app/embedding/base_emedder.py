from abc import ABC, abstractmethod
from typing import List
from app.models.text_chunk import TextChunk
from sentence_transformers import SentenceTransformer
from app.models.query import Query
from app.models.embedded import EmbeddedQuery

class BaseEmbedder(ABC):
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)

    @abstractmethod
    def embed_text(self, chunk: List[TextChunk]) -> List[dict]:
        pass
    
    @abstractmethod
    def embed_query(self, query: Query) -> EmbeddedQuery:
        pass

    