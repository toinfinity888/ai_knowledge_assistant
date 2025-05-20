from abc import ABC, abstractmethod
from typing import List
from app.models.embedded import EmbeddedChunk
from app.models.query import Query
from qdrant_client.models import ScoredPoint

class BaseVectorStore(ABC):
    @abstractmethod
    def upsert(self, chunks: List[EmbeddedChunk]) -> None:
        """Upserting of points to collection"""
        pass
    
    @abstractmethod
    def search(self, query_vector: List[float], top_k: int) -> List[ScoredPoint]:
        pass