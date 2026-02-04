"""
Domain Schema Service

CRUD operations for the Domain Schema Registry.
Manages domain schemas and their fields per company.
"""
import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.models.domain_schema import DomainSchema, DomainSchemaField

logger = logging.getLogger(__name__)

# Singleton instance
_domain_schema_service = None


def get_domain_schema_service() -> "DomainSchemaService":
    global _domain_schema_service
    if _domain_schema_service is None:
        _domain_schema_service = DomainSchemaService()
    return _domain_schema_service


class DomainSchemaService:
    """Service for managing domain schemas and fields."""

    # ==================== Schema CRUD ====================

    def get_schemas_for_company(
        self, company_id: int, db: Session, active_only: bool = True
    ) -> List[DomainSchema]:
        query = db.query(DomainSchema).filter(DomainSchema.company_id == company_id)
        if active_only:
            query = query.filter(DomainSchema.is_active == True)
        return query.order_by(DomainSchema.display_order).all()

    def get_schema(
        self, schema_id: int, company_id: int, db: Session
    ) -> Optional[DomainSchema]:
        return (
            db.query(DomainSchema)
            .filter(DomainSchema.id == schema_id, DomainSchema.company_id == company_id)
            .first()
        )

    def create_schema(
        self,
        company_id: int,
        name: str,
        slug: str,
        db: Session,
        description: Optional[str] = None,
    ) -> DomainSchema:
        max_order = (
            db.query(DomainSchema.display_order)
            .filter(DomainSchema.company_id == company_id)
            .order_by(DomainSchema.display_order.desc())
            .first()
        )
        next_order = (max_order[0] + 1) if max_order else 0

        schema = DomainSchema(
            company_id=company_id,
            name=name,
            slug=slug,
            description=description,
            display_order=next_order,
        )
        db.add(schema)
        db.flush()
        logger.info(f"Created domain schema '{slug}' for company {company_id}")
        return schema

    def update_schema(
        self, schema_id: int, company_id: int, updates: Dict[str, Any], db: Session
    ) -> Optional[DomainSchema]:
        schema = self.get_schema(schema_id, company_id, db)
        if not schema:
            return None
        for key in ("name", "slug", "description", "is_active", "display_order"):
            if key in updates:
                setattr(schema, key, updates[key])
        db.flush()
        return schema

    def delete_schema(
        self, schema_id: int, company_id: int, db: Session
    ) -> bool:
        schema = self.get_schema(schema_id, company_id, db)
        if not schema:
            return False
        db.delete(schema)
        db.flush()
        logger.info(f"Deleted domain schema {schema_id} for company {company_id}")
        return True

    # ==================== Field CRUD ====================

    def get_field(self, field_id: int, db: Session) -> Optional[DomainSchemaField]:
        return db.query(DomainSchemaField).filter(DomainSchemaField.id == field_id).first()

    def add_field(
        self,
        schema_id: int,
        name: str,
        slug: str,
        db: Session,
        description: Optional[str] = None,
        field_type: str = "text",
        is_required: bool = False,
        options: Optional[List[str]] = None,
    ) -> DomainSchemaField:
        max_order = (
            db.query(DomainSchemaField.display_order)
            .filter(DomainSchemaField.schema_id == schema_id)
            .order_by(DomainSchemaField.display_order.desc())
            .first()
        )
        next_order = (max_order[0] + 1) if max_order else 0

        field = DomainSchemaField(
            schema_id=schema_id,
            name=name,
            slug=slug,
            description=description,
            field_type=field_type,
            is_required=is_required,
            options=options or [],
            display_order=next_order,
        )
        db.add(field)
        db.flush()
        return field

    def update_field(
        self, field_id: int, updates: Dict[str, Any], db: Session
    ) -> Optional[DomainSchemaField]:
        field = self.get_field(field_id, db)
        if not field:
            return None
        for key in ("name", "slug", "description", "field_type", "is_required", "options", "display_order"):
            if key in updates:
                setattr(field, key, updates[key])
        db.flush()
        return field

    def delete_field(self, field_id: int, db: Session) -> bool:
        field = self.get_field(field_id, db)
        if not field:
            return False
        db.delete(field)
        db.flush()
        return True

    # ==================== Validator Helper ====================

    def get_schemas_for_validator(
        self, company_id: int, db: Session
    ) -> List[Dict[str, Any]]:
        """Return active schemas in the format expected by the validator system prompt."""
        schemas = self.get_schemas_for_company(company_id, db, active_only=True)
        return [s.to_validator_dict() for s in schemas]

    # ==================== Seed Defaults ====================

    def seed_default_schemas(self, company_id: int, db: Session) -> List[DomainSchema]:
        """Create the 4 default domain schemas for a company."""
        existing = self.get_schemas_for_company(company_id, db, active_only=False)
        if existing:
            logger.info(f"Company {company_id} already has schemas, skipping seed")
            return existing

        schemas = []
        for domain_def in _DEFAULT_DOMAINS:
            schema = self.create_schema(
                company_id=company_id,
                name=domain_def["name"],
                slug=domain_def["slug"],
                description=domain_def["description"],
                db=db,
            )
            for field_def in domain_def["fields"]:
                self.add_field(
                    schema_id=schema.id,
                    name=field_def["name"],
                    slug=field_def["slug"],
                    description=field_def.get("description"),
                    field_type=field_def.get("field_type", "text"),
                    is_required=field_def.get("is_required", False),
                    options=field_def.get("options"),
                    db=db,
                )
            schemas.append(schema)

        logger.info(f"Seeded {len(schemas)} default domain schemas for company {company_id}")
        return schemas


# ==================== Default Domain Definitions ====================

_DEFAULT_DOMAINS = [
    {
        "name": "Video Surveillance (CCTV)",
        "slug": "video_surveillance",
        "description": "IP cameras, NVRs, DVRs, and video management systems",
        "fields": [
            {
                "name": "Brand",
                "slug": "brand",
                "description": "Camera/NVR manufacturer",
                "field_type": "select",
                "is_required": True,
                "options": ["Hikvision", "Dahua", "Axis", "Hanwha", "Bosch", "Vivotek", "Other"],
            },
            {
                "name": "Model/Series",
                "slug": "model_series",
                "description": "Specific model number or product series",
                "field_type": "text",
                "is_required": True,
            },
            {
                "name": "Symptom/LED Status",
                "slug": "symptom_led_status",
                "description": "Visible symptoms, LED behavior, or error indicators",
                "field_type": "text",
                "is_required": True,
            },
            {
                "name": "Power Source",
                "slug": "power_source",
                "description": "How the device is powered",
                "field_type": "select",
                "is_required": False,
                "options": ["PoE", "12V DC", "24V AC", "Solar", "Battery", "Unknown"],
            },
        ],
    },
    {
        "name": "Access Control (ACS)",
        "slug": "access_control",
        "description": "Door controllers, readers, locks, and access management",
        "fields": [
            {
                "name": "Controller Type",
                "slug": "controller_type",
                "description": "Type of access controller",
                "field_type": "select",
                "is_required": True,
                "options": ["2-door", "4-door", "Single", "Network", "Standalone"],
            },
            {
                "name": "Reader Protocol",
                "slug": "reader_protocol",
                "description": "Communication protocol of the card/badge reader",
                "field_type": "select",
                "is_required": True,
                "options": ["Wiegand", "OSDP", "Bluetooth", "NFC", "Biometric"],
            },
            {
                "name": "Lock Mechanism",
                "slug": "lock_mechanism",
                "description": "Type of lock on the door",
                "field_type": "select",
                "is_required": False,
                "options": ["Electric Strike", "Mag Lock", "Motor Lock", "Deadbolt"],
            },
            {
                "name": "Error Code",
                "slug": "error_code",
                "description": "Hexadecimal code or beep sequence displayed by the controller",
                "field_type": "text",
                "is_required": True,
            },
        ],
    },
    {
        "name": "Subscriptions & Licensing",
        "slug": "subscriptions_licensing",
        "description": "Cloud subscriptions, software licenses, and service tiers",
        "fields": [
            {
                "name": "Service Tier",
                "slug": "service_tier",
                "description": "Subscription plan level",
                "field_type": "select",
                "is_required": True,
                "options": ["Basic", "Standard", "Premium", "Enterprise"],
            },
            {
                "name": "Region",
                "slug": "region",
                "description": "Deployment region (important for compliance)",
                "field_type": "text",
                "is_required": False,
            },
            {
                "name": "Expiration Date",
                "slug": "expiration_date",
                "description": "License or subscription expiration date",
                "field_type": "text",
                "is_required": False,
            },
            {
                "name": "Error Message",
                "slug": "error_message",
                "description": "Platform-specific error text shown to the user",
                "field_type": "text",
                "is_required": True,
            },
        ],
    },
    {
        "name": "Physical Installation",
        "slug": "physical_installation",
        "description": "Device mounting, cabling, and environmental requirements",
        "fields": [
            {
                "name": "Environment",
                "slug": "environment",
                "description": "Installation location type",
                "field_type": "select",
                "is_required": True,
                "options": ["Indoor", "Outdoor", "Parking", "Elevator", "Entrance"],
            },
            {
                "name": "Mounting Height",
                "slug": "mounting_height",
                "description": "Installation height (affects field of view and sensor range)",
                "field_type": "text",
                "is_required": False,
            },
            {
                "name": "Compliance Standard",
                "slug": "compliance_standard",
                "description": "Applicable standards or certifications",
                "field_type": "select",
                "is_required": False,
                "options": ["IP66", "IP67", "IK10", "NDAA", "ONVIF"],
            },
        ],
    },
]
