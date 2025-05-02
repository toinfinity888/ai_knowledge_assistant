from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime
from pathlib import Path
from qdrant_client.models import PointStruct

@dataclass
class EmbeddedChunk:
    id: str
    embedding: List[float]
    text: str
    file_name: str
    source: Path
    page: Optional[int]
    file_type: Optional[str]
    last_modified: Optional[datetime]
    text_hash: str

    def to_qdrant_point(self) -> PointStruct:
        payload = {
            "text": self.text,
            "file_name": self.file_name,
            "source": str(self.source),
            "page": self.page,
            "file_type": self.file_type,
            "last_modified": self.last_modeified.isoformat() if self.last_modified else None,
            "text_hash": self.text_hash
        }
        return PointStruct(
            id=self.id,
            vector=self.embedding,
            payload=payload
        )
        
