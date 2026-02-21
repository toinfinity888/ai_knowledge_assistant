"""
Session Feedback Model

Stores post-session feedback with star ratings for solution relevance
and speech recognition quality.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.models.base import Base


class SessionFeedback(Base):
    """
    Post-session feedback with star ratings.

    Captured when agent ends a call, with option to skip.
    """
    __tablename__ = 'session_feedback'

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

    # 5-star ratings (1-5, NULL if skipped)
    solution_rating = Column(Integer, nullable=True)
    speech_recognition_rating = Column(Integer, nullable=True)

    # Outcome tracking
    solution_found = Column(Boolean, nullable=True)
    issue_resolved = Column(Boolean, nullable=True)

    # Optional comments
    comments = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    session = relationship("CallSession", back_populates="feedback")
    company = relationship("Company")
    agent_user = relationship("User")

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'company_id': self.company_id,
            'agent_user_id': self.agent_user_id,
            'solution_rating': self.solution_rating,
            'speech_recognition_rating': self.speech_recognition_rating,
            'solution_found': self.solution_found,
            'issue_resolved': self.issue_resolved,
            'comments': self.comments,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
