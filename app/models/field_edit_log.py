"""
Field Edit Log Model

Tracks manual edits to auto-filled fields during support sessions.
Used to identify AI extraction quality issues.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.models.base import Base


class FieldEditLog(Base):
    """
    Tracks when agents manually correct auto-filled fields.

    High edit counts for specific fields indicate AI extraction issues.
    """
    __tablename__ = 'field_edit_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign keys
    session_id = Column(
        Integer,
        ForeignKey('call_sessions.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    company_id = Column(
        Integer,
        ForeignKey('companies.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    agent_user_id = Column(
        Integer,
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )

    # Field information
    field_slug = Column(String(100), nullable=False, index=True)
    field_name = Column(String(255), nullable=True)

    # Edit tracking
    original_value = Column(Text, nullable=True)  # AI-extracted value
    edited_value = Column(Text, nullable=True)    # User-corrected value

    # Timestamps
    edited_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    session = relationship("CallSession", back_populates="field_edits")
    company = relationship("Company")
    agent_user = relationship("User")

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'field_slug': self.field_slug,
            'field_name': self.field_name,
            'original_value': self.original_value,
            'edited_value': self.edited_value,
            'edited_at': self.edited_at.isoformat() if self.edited_at else None,
        }
