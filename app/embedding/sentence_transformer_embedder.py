from sentence_transformers import SentenceTransformer
from processing.text_chunk import TextChunk
from embedding.embedded import EmbeddedChunk
from embedding.base_emedder import BaseEmbedder
from typing import List
from search.query import Query
from embedding.embedded import EmbeddedQuery

class SentenceTransformerEmbedderForText(BaseEmbedder):
    def embed(self, chunks: List[TextChunk]) -> List[EmbeddedChunk]:
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
                text_hash=chunk.text_hash
            ))
        return embedded
    
class SentenceTransformerEmbedderForQuery(BaseEmbedder):
    def embed(self, query: Query) -> EmbeddedQuery:
        text = query.text
        vector = self.model.encode(text, show_progress_bar=True)
        return EmbeddedQuery(query=query, embedding=vector)