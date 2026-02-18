"""
Company Model for Multi-Tenancy
Represents an organization using the AI Knowledge Assistant
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, JSON, DateTime
from sqlalchemy.orm import relationship

from app.models.base import Base


class Company(Base):
    """
    Represents a company/organization in the multi-tenant system.
    All data is isolated by company_id for complete tenant separation.
    """
    __tablename__ = 'companies'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Company identification
    slug = Column(String(100), unique=True, nullable=False, index=True)  # URL-friendly identifier
    name = Column(String(255), nullable=False)

    # Subscription/plan
    plan = Column(String(50), default='free', nullable=False)  # free, basic, pro, enterprise

    # Status
    is_active = Column(Boolean, default=True, nullable=False)

    # Company-specific settings (JSON for flexibility)
    settings = Column(JSON, default=dict)  # e.g., {"max_agents": 10, "features": ["realtime", "crm"]}

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships - CASCADE delete all company data when company is deleted
    users = relationship(
        "User",
        back_populates="company",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    call_sessions = relationship(
        "CallSession",
        back_populates="company",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    integration_configs = relationship(
        "IntegrationConfig",
        back_populates="company",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    def __repr__(self):
        return f"<Company(slug='{self.slug}', name='{self.name}', plan='{self.plan}')>"

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "slug": self.slug,
            "name": self.name,
            "plan": self.plan,
            "is_active": self.is_active,
            "settings": self.settings or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
