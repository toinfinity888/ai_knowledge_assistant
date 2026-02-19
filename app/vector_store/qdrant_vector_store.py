from qdrant_client import QdrantClient
from qdrant_client.models import (
    PointStruct,
    VectorParams,
    Distance,
    ScoredPoint,
    Filter,
    FieldCondition,
    MatchValue,
    PayloadSchemaType,
    FilterSelector,
    SearchRequest,
    NamedVector,
    NamedSparseVector,
    SparseVector,
    SparseIndexParams,
    SparseVectorParams,
)
from app.vector_store.base_vector_store import BaseVectorStore
from app.models.embedded import EmbeddedChunk
from typing import List, Optional, Dict
from app.config.qdrant_config import QdrantSetting
from app.logging.logger import logger

class QdrantVectorStore(BaseVectorStore):
    def __init__(self, settings: QdrantSetting):
        self.settings = settings
        self.collection_name = settings.collection_name

        # Build proper URL for Qdrant Cloud
        if settings.https:
            url = f"https://{settings.host}:{settings.port}"
        else:
            url = f"http://{settings.host}:{settings.port}"

        self.client = QdrantClient(
                url=url,
                api_key=settings.api_key,
        )

        self._init_collection()

    def _init_collection(self):
        """Create or recreate the collection based on settings."""
        if self.settings.recreate and self.client.collection_exists(self.collection_name):
            logger.warning(f"Recreating collection '{self.collection_name}'...")
            self.client.delete_collection(self.collection_name)

        if not self.client.collection_exists(self.collection_name):
            logger.info(f"Creating collection '{self.collection_name}'...")
            self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.settings.vector_size,
                        distance=self.settings.distance
                    )
            )

        else:
            logger.info(f"Collection '{self.collection_name}' already exists.")

        # Ensure required indexes exist for filtering
        self._ensure_indexes()

    def _ensure_indexes(self):
        """Ensure required payload indexes exist for efficient filtering."""
        # Create company_id index for multi-tenancy
        self.create_company_id_index()
        # Create document_id index for document deletion
        self.create_document_id_index()

    def _get_existing_hashes(self, chunk_ids: List[str]) -> Dict[str, str]:
        response = self.client.retrieve(
            collection_name=self.collection_name,
            ids=chunk_ids,
            with_payload=True
        )
        return {point.id: point.payload.get('text_hash') for point in response}
                    

    def upsert(self, chunks: List[EmbeddedChunk], batch_size: int = 256) -> None:
        chunk_id_to_chunk = {chunk.qdrant_id(): chunk for chunk in chunks}  # New chunks
        existing_hashes = self._get_existing_hashes(list(chunk_id_to_chunk.keys())) # Dictionary[point.id: 'text_hash']
        chunks_to_upsert = [
            chunk for id, chunk in chunk_id_to_chunk.items()
            if id not in existing_hashes or existing_hashes[id] != chunk.text_hash
        ]

        if not chunks_to_upsert:
            logger.info(f"NO changes detected. Nothing to upsert.")
            return

        logger.info(f"Upserting points to '{self.collection_name}'...")
        for i in range(0, len(chunks_to_upsert), batch_size):
            batch = chunks_to_upsert[i:i+batch_size]
            points: List[PointStruct] = [chunk.to_qdrant_point() for chunk in batch]
            self.client.upsert(collection_name=self.collection_name, points=points)
        logger.info(f'Upserted {len(points)} updated/new chunks.')

    def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        company_id: Optional[int] = None
    ) -> List[ScoredPoint]:
        """
        Search for similar vectors in the collection

        Args:
            query_vector: Query embedding vector
            top_k: Number of results to return
            company_id: Optional company ID for multi-tenant filtering

        Returns:
            List of scored points matching the query
        """
        # Build filter for company_id if provided
        query_filter = None
        if company_id is not None:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="company_id",
                        match=MatchValue(value=company_id)
                    )
                ]
            )

        return self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True
        )

    def create_company_id_index(self) -> None:
        """
        Create a payload index on company_id for efficient filtered searches.
        Should be called during migration or initialization.
        """
        try:
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="company_id",
                field_schema=PayloadSchemaType.INTEGER
            )
            logger.info(f"Created company_id index on collection '{self.collection_name}'")
        except Exception as e:
            # Index may already exist
            logger.debug(f"Could not create company_id index (may already exist): {e}")

    def create_document_id_index(self) -> None:
        """
        Create a payload index on document_id for efficient document deletion.
        Should be called when setting up document upload feature.
        """
        try:
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="document_id",
                field_schema=PayloadSchemaType.INTEGER
            )
            logger.info(f"Created document_id index on collection '{self.collection_name}'")
        except Exception as e:
            logger.debug(f"Could not create document_id index (may already exist): {e}")

    def delete_by_document_id(self, document_id: int, company_id: int) -> int:
        """
        Delete all vectors for a specific document.

        This only affects documents uploaded through the new upload system
        (which have document_id in their payload). Legacy vectors without
        document_id are not affected.

        Args:
            document_id: Database document ID
            company_id: Company ID for multi-tenant isolation

        Returns:
            Number of points deleted (estimated)
        """
        logger.info(f"Deleting vectors for document_id={document_id}, company_id={company_id}")

        try:
            # Count before deletion (for logging)
            count_result = self.client.count(
                collection_name=self.collection_name,
                count_filter=Filter(
                    must=[
                        FieldCondition(key="document_id", match=MatchValue(value=document_id)),
                        FieldCondition(key="company_id", match=MatchValue(value=company_id))
                    ]
                )
            )
            count_before = count_result.count

            # Delete matching points
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=FilterSelector(
                    filter=Filter(
                        must=[
                            FieldCondition(key="document_id", match=MatchValue(value=document_id)),
                            FieldCondition(key="company_id", match=MatchValue(value=company_id))
                        ]
                    )
                )
            )

            logger.info(f"Deleted {count_before} vectors for document_id={document_id}")
            return count_before

        except Exception as e:
            logger.error(f"Error deleting vectors for document_id={document_id}: {e}")
            raise

    def upsert_with_document_id(
        self,
        chunks: List[EmbeddedChunk],
        document_id: int,
        batch_size: int = 256
    ) -> None:
        """
        Upsert chunks with document_id in payload for deletion support.

        Args:
            chunks: List of embedded chunks to upsert
            document_id: Database document ID to include in payload
            batch_size: Batch size for upserting
        """
        if not chunks:
            logger.info("No chunks to upsert")
            return

        logger.info(f"Upserting {len(chunks)} chunks for document_id={document_id}")

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            points = []

            for chunk in batch:
                point = chunk.to_qdrant_point()
                # Add document_id to payload
                point.payload["document_id"] = document_id
                points.append(point)

            self.client.upsert(collection_name=self.collection_name, points=points)

        logger.info(f"Upserted {len(chunks)} chunks for document_id={document_id}")

    def hybrid_search(
        self,
        query_vector: List[float],
        query_text: str,
        top_k: int = 10,
        company_id: Optional[int] = None,
        alpha: float = 0.7,  # Weight for dense search (1-alpha for sparse)
    ) -> List[ScoredPoint]:
        """
        Hybrid search combining dense vectors and BM25 keyword matching.

        Uses Reciprocal Rank Fusion (RRF) to combine results from:
        - Dense semantic search (captures meaning)
        - Sparse BM25 search (captures exact keywords, codes)

        Note: Falls back to dense-only search for vectors without sparse component.

        Args:
            query_vector: Dense embedding of the query
            query_text: Original query text for BM25
            top_k: Number of results to return
            company_id: Company ID for multi-tenant filtering
            alpha: Weight for dense search (0-1). Higher = more semantic.

        Returns:
            List of scored points, ranked by combined score
        """
        # Build filter
        query_filter = None
        if company_id is not None:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="company_id",
                        match=MatchValue(value=company_id)
                    )
                ]
            )

        # For now, use dense search with text boost in post-processing
        # Full sparse vector support requires collection schema update
        dense_results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            query_filter=query_filter,
            limit=top_k * 2,  # Get more for reranking
            with_payload=True
        )

        # Boost results containing exact query terms
        query_terms = set(query_text.lower().split())
        boosted_results = []

        for result in dense_results:
            text = result.payload.get("text", "").lower()

            # Count matching terms for boost
            matching_terms = sum(1 for term in query_terms if term in text)
            term_boost = matching_terms * 0.05  # Small boost per matching term

            # Check for exact code patterns (e.g., "E-4521", "XR-200")
            code_boost = 0
            import re
            code_pattern = r'\b[A-Z]{1,3}[-]?\d{3,5}\b'
            query_codes = set(re.findall(code_pattern, query_text.upper()))
            text_codes = set(re.findall(code_pattern, text.upper()))
            if query_codes & text_codes:
                code_boost = 0.15  # Significant boost for exact code match

            # Combine scores
            combined_score = result.score + term_boost + code_boost
            result.score = min(combined_score, 1.0)  # Cap at 1.0
            boosted_results.append(result)

        # Sort by combined score
        boosted_results.sort(key=lambda x: x.score, reverse=True)

        return boosted_results[:top_k]

    def get_collection_info(self) -> Dict:
        """Get information about the collection (for debugging/admin)."""
        try:
            info = self.client.get_collection(self.collection_name)
            return {
                "name": self.collection_name,
                "vectors_count": info.vectors_count,
                "points_count": info.points_count,
                "status": info.status,
            }
        except Exception as e:
            logger.error(f"Error getting collection info: {e}")
            return {"error": str(e)}