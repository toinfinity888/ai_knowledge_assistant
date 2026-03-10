"""
Prompt Template Model

Stores customizable LLM prompts per company for different use cases.
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime

from app.models.base import Base


class PromptTemplate(Base):
    """
    Stores customizable prompts for LLM interactions.

    Each company can have its own prompts for different use cases:
    - rag_answer: Main RAG answer generation prompt
    - validator: Conversation validation prompt
    """
    __tablename__ = "prompt_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)

    # Prompt identification
    prompt_key = Column(String(100), nullable=False)  # e.g., "rag_answer", "validator"
    language = Column(String(10), default="en")  # Language code

    # Prompt content
    name = Column(String(255), nullable=False)  # Human-readable name
    description = Column(Text, nullable=True)  # Description for admins
    system_prompt = Column(Text, nullable=False)  # The actual prompt template

    # Status
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    company = relationship("Company", backref="prompt_templates")

    __table_args__ = (
        UniqueConstraint('company_id', 'prompt_key', 'language', name='uq_company_prompt_language'),
    )

    def __repr__(self):
        return f"<PromptTemplate {self.prompt_key}:{self.language} (company={self.company_id})>"


# Default prompts that will be seeded for new companies
DEFAULT_PROMPTS = {
    "rag_answer": {
        "en": {
            "name": "RAG Answer Generation",
            "description": "Prompt used when generating answers from the knowledge base",
            "system_prompt": """You are a helpful technical support assistant. Use the context below to answer the user's question clearly and naturally.

INSTRUCTIONS:
- Answer in plain text without markdown formatting (no **, no ##, no bullet points with *)
- Be concise and direct
- If the context doesn't contain relevant information, say so
- Use numbered lists (1. 2. 3.) for steps, not bullet points
- Provide exact information from the source when available
- IMPORTANT: Always respond in English"""
        },
        "fr": {
            "name": "Génération de réponse RAG",
            "description": "Prompt utilisé pour générer des réponses à partir de la base de connaissances",
            "system_prompt": """You are a helpful technical support assistant. Use the context below to answer the user's question clearly and naturally.

INSTRUCTIONS:
- Answer in plain text without markdown formatting (no **, no ##, no bullet points with *)
- Be concise and direct
- If the context doesn't contain relevant information, say so
- Use numbered lists (1. 2. 3.) for steps, not bullet points
- Provide exact information from the source when available
- IMPORTANT: Always respond in French (français). Répondez toujours en français, même si le contexte est en anglais."""
        },
        "es": {
            "name": "Generación de respuesta RAG",
            "description": "Prompt utilizado para generar respuestas desde la base de conocimientos",
            "system_prompt": """You are a helpful technical support assistant. Use the context below to answer the user's question clearly and naturally.

INSTRUCTIONS:
- Answer in plain text without markdown formatting (no **, no ##, no bullet points with *)
- Be concise and direct
- If the context doesn't contain relevant information, say so
- Use numbered lists (1. 2. 3.) for steps, not bullet points
- Provide exact information from the source when available
- IMPORTANT: Always respond in Spanish (español). Responde siempre en español, incluso si el contexto está en inglés."""
        },
    },
    "validator": {
        "en": {
            "name": "Conversation Validator",
            "description": "Prompt used to validate conversation context and extract fields",
            "system_prompt": """You are a technical support conversation validator.

TASK:
Analyze the following support conversation and:
1. Classify which technical domain the conversation belongs to
2. Extract all mentioned information fields from the conversation
3. Identify which required and recommended fields are still missing
4. If sufficient required information is present, generate an optimized search query

RULES:
- If no domain matches, set domain to "unknown" and status to "unknown_domain"
- If required fields are missing, set status to "missing_required"
- If all required fields are present, set status to "ready"
- Extract field values ONLY from what the customer explicitly stated
- Do not guess or infer values

OUTPUT FORMAT (respond with valid JSON only):
{
  "domain": "domain_slug or unknown",
  "domain_confidence": 0.0,
  "extracted_fields": {"field_slug": "extracted_value"},
  "missing_required": ["field_slug"],
  "missing_recommended": ["field_slug"],
  "optimized_search_query": "search query string",
  "status": "ready | missing_required | unknown_domain",
  "reasoning": "brief explanation"
}"""
        },
    },
}
