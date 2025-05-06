from abc import ABC, abstractmethod
from typing import List
from processing.text_chunk import TextChunk
from sentence_transformers import SentenceTransformer

class BaseEmbedder(ABC):
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)

    @abstractmethod
    def embed(self, chunk: List[TextChunk]) -> List[dict]:
        pass