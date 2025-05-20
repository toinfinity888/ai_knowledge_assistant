from app.retriever.base_search_engine import BaseSearchEngine
from app.logging.logger import logger
from app.embedding.base_emedder import BaseEmbedder
from app.models.embedded import EmbeddedChunk
from app.models.embedded import EmbeddedQuery
from app.vector_store.qdrant_vector_store import QdrantVectorStore
from app.vector_store.base_vector_store import BaseVectorStore
from app.models.query import Query
from typing import List, Optional
from datetime import datetime

def create_query(
        text: str,
        filters: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        mode: Optional[str] = 'default',
        timestamp: Optional[datetime] = None,
) -> Query:
    return Query(
        text=text.strip(),
        filters=filters,
        user_id=user_id,
        mode=mode,
        timestamp=timestamp or datetime.utcnow()
    )

class SemanticSearchEngine(BaseSearchEngine):
    def __init__(self, embedder: BaseEmbedder, vector_store: BaseVectorStore, retriever_name: str='SemanticSearch'):
        self.embedder = embedder
        self.vector_store = vector_store
        self.retriever_name = retriever_name

    def search(self, query: Query) -> List[EmbeddedChunk]:
        vector = self.embedder.embed_query(query).embedding # Take embedding from embed_query object
        resoult = self.vector_store.search(vector)
        if not resoult:
            logger.info('No found anything')
        return [EmbeddedChunk.from_point(p) for p in resoult]

