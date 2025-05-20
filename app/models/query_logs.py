import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, JSON, DateTime
from sqlalchemy.orm import declarative_base
from app.database.postgresql_session import engine

Base = declarative_base()

class QueryLogs(Base):
    __tablename__= 'query_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    query_text = Column(String, nullable=True)
    response_text = Column(String, nullable=True)
    has_response = Column(Boolean, nullable=False)
    response_status = Column(String, default='NO_RESPONSE')
    response_time_ms = Column(Integer, nullable=True)
    retriever_used = Column(String, nullable=True)
    llm_model_used = Column(String, nullable=True)
    retrieved_context = Column(JSON, default=list)
    user_id = Column(String, default='anonymous')
    timestamp: datetime = Column(DateTime, default=datetime.utcnow())

# Create table
Base.metadata.create_all(engine)
    