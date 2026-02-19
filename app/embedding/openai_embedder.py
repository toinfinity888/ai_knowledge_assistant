"""OpenAI Embedder using text-embedding-3-large model."""
from typing import List
from openai import OpenAI

from app.embedding.base_emedder import BaseEmbedder
from app.models.text_chunk import TextChunk
from app.models.embedded import EmbeddedChunk, EmbeddedQuery
from app.models.query import Query
from app.config.openai_config import OpenAISetting


class OpenAIEmbedder(BaseEmbedder):
    """
    OpenAI-based embedder using the text-embedding-3-large model.

    Uses the OpenAI API to generate embeddings for text chunks and queries.
    """

    def __init__(self, settings: OpenAISetting = None):
        """
        Initialize the embedder.

        Args:
            settings: OpenAI configuration settings
        """
        if settings is None:
            settings = OpenAISetting()

        self.settings = settings
        self.client = OpenAI(api_key=settings.api_key)
        self.model_name = settings.embedding_model

    def embed_text(self, chunks: List[TextChunk]) -> List[EmbeddedChunk]:
        """
        Embed a list of text chunks.

        Args:
            chunks: List of TextChunk objects to embed

        Returns:
            List of EmbeddedChunk objects with embeddings
        """
        if not chunks:
            return []

        texts = [chunk.text for chunk in chunks]

        response = self.client.embeddings.create(
            input=texts,
            model=self.model_name
        )

        embedded = []
        for i, (chunk, vec_data) in enumerate(zip(chunks, response.data)):
            embedded.append(EmbeddedChunk(
                id=chunk.chunk_id if chunk.chunk_id else f"chunk_{i}",
                embedding=vec_data.embedding,
                text=chunk.text,
                source=chunk.source
            ))

        return embedded

    def embed_query(self, query: Query) -> EmbeddedQuery:
        """
        Embed a query.

        Args:
            query: Query object to embed

        Returns:
            EmbeddedQuery with the embedding vector
        """
        response = self.client.embeddings.create(
            input=query.text,
            model=self.model_name
        )

        vector = response.data[0].embedding
        return EmbeddedQuery(query=query, embedding=vector)

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a list of raw text strings.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        response = self.client.embeddings.create(
            input=texts,
            model=self.model_name
        )

        return [data.embedding for data in response.data]
