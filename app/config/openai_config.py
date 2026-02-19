"""OpenAI Configuration Settings"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class OpenAISetting(BaseSettings):
    """Configuration for OpenAI API."""

    api_key: str = Field(default="", description="OpenAI API key")
    embedding_model: str = Field(
        default="text-embedding-3-large",
        description="Model to use for embeddings"
    )
    embedding_dimensions: int = Field(
        default=3072,
        description="Embedding vector dimensions"
    )

    class Config:
        env_file = '/Users/saraevsviatoslav/Documents/ai_knowledge_assistant/.env'
        env_prefix = "OPENAI_"
        extra = 'allow'
        case_sensitive = False
