from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime
from pathlib import Path
from qdrant_client.models import PointStruct, ScoredPoint
from search.query import Query

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
    score: Optional[float]

    def to_qdrant_point(self) -> PointStruct:
        payload = {
            "text": self.text,
            "file_name": self.file_name,
            "source": str(self.source),
            "page": self.page,
            "file_type": self.file_type,
            "last_modified": self.last_modeified.isoformat() if self.last_modified else None,
            "text_hash": self.text_hash,
        }
        return PointStruct(
            id=self.id,
            vector=self.embedding,
            payload=payload
        )
    
    @classmethod
    def from_point(cls, point: ScoredPoint) -> "EmbeddedChunk":
        payload = point.payload or {}

        return cls(
            id=point.id,
            embedding=point.vector,
            text=payload.get('text', ''),
            file_name=payload.get('file_name'),
            source=payload.get('source'),
            page=payload.get('page'),
            file_type=payload.get('file_type'),
            last_modified=payload.get('last_modified'),
            text_hash=payload.get('text_hash'),
            score=payload.get('score')
        )
    
@dataclass
class EmbeddedQuery:
    query: Query
    embedding: List[float]
        
