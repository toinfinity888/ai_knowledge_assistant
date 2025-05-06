from search.base_search_engine import BaseSearchEngine
from core.logger import logger
from embedding.base_emedder import BaseEmbedder
from embedding.embedded_chunk import EmbeddedChunk
from vector_store.qdrant_vector_store import QdrantVectorStore
from search.query import Query
from typing import List, Optional
from datetime import datetime

def creat_query(
        text: str,
        filters: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        mode: Optional[str] = 'default',
        timestamp: Optional[datetime] = None,
) -> Query:
    return Query(
        text=text.strip(),
        filters=filters,
        user_id=user_id
        mode=mode,
        timestamp=timestamp= or datetime.utcnow()
    )