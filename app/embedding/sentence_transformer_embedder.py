from sentence_transformers import SentenceTransformer
from processing.text_chunk import TextChunk
from processing.embedded_chunk import EmbeddedChunk
from embedding.base_emedder import BaseEmbedder
from typing import List

class SentenceTransformerEmbedder(BaseEmbedder):
    def __init__(self, model_name: str = "all=MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)

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