from abc import ABC, abstractmethod
from typing import List
from processing.text_chunk import TextChunk

class BaseSearchEngine(ABC):
    @abstractmethod
    async def search(self, query: str) -> List[TextChunk]:
        pass