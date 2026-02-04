"""
Invitation Model for Token-Based User Onboarding
Enables secure invite-based user registration flow
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.models.base import Base
from app.models.user import UserRole


def utcnow():
    """Return current UTC time (timezone-aware)"""
    return datetime.now(timezone.utc)


class Invitation(Base):
    """
    Represents a pending invitation for a new user to join the platform.

    Flow:
    1. Admin creates invitation for email/role
    2. System generates secure token
    3. User receives email with invite link
    4. User clicks link, sets password
    5. User account is created with specified role
    """
    __tablename__ = 'invitations'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Invitee information
    email = Column(String(255), nullable=False, index=True)

    # Company assignment (nullable for SUPER_ADMIN invitations)
    company_id = Column(
        Integer,
        ForeignKey('companies.id', ondelete='CASCADE'),
        nullable=True,
        index=True
    )

    # Role to assign when invitation is accepted
    role = Column(
        SQLEnum(UserRole, values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )

    # Secure token for invitation link
    token = Column(String(64), unique=True, nullable=False, index=True)

    # Expiration
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # Acceptance tracking
    is_accepted = Column(Boolean, default=False, nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=True)

    # Creator tracking
    created_by_user_id = Column(
        Integer,
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True
    )
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Relationships
    company = relationship("Company", backref="invitations")
    created_by = relationship("User", foreign_keys=[created_by_user_id])

    def __repr__(self):
        return f"<Invitation(email='{self.email}', role='{self.role}', company_id={self.company_id})>"

    def is_valid(self) -> bool:
        """Check if invitation is still valid (not accepted and not expired)"""
        if self.is_accepted:
            return False
        return datetime.now(timezone.utc) < self.expires_at

    def is_expired(self) -> bool:
        """Check if invitation has expired"""
        return datetime.now(timezone.utc) >= self.expires_at

    def mark_accepted(self):
        """Mark invitation as accepted"""
        self.is_accepted = True
        self.accepted_at = utcnow()

    def to_dict(self, include_token: bool = False):
        """Convert to dictionary for API responses"""
        data = {
            "id": self.id,
            "email": self.email,
            "role": self.role.value,
            "company_id": self.company_id,
            "is_accepted": self.is_accepted,
            "is_expired": self.is_expired(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "accepted_at": self.accepted_at.isoformat() if self.accepted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "created_by_user_id": self.created_by_user_id,
        }
        if include_token:
            data["token"] = self.token
        if self.company:
            data["company_name"] = self.company.name
        return data
