from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance, ScoredPoint
from vector_store.base_vector_store import BaseVectorStore
from ai_knowledge_assistant.app.embedding.embedded import EmbeddedChunk
from typing import List, Optional
from config.qdrant_config import QdrantSetting
from core.logger import logger

class QdrantVectorStore(BaseVectorStore):
    def __init__(self, settings: QdrantSetting):
        self.settings = settings
        self.collection_name = settings.qdrant_collection_name

        self.client = QdrantClient(
                host=settings.qdrant_host,
                port=settings.qdrant_port,
                api_key=settings.qdrant_api_key,
                https=settings.qdrant_https,
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
                        size=self.settings.qdrant_vector_size,
                        distance=self.settings.qdrant_distance
                    )
            )

        else:
            logger.info(f"Collection '{self.collection_name}' already exists.")

    def _get_existing_hashes(self, chunk_ids: List[str]) -> List[str, str]:
        response = self.client.retrieve(
            collection_name=self.collection_name,
            ids=chunk_ids,
            with_payload=True
        )
        return{point.id: point.payload.get('text_hash') for point in response}
                    

    def upsert(self, chunks: List[EmbeddedChunk]) -> None:
        chunk_id_to_chunk = {chunks.chunk_id: chunk for chunk in chunks}  # New chunks
        existing_hashes = self._get_existing_hashes(list(chunk_id_to_chunk.keys())) # Dictionary[point.id: 'text_hash']
        chunks_to_upsert = [
            chunk for chunk_id, chunk in chunk_id_to_chunk.items()
            if chunk_id not in existing_hashes or existing_hashes[chunk_id] != chunk.text_hash
        ]

        if not chunks_to_upsert is None:
            logger.info(f"NO changes detected. Nothing to upsert.")
            return

        points: List[PointStruct] = [chunk.to_qdrant_point() for chunk in chunks_to_upsert]
        logger.info(f"Upserting {len(points)} points to '{self.collection_name}'...")
        self.client.upsert(collection_name=self.collection_name, points=points)
        logger.info(f'Upserted {len(points)} updated/new chunks.')

    def search(self, query_vector: List[float], top_k: int = 5) -> List[ScoredPoint]:
        return self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=top_k,
            with_payload=True
        ) 