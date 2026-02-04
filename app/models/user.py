"""
User Model for Multi-Tenancy Authentication
Represents support agents and administrators within a company
"""
from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.models.base import Base


def utcnow():
    """Return current UTC time (timezone-aware)"""
    return datetime.now(timezone.utc)


class UserRole(str, Enum):
    """User roles - hierarchical access control"""
    SUPER_ADMIN = "super_admin"  # Apertool platform admin - global access, no company
    ADMIN = "admin"              # Company admin - can manage company settings and users
    AGENT = "agent"              # Support agent - can handle calls and view knowledge base
    VIEWER = "viewer"            # Read-only access to dashboards


class User(Base):
    """
    Represents a user (support agent, admin) within a company.
    Users belong to exactly one company for data isolation.
    """
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Company relationship (nullable for SUPER_ADMIN users who have global access)
    company_id = Column(
        Integer,
        ForeignKey('companies.id', ondelete='CASCADE'),
        nullable=True,  # SUPER_ADMIN users have no company
        index=True
    )

    # User identification
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)

    # Authentication
    password_hash = Column(String(255), nullable=False)

    # Role and status
    # Use values_callable to ensure lowercase values are used in the database
    role = Column(
        SQLEnum(UserRole, values_callable=lambda x: [e.value for e in x]),
        default=UserRole.AGENT,
        nullable=False
    )
    is_active = Column(Boolean, default=True, nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    last_login = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    company = relationship("Company", back_populates="users")
    refresh_tokens = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    call_sessions = relationship(
        "CallSession",
        back_populates="agent_user",
        foreign_keys="CallSession.agent_user_id"
    )

    def __repr__(self):
        return f"<User(email='{self.email}', role='{self.role}', company_id={self.company_id})>"

    def to_dict(self, include_company: bool = False):
        """Convert to dictionary for API responses"""
        data = {
            "id": self.id,
            "email": self.email,
            "full_name": self.full_name,
            "role": self.role.value,
            "is_active": self.is_active,
            "company_id": self.company_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }
        if include_company and self.company:
            data["company"] = {
                "id": self.company.id,
                "slug": self.company.slug,
                "name": self.company.name,
            }
        return data

    def has_role(self, *roles: UserRole) -> bool:
        """Check if user has any of the specified roles"""
        return self.role in roles

    def is_admin(self) -> bool:
        """Check if user is a company admin"""
        return self.role == UserRole.ADMIN

    def is_super_admin(self) -> bool:
        """Check if user is a platform super admin"""
        return self.role == UserRole.SUPER_ADMIN

    def can_manage_company(self, company_id: int) -> bool:
        """Check if user can manage the specified company"""
        if self.is_super_admin():
            return True
        return self.company_id == company_id and self.is_admin()
