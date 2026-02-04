"""
Domain Schema Registry Models

Defines the domain-specific schemas used by the Intelligence Gatekeeper
to validate conversation context before triggering RAG searches.
Each company can have its own set of domain schemas.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, JSON, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.models.base import Base


class DomainSchema(Base):
    """
    Represents a domain category (e.g., CCTV, Access Control) for the Gatekeeper.
    Company-scoped for multi-tenant isolation.
    """
    __tablename__ = 'domain_schemas'

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey('companies.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )

    name = Column(String(255), nullable=False)
    slug = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    display_order = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    company = relationship("Company", backref="domain_schemas")
    fields = relationship(
        "DomainSchemaField",
        back_populates="schema",
        cascade="all, delete-orphan",
        order_by="DomainSchemaField.display_order",
    )

    def __repr__(self):
        return f"<DomainSchema(slug='{self.slug}', name='{self.name}', company_id={self.company_id})>"

    def to_dict(self):
        return {
            "id": self.id,
            "company_id": self.company_id,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "is_active": self.is_active,
            "display_order": self.display_order,
            "fields": [f.to_dict() for f in self.fields],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_validator_dict(self):
        """Format for the LLM validator system prompt."""
        required_fields = []
        recommended_fields = []
        for f in self.fields:
            entry = {
                "name": f.name,
                "slug": f.slug,
                "description": f.description or "",
                "field_type": f.field_type,
            }
            if f.field_type == "select" and f.options:
                entry["options"] = f.options
            if f.is_required:
                required_fields.append(entry)
            else:
                recommended_fields.append(entry)
        return {
            "name": self.name,
            "slug": self.slug,
            "description": self.description or "",
            "required_fields": required_fields,
            "recommended_fields": recommended_fields,
        }


class DomainSchemaField(Base):
    """
    Individual field within a domain schema.
    Defines what information the validator should extract and check.
    """
    __tablename__ = 'domain_schema_fields'

    id = Column(Integer, primary_key=True, autoincrement=True)
    schema_id = Column(
        Integer,
        ForeignKey('domain_schemas.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )

    name = Column(String(255), nullable=False)
    slug = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    field_type = Column(String(50), default='text')  # text, select, number
    is_required = Column(Boolean, default=False, nullable=False)
    options = Column(JSON, default=list)  # For select fields
    display_order = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    schema = relationship("DomainSchema", back_populates="fields")

    def __repr__(self):
        return f"<DomainSchemaField(slug='{self.slug}', required={self.is_required})>"

    def to_dict(self):
        return {
            "id": self.id,
            "schema_id": self.schema_id,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "field_type": self.field_type,
            "is_required": self.is_required,
            "options": self.options or [],
            "display_order": self.display_order,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
