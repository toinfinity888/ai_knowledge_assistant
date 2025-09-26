from abc import ABC, abstractmethod
from typing import List
from app.models.text_chunk import TextChunk
from sentence_transformers import SentenceTransformer
from app.models.query import Query
from app.models.embedded import EmbeddedQuery
from openai import OpenAI
import os
from dotenv import load_dotenv
load_dotenv()

class BaseEmbedder(ABC):
    def __init__(self, model_name: str = "text-embedding-3-large"):
        self.client = OpenAI(
            api_key=os.getenv('OPENAI_API_KEY')
        )
        self.model_name = model_name

    @abstractmethod
    def embed_text(self, chunk: List[TextChunk]) -> List[dict]:
        pass
    
    @abstractmethod
    def embed_query(self, query: Query) -> EmbeddedQuery:
        pass

    