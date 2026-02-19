from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime
from pathlib import Path
from qdrant_client.models import PointStruct, ScoredPoint
from app.models.query import Query
from uuid import uuid5, NAMESPACE_DNS
from app.models.text_chunk_for_mvp import TextChunkForMvp

@dataclass
class EmbeddedChunk:
    id: str
    embedding: List[float]
    text: str
    source: Path
    file_name: Optional[str] = None
    page: Optional[int] = None
    file_type: Optional[str] = None
    last_modified: Optional[datetime] = None
    text_hash: Optional[str] = None
    company_id: Optional[int] = None  # Multi-tenant isolation
    document_id: Optional[int] = None  # For document deletion support

    def qdrant_id(self) -> str:
        return str(uuid5(NAMESPACE_DNS, self.id))

    def to_qdrant_point(self) -> PointStruct:
        qdrant_id = str(uuid5(NAMESPACE_DNS, self.id))
        payload = {
            "chunk_id": self.id,
            "text": self.text,
            "file_name": self.file_name,
            "source": str(self.source),
            "page": self.page,
            "file_type": self.file_type,
            "last_modified": self.last_modified.isoformat() if self.last_modified else None,
            "text_hash": self.text_hash,
        }
        # Add company_id if present (for multi-tenancy)
        if self.company_id is not None:
            payload["company_id"] = self.company_id
        # Add document_id if present (for deletion support)
        if self.document_id is not None:
            payload["document_id"] = self.document_id
        return PointStruct(
            id=qdrant_id,
            vector=self.embedding,
            payload=payload
        )
    
    @classmethod
    def from_point(cls, point: ScoredPoint) -> TextChunkForMvp:
        payload = point.payload or {}

        # Extract text content
        # Support multiple field names for text content
        if "posts" in payload:
            text = str(payload["posts"])
        elif "content" in payload:
            text = payload["content"]
        elif "text" in payload:
            text = payload["text"]
        elif "abstract" in payload:
            text = payload["abstract"]
        else:
            text = ""

        # Extract metadata from payload
        # Support both new format (file_name) and legacy format (title)
        file_name = payload.get("file_name") or payload.get("title")
        source = Path(payload["source"]) if payload.get("source") else None
        page = payload.get("page")
        chunk_id = payload.get("chunk_id")
        file_type = payload.get("file_type")

        # Get score from the ScoredPoint
        score = point.score if hasattr(point, 'score') else None

        return TextChunkForMvp(
            text=text,
            file_name=file_name,
            source=source,
            page=page,
            chunk_id=chunk_id,
            file_type=file_type,
            score=score,
        )
        
@dataclass
class EmbeddedQuery:
    query: Query
    embedding: List[float]
        
