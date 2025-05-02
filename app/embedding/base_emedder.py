from abc import ABC, abstractmethod
from typing import List
from processing.text_chunk import TextChunk

class BaseEmbedder(ABC):
    @abstractmethod
    def embed(self, chunk: List[TextChunk]) -> List[dict]:
        """
        Return a list of dicts:
        {
            "id": chunk.chunk_id,
            "embedding": [float...],
            "metadata": {...},
            "text": chunk.text
        }
        """