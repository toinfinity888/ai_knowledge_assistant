from abc import ABC, abstractmethod
from typing import List
from embedding.embedded_chunk import EmbeddedChunk

class BaseVectorStore(ABC):
    @abstractmethod
    def upsert(self, chunks: List[EmbeddedChunk]) -> None:
        """Upserting of points to collection"""
        pass