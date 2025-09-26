from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
from qdrant_client.models import Distance

class QdrantSetting(BaseSettings):
    host: str
    port: int = 6333
    api_key: Optional[str] = None
    collection_name: str = 'mvp_support'
    vector_size: int = 3075
    https: bool = False
    recreate: bool = False
    distance: Distance = Distance.COSINE

    class Config:
        env_file = '/Users/saraevsviatoslav/Documents/ai_knowledge_assistant/.env'
        env_prefix = "QDRANT_"
        extra = 'allow'  # <--- ключевая строка
        case_sensitive = False
