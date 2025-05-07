from abc import ABC, abstractmethod
from pathlib import Path
from typing import List
from app.processing.text_chunk import TextChunk

class BaseLoader(ABC):
    @abstractmethod
    def load(self, path: Path) -> List[TextChunk]:
        """Load document and return a list of chunks"""
        pass