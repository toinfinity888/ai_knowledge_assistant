from pydantic import BaseSetting, Field
from typing import Optional
from qdrant_client.models import Distance

class QdrantSetting(BaseSetting):
    qdrant_host: str = Field(default=None, env='QDRANT_HOST')
    qdrant_port: int = 6333
    qdrant_api_key = Optional[str] = Field(default=None, env='QDRANT_CLOUD_KEY')
    qdrant_collection_name: str = 'entraprise_docs'
    qdrant_vector_size: int = 384
    qdrant_https: bool = False
    qdrant_recreate: bool = False
    qdrant_distance: Distance = Distance.COSINE

    class Config:
        env_file = '.env'
