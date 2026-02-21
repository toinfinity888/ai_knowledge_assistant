"""
Query Logs Model
Tracks all queries made to the RAG engine for analytics and debugging
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, JSON, DateTime, ForeignKey

from app.models.base import Base


class QueryLogs(Base):
    """
    Logs all queries made to the knowledge base for analytics and debugging.
    Optionally scoped to a company for multi-tenant environments.
    """
    __tablename__ = 'query_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Multi-tenancy: Company isolation (nullable for backward compatibility)
    company_id = Column(
        Integer,
        ForeignKey('companies.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )

    # Query data
    query_text = Column(String, nullable=True)
    response_text = Column(String, nullable=True)
    has_response = Column(Boolean, nullable=False)
    response_status = Column(String, default='NO_RESPONSE')
    response_time_ms = Column(Integer, nullable=True)

    # Engine info
    retriever_used = Column(String, nullable=True)
    llm_model_used = Column(String, nullable=True)
    retrieved_context = Column(JSON, default=list)

    # User tracking
    user_id = Column(String, default='anonymous')

    # Session tracking (for analytics)
    session_id = Column(
        Integer,
        ForeignKey('call_sessions.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    agent_user_id = Column(
        Integer,
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    search_type = Column(String(50), nullable=True)  # 'manual', 'automatic', 'force_search'

    # Timestamp
    timestamp = Column(DateTime, default=datetime.utcnow)
    