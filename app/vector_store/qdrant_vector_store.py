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