"""
Audit Log Model for NIS2/ANSSI Compliance
Tracks all administrative actions for security audits
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.models.base import Base


def utcnow():
    """Return current UTC time (timezone-aware)"""
    return datetime.now(timezone.utc)


class ActionType:
    """Standard action types for audit logging"""
    # User actions
    USER_CREATE = "user.create"
    USER_UPDATE = "user.update"
    USER_DELETE = "user.delete"
    USER_DEACTIVATE = "user.deactivate"
    USER_ACTIVATE = "user.activate"

    # Company actions
    COMPANY_CREATE = "company.create"
    COMPANY_UPDATE = "company.update"
    COMPANY_DEACTIVATE = "company.deactivate"
    COMPANY_DELETE = "company.delete"

    # Document actions
    DOCUMENT_UPLOAD = "document.upload"
    DOCUMENT_DELETE = "document.delete"

    # Password actions
    PASSWORD_CHANGE = "password.change"
    PASSWORD_RESET = "password.reset"

    # Invitation actions
    INVITATION_CREATE = "invitation.create"
    INVITATION_ACCEPT = "invitation.accept"
    INVITATION_REVOKE = "invitation.revoke"

    # Auth actions
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_LOGOUT_ALL = "auth.logout_all"
    AUTH_TOKEN_REFRESH = "auth.token_refresh"

    # Settings actions
    SETTINGS_UPDATE = "settings.update"


class TargetType:
    """Standard target types for audit logging"""
    USER = "user"
    COMPANY = "company"
    DOCUMENT = "document"
    INVITATION = "invitation"
    SETTINGS = "settings"
    SESSION = "session"


class AuditLog(Base):
    """
    Immutable audit log entry for compliance tracking.
    Records who did what, when, and from where.

    Note: Actor email is denormalized to persist even if user is deleted.
    """
    __tablename__ = 'audit_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Actor information (who performed the action)
    actor_user_id = Column(
        Integer,
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True
    )
    actor_email = Column(String(255), nullable=False)  # Denormalized for persistence

    # Action details
    action_type = Column(String(50), nullable=False, index=True)
    target_type = Column(String(50), nullable=False)
    target_id = Column(Integer, nullable=True)

    # Company scope (null for global/platform actions)
    company_id = Column(
        Integer,
        ForeignKey('companies.id', ondelete='SET NULL'),
        nullable=True
    )

    # Additional details (JSON for flexibility)
    details = Column(JSON, nullable=True)

    # Request metadata
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)

    # Timestamp (immutable)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)

    # Relationships
    actor = relationship("User", foreign_keys=[actor_user_id])
    company = relationship("Company", foreign_keys=[company_id])

    def __repr__(self):
        return f"<AuditLog(action='{self.action_type}', actor='{self.actor_email}', target='{self.target_type}:{self.target_id}')>"

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "actor_user_id": self.actor_user_id,
            "actor_email": self.actor_email,
            "action_type": self.action_type,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "company_id": self.company_id,
            "details": self.details,
            "ip_address": self.ip_address,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
