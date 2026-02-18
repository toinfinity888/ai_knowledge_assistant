"""
Integration Configuration Model for Enterprise Telephony Integrations

Stores per-tenant configuration for:
- Mode 1: Cloud telephony webhooks (Aircall, Genesys Cloud, Talkdesk, etc.)
- Mode 2: SIPREC for on-premise PBX (Avaya, Cisco, Genesys PureConnect)
- Demo mode: Direct Twilio calls (for pre-integration demos)
"""
from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.models.base import Base


def utcnow():
    """Return current UTC time (timezone-aware)"""
    return datetime.now(timezone.utc)


class IntegrationType(str, Enum):
    """Supported integration types"""
    CLOUD_WEBHOOK = "cloud_webhook"    # Mode 1: Webhooks + Provider ASR
    SIPREC = "siprec"                  # Mode 2: SIPREC standard
    DEMO_TWILIO = "demo_twilio"        # Demo: Direct Twilio calls


class IntegrationProvider(str, Enum):
    """Supported telephony providers"""
    # Cloud providers (Mode 1)
    AIRCALL = "aircall"
    GENESYS_CLOUD = "genesys_cloud"
    TALKDESK = "talkdesk"
    RINGOVER = "ringover"
    FIVE9 = "five9"
    TWILIO_FLEX = "twilio_flex"
    GENERIC = "generic"

    # On-premise providers (Mode 2 - SIPREC)
    AVAYA = "avaya"
    CISCO = "cisco"
    GENESYS_PURECONNECT = "genesys_pureconnect"
    ASTERISK = "asterisk"

    # Demo
    TWILIO_DEMO = "twilio_demo"


class IntegrationStatus(str, Enum):
    """Integration health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class IntegrationConfig(Base):
    """
    Per-tenant integration configuration.

    Each company can have multiple integration configurations
    for different telephony systems or environments (prod, staging).
    """
    __tablename__ = 'integration_configs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(
        Integer,
        ForeignKey('companies.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # Integration identification
    integration_id = Column(String(100), nullable=False, index=True)  # Unique per company
    name = Column(String(255), nullable=False)  # Human-friendly name
    description = Column(Text, nullable=True)

    # Type and provider
    integration_type = Column(
        SQLEnum(IntegrationType, values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )
    provider = Column(
        SQLEnum(IntegrationProvider, values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_primary = Column(Boolean, default=False)  # Primary integration for company

    # =========================================================================
    # Mode 1: Cloud Webhook Configuration
    # =========================================================================

    # Webhook security
    webhook_secret = Column(String(255), nullable=True)  # For signature verification
    webhook_url_suffix = Column(String(100), nullable=True)  # Custom URL suffix

    # Transcription source
    # 'provider_asr' = use provider's built-in ASR
    # 'deepgram' = forward audio to our Deepgram
    # 'whisper' = use local Whisper
    transcription_source = Column(String(50), default='provider_asr')

    # =========================================================================
    # Mode 2: SIPREC Configuration
    # =========================================================================

    siprec_port = Column(Integer, nullable=True)  # SIP port for SIPREC (e.g., 5060)
    siprec_transport = Column(String(10), default='udp')  # udp, tcp, tls
    allowed_sources = Column(JSON, default=list)  # IP whitelist for SIPREC
    srtp_enabled = Column(Boolean, default=True)  # Require SRTP encryption

    # =========================================================================
    # Common Configuration
    # =========================================================================

    # API credentials (encrypted at rest via application-level encryption)
    credentials = Column(JSON, default=dict)
    # Example:
    # {
    #   "api_key": "...",
    #   "api_secret": "...",
    #   "access_token": "...",
    #   "account_sid": "..."
    # }

    # Provider-specific settings
    settings = Column(JSON, default=dict)
    # Example for Aircall:
    # {
    #   "api_base_url": "https://api.aircall.io/v1",
    #   "events_to_subscribe": ["call.started", "call.ended", "call.transcription"]
    # }

    # Field mapping: provider fields → our schema
    metadata_mapping = Column(JSON, default=dict)
    # Example:
    # {
    #   "caller_id_field": "from_number",
    #   "agent_id_field": "user_id",
    #   "custom_mappings": {"priority": "tags.priority"}
    # }

    # Audio settings
    audio_settings = Column(JSON, default=dict)
    # {
    #   "target_sample_rate": 16000,
    #   "enable_noise_reduction": false,
    #   "language": "fr"
    # }

    # =========================================================================
    # Health Monitoring
    # =========================================================================

    health_status = Column(
        SQLEnum(IntegrationStatus, values_callable=lambda x: [e.value for e in x]),
        default=IntegrationStatus.UNKNOWN
    )
    last_health_check = Column(DateTime(timezone=True), nullable=True)
    last_event_received = Column(DateTime(timezone=True), nullable=True)
    consecutive_failures = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)

    # =========================================================================
    # Statistics
    # =========================================================================

    total_calls_processed = Column(Integer, default=0)
    total_events_received = Column(Integer, default=0)

    # =========================================================================
    # Timestamps
    # =========================================================================

    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    # =========================================================================
    # Relationships
    # =========================================================================

    company = relationship("Company", back_populates="integration_configs")

    def __repr__(self):
        return f"<IntegrationConfig(id={self.id}, name='{self.name}', type='{self.integration_type}', provider='{self.provider}')>"

    def to_dict(self, include_credentials: bool = False) -> dict:
        """Convert to dictionary for API responses"""
        data = {
            "id": self.id,
            "company_id": self.company_id,
            "integration_id": self.integration_id,
            "name": self.name,
            "description": self.description,
            "integration_type": self.integration_type.value if self.integration_type else None,
            "provider": self.provider.value if self.provider else None,
            "is_active": self.is_active,
            "is_primary": self.is_primary,
            "transcription_source": self.transcription_source,
            "settings": self.settings,
            "metadata_mapping": self.metadata_mapping,
            "audio_settings": self.audio_settings,
            "health_status": self.health_status.value if self.health_status else None,
            "last_health_check": self.last_health_check.isoformat() if self.last_health_check else None,
            "last_event_received": self.last_event_received.isoformat() if self.last_event_received else None,
            "total_calls_processed": self.total_calls_processed,
            "total_events_received": self.total_events_received,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

        # SIPREC-specific fields
        if self.integration_type == IntegrationType.SIPREC:
            data["siprec_port"] = self.siprec_port
            data["siprec_transport"] = self.siprec_transport
            data["allowed_sources"] = self.allowed_sources
            data["srtp_enabled"] = self.srtp_enabled

        # Only include credentials if explicitly requested (for internal use)
        if include_credentials:
            data["credentials"] = self.credentials
            data["webhook_secret"] = self.webhook_secret

        return data

    def update_health(self, status: IntegrationStatus, error: str = None):
        """Update health status"""
        self.health_status = status
        self.last_health_check = utcnow()
        self.error_message = error

        if status == IntegrationStatus.HEALTHY:
            self.consecutive_failures = 0
        else:
            self.consecutive_failures += 1

    def record_event(self):
        """Record that an event was received"""
        self.last_event_received = utcnow()
        self.total_events_received += 1

    def record_call(self):
        """Record that a call was processed"""
        self.total_calls_processed += 1

    def get_webhook_url(self, base_url: str) -> str:
        """Generate the webhook URL for this integration"""
        suffix = self.webhook_url_suffix or self.integration_id
        return f"{base_url}/api/v1/integrations/{self.provider.value}/webhook/{suffix}"
