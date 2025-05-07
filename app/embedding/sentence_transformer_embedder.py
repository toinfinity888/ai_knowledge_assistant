from sentence_transformers import SentenceTransformer
from app.processing.text_chunk import TextChunk
from app.embedding.embedded import EmbeddedChunk
from app.embedding.base_emedder import BaseEmbedder
from typing import List
from app.query.query import Query
from app.embedding.embedded import EmbeddedQuery

class SentenceTransformerEmbedder(BaseEmbedder):
    def embed_text(self, chunks: List[TextChunk]) -> List[EmbeddedChunk]:
        texts = [chunk.text for chunk in chunks]
        vectors = self.model.encode(texts, show_progress_bar=True)

        embedded = []
        for chunk, vector in zip(chunks, vectors):
            embedded.append(EmbeddedChunk(
                id=chunk.chunk_id,
                embedding=vector,
                text=chunk.text,
                file_name=chunk.file_name,
                source=chunk.source,
                page=chunk.page,
                file_type=chunk.file_type,
                last_modified=chunk.last_modified,
                text_hash=chunk.text_hash,
                score=chunk.score
            ))
        return embedded
    
    def embed_query(self, query: Query) -> EmbeddedQuery:
        text = query.text
        vector = self.model.encode(text, show_progress_bar=True)
        return EmbeddedQuery(query=query, embedding=vector)