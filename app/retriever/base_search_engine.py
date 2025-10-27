from abc import ABC, abstractmethod
from typing import List
from app.models.text_chunk_for_mvp import TextChunkForMvp

class BaseSearchEngine(ABC):
    @abstractmethod
    async def search(self, query: str) -> List[TextChunkForMvp]:
        pass