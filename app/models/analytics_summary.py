"""
Analytics Daily Summary Model

Pre-aggregated daily metrics for fast dashboard queries.
Updated via scheduled job or on-demand aggregation.
"""
from datetime import datetime, date
from sqlalchemy import Column, Integer, BigInteger, Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.models.base import Base


class AnalyticsDailySummary(Base):
    """
    Pre-aggregated daily analytics metrics per company and user.

    When agent_user_id is NULL, represents company-wide totals.
    """
    __tablename__ = 'analytics_daily_summary'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Scope
    date = Column(Date, nullable=False, index=True)
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
    )  # NULL = company total

    # Session counts
    total_sessions = Column(Integer, default=0)
    sessions_with_feedback = Column(Integer, default=0)

    # Search metrics
    total_searches = Column(Integer, default=0)
    zero_result_searches = Column(Integer, default=0)

    # Field edit metrics
    total_field_edits = Column(Integer, default=0)

    # Outcome metrics
    solutions_found = Column(Integer, default=0)
    issues_resolved = Column(Integer, default=0)

    # Rating sums (for averaging: avg = sum / count)
    solution_rating_sum = Column(Integer, default=0)
    solution_rating_count = Column(Integer, default=0)
    speech_rating_sum = Column(Integer, default=0)
    speech_rating_count = Column(Integer, default=0)

    # Time metrics (in milliseconds, for averaging)
    total_session_duration_ms = Column(BigInteger, default=0)
    total_response_time_ms = Column(BigInteger, default=0)
    response_time_count = Column(Integer, default=0)

    # Suggestion metrics
    suggestions_shown = Column(Integer, default=0)
    suggestions_clicked = Column(Integer, default=0)
    suggestions_helpful = Column(Integer, default=0)
    suggestions_not_helpful = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Unique constraint: one record per date/company/user combination
    __table_args__ = (
        UniqueConstraint('date', 'company_id', 'agent_user_id', name='uix_daily_summary'),
    )

    # Relationships
    company = relationship("Company")
    agent_user = relationship("User")

    @property
    def avg_solution_rating(self) -> float | None:
        """Calculate average solution rating."""
        if self.solution_rating_count > 0:
            return self.solution_rating_sum / self.solution_rating_count
        return None

    @property
    def avg_speech_rating(self) -> float | None:
        """Calculate average speech recognition rating."""
        if self.speech_rating_count > 0:
            return self.speech_rating_sum / self.speech_rating_count
        return None

    @property
    def avg_session_duration_seconds(self) -> float | None:
        """Calculate average session duration in seconds."""
        if self.total_sessions > 0:
            return (self.total_session_duration_ms / self.total_sessions) / 1000
        return None

    @property
    def avg_response_time_ms(self) -> float | None:
        """Calculate average response time in milliseconds."""
        if self.response_time_count > 0:
            return self.total_response_time_ms / self.response_time_count
        return None

    @property
    def solution_found_rate(self) -> float | None:
        """Calculate solution found rate."""
        if self.sessions_with_feedback > 0:
            return self.solutions_found / self.sessions_with_feedback
        return None

    @property
    def issue_resolved_rate(self) -> float | None:
        """Calculate issue resolved rate."""
        if self.sessions_with_feedback > 0:
            return self.issues_resolved / self.sessions_with_feedback
        return None

    @property
    def suggestion_click_rate(self) -> float | None:
        """Calculate suggestion click rate."""
        if self.suggestions_shown > 0:
            return self.suggestions_clicked / self.suggestions_shown
        return None

    @property
    def zero_result_rate(self) -> float | None:
        """Calculate zero-result search rate."""
        if self.total_searches > 0:
            return self.zero_result_searches / self.total_searches
        return None

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            'date': self.date.isoformat() if self.date else None,
            'company_id': self.company_id,
            'agent_user_id': self.agent_user_id,
            'total_sessions': self.total_sessions,
            'sessions_with_feedback': self.sessions_with_feedback,
            'total_searches': self.total_searches,
            'zero_result_searches': self.zero_result_searches,
            'total_field_edits': self.total_field_edits,
            'solutions_found': self.solutions_found,
            'issues_resolved': self.issues_resolved,
            'avg_solution_rating': self.avg_solution_rating,
            'avg_speech_rating': self.avg_speech_rating,
            'avg_session_duration_seconds': self.avg_session_duration_seconds,
            'avg_response_time_ms': self.avg_response_time_ms,
            'solution_found_rate': self.solution_found_rate,
            'issue_resolved_rate': self.issue_resolved_rate,
            'suggestion_click_rate': self.suggestion_click_rate,
            'zero_result_rate': self.zero_result_rate,
            'suggestions_shown': self.suggestions_shown,
            'suggestions_clicked': self.suggestions_clicked,
        }
