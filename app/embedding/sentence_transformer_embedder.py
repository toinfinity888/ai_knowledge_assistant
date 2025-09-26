from sentence_transformers import SentenceTransformer
from app.models.text_chunk import TextChunk
from app.models.embedded import EmbeddedChunk
from app.embedding.base_emedder import BaseEmbedder
from typing import List
from app.models.query import Query
from app.models.embedded import EmbeddedQuery
from openai import OpenAI
from dotenv import load_dotenv


class SentenceTransformerEmbedder(BaseEmbedder):
    def __init__(self):
        super().__init__()
    def embed_text(self, chunks: List[TextChunk]) -> List[EmbeddedChunk]:
        texts = [chunk.text for chunk in chunks]
        response = self.client.embeddings.create(
            input=texts,
            model=self.model_name
        )
        vectors = response.data[0].embedding

        embedded = []
        for chunk, vector in zip(chunks, vectors):
            embedded.append(EmbeddedChunk(
                id=chunk.chunk_id,
                embedding=vector,
                text=chunk.text,
                #file_name=chunk.file_name,
            #     source=chunk.source,
            #     page=chunk.page,
            #     file_type=chunk.file_type,
            #     last_modified=chunk.last_modified,
            #     text_hash=chunk.text_hash,
            #     score=chunk.score
            # 
            ))
        return embedded
    
    def embed_query(self, query: Query) -> EmbeddedQuery:
        text = query.text
        response = self.client.embeddings.create(input=text,
                                                 model=self.model_name)
        vector = response.data[0].embedding
        return EmbeddedQuery(query=query, embedding=vector)