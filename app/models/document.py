"""
Document Model for Knowledge Base Management

Represents uploaded documents (PDFs) that are parsed and stored in the vector database.
Each document belongs to a company for multi-tenant isolation.
"""
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.models.base import Base


class DocumentStatus(str, Enum):
    """Status of document processing"""
    PENDING = "pending"          # Uploaded, waiting for processing
    PROCESSING = "processing"    # Currently being parsed/embedded
    COMPLETED = "completed"      # Successfully processed
    FAILED = "failed"            # Processing failed


class Document(Base):
    """
    Represents an uploaded document in the knowledge base.

    Documents are parsed, chunked, and stored as vectors in Qdrant.
    The document_id is stored in vector payloads to enable deletion.
    """
    __tablename__ = 'documents'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Company isolation (multi-tenancy)
    company_id = Column(
        Integer,
        ForeignKey('companies.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # File metadata
    filename = Column(String(255), nullable=False)  # Stored name (UUID-based)
    original_filename = Column(String(255), nullable=False)  # User's original filename
    file_size = Column(Integer, nullable=False)  # Size in bytes
    mime_type = Column(String(100), default='application/pdf')

    # Processing status
    status = Column(
        SQLEnum(DocumentStatus),
        default=DocumentStatus.PENDING,
        nullable=False,
        index=True
    )
    chunk_count = Column(Integer, default=0)  # Number of chunks created
    error_message = Column(Text, nullable=True)  # Error details if failed

    # Audit
    created_by_user_id = Column(
        Integer,
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)  # When processing completed

    # Relationships
    company = relationship("Company", back_populates="documents")
    created_by = relationship("User", foreign_keys=[created_by_user_id])

    def __repr__(self):
        return f"<Document(id={self.id}, filename='{self.original_filename}', status='{self.status.value}')>"

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "company_id": self.company_id,
            "filename": self.original_filename,
            "file_size": self.file_size,
            "mime_type": self.mime_type,
            "status": self.status.value,
            "chunk_count": self.chunk_count,
            "error_message": self.error_message,
            "created_by_user_id": self.created_by_user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
        }
