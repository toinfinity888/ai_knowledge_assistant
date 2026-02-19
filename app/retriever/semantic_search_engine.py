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

    def search(
        self,
        query: Query,
        company_id: Optional[int] = None,
        top_k: int = 5
    ) -> List[EmbeddedChunk]:
        """
        Search for relevant documents based on query

        Args:
            query: Query object containing search text
            company_id: Optional company ID for multi-tenant filtering
            top_k: Number of results to return

        Returns:
            List of embedded chunks matching the query
        """
        vector = self.embedder.embed_query(query).embedding  # Take embedding from embed_query object
        result = self.vector_store.search(vector, top_k=top_k, company_id=company_id)
        if not result:
            logger.info('No found anything')
        return [EmbeddedChunk.from_point(p) for p in result]

    def hybrid_search(
        self,
        query: Query,
        company_id: Optional[int] = None,
        top_k: int = 10,
        alpha: float = 0.7,
    ) -> List[EmbeddedChunk]:
        """
        Hybrid search combining semantic and keyword matching.

        This is particularly useful for queries containing:
        - Product codes (e.g., "XR-200")
        - Error codes (e.g., "E-4521")
        - Serial numbers
        - Exact technical terms

        Args:
            query: Query object containing search text
            company_id: Company ID for multi-tenant filtering
            top_k: Number of results to return
            alpha: Weight for semantic search (1-alpha for keyword)

        Returns:
            List of embedded chunks ranked by combined score
        """
        vector = self.embedder.embed_query(query).embedding

        # Check if vector store supports hybrid search
        if hasattr(self.vector_store, 'hybrid_search'):
            result = self.vector_store.hybrid_search(
                query_vector=vector,
                query_text=query.text,
                top_k=top_k,
                company_id=company_id,
                alpha=alpha
            )
        else:
            # Fallback to regular search
            result = self.vector_store.search(vector, top_k=top_k, company_id=company_id)

        if not result:
            logger.info('No results found for hybrid search')
        return [EmbeddedChunk.from_point(p) for p in result]

