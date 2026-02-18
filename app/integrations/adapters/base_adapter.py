"""
Base Webhook Adapter for Cloud Telephony Integrations

Defines the abstract interface that all provider-specific adapters must implement.
Handles normalization of provider-specific webhook payloads to our internal schema.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List
import hmac
import hashlib
import logging

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Normalized event types across all providers"""
    # Call lifecycle events
    CALL_STARTED = "call.started"
    CALL_RINGING = "call.ringing"
    CALL_ANSWERED = "call.answered"
    CALL_ENDED = "call.ended"
    CALL_TRANSFERRED = "call.transferred"
    CALL_HOLD = "call.hold"
    CALL_UNHOLD = "call.unhold"

    # Transcription events
    TRANSCRIPTION_PARTIAL = "transcription.partial"
    TRANSCRIPTION_FINAL = "transcription.final"

    # Recording events
    RECORDING_STARTED = "recording.started"
    RECORDING_COMPLETED = "recording.completed"
    RECORDING_AVAILABLE = "recording.available"

    # Agent events
    AGENT_JOINED = "agent.joined"
    AGENT_LEFT = "agent.left"

    # Unknown/custom
    UNKNOWN = "unknown"


class Speaker(str, Enum):
    """Speaker identification"""
    CUSTOMER = "customer"
    AGENT = "agent"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class CallDirection(str, Enum):
    """Call direction"""
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    INTERNAL = "internal"


@dataclass
class CallMetadata:
    """Normalized call metadata"""
    external_call_id: str
    direction: CallDirection = CallDirection.INBOUND

    # Participants
    caller_number: Optional[str] = None
    callee_number: Optional[str] = None
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    agent_email: Optional[str] = None

    # Customer info (if available from CRM integration)
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None

    # Queue/routing info
    queue_id: Optional[str] = None
    queue_name: Optional[str] = None
    skills: List[str] = field(default_factory=list)

    # Timing
    started_at: Optional[datetime] = None
    answered_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None

    # Provider-specific
    provider_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "external_call_id": self.external_call_id,
            "direction": self.direction.value,
            "caller_number": self.caller_number,
            "callee_number": self.callee_number,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "agent_email": self.agent_email,
            "customer_id": self.customer_id,
            "customer_name": self.customer_name,
            "queue_id": self.queue_id,
            "queue_name": self.queue_name,
            "skills": self.skills,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "answered_at": self.answered_at.isoformat() if self.answered_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_seconds": self.duration_seconds,
            "provider_metadata": self.provider_metadata,
        }


@dataclass
class TranscriptionChunk:
    """Normalized transcription chunk"""
    external_call_id: str
    text: str
    speaker: Speaker = Speaker.UNKNOWN
    is_final: bool = False

    # Timing (seconds from call start)
    start_time: Optional[float] = None
    end_time: Optional[float] = None

    # Quality metrics
    confidence: Optional[float] = None
    language: Optional[str] = None

    # Provider-specific
    provider_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "external_call_id": self.external_call_id,
            "text": self.text,
            "speaker": self.speaker.value,
            "is_final": self.is_final,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "confidence": self.confidence,
            "language": self.language,
            "provider_metadata": self.provider_metadata,
        }


@dataclass
class WebhookEvent:
    """Normalized webhook event"""
    event_type: EventType
    external_call_id: str
    timestamp: datetime
    provider: str

    # Event-specific data
    call_metadata: Optional[CallMetadata] = None
    transcription: Optional[TranscriptionChunk] = None
    recording_url: Optional[str] = None

    # Raw payload for debugging
    raw_payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "external_call_id": self.external_call_id,
            "timestamp": self.timestamp.isoformat(),
            "provider": self.provider,
            "call_metadata": self.call_metadata.to_dict() if self.call_metadata else None,
            "transcription": self.transcription.to_dict() if self.transcription else None,
            "recording_url": self.recording_url,
        }


class BaseWebhookAdapter(ABC):
    """
    Abstract base class for webhook adapters.

    Each provider-specific adapter must implement:
    - verify_signature(): Validate webhook authenticity
    - parse_event(): Convert provider payload to normalized WebhookEvent
    - get_provider_name(): Return provider identifier
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize adapter with configuration.

        Args:
            config: Provider-specific configuration including:
                - webhook_secret: For signature verification
                - api_key: For API calls if needed
                - settings: Provider-specific settings
        """
        self.config = config
        self.webhook_secret = config.get('webhook_secret')

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider identifier (e.g., 'aircall', 'genesys')"""
        pass

    @abstractmethod
    def verify_signature(
        self,
        payload: bytes,
        signature: str,
        headers: Dict[str, str]
    ) -> bool:
        """
        Verify webhook signature to ensure authenticity.

        Args:
            payload: Raw request body bytes
            signature: Signature from request header
            headers: All request headers

        Returns:
            True if signature is valid, False otherwise
        """
        pass

    @abstractmethod
    def parse_event(self, payload: Dict[str, Any]) -> Optional[WebhookEvent]:
        """
        Parse provider-specific payload into normalized WebhookEvent.

        Args:
            payload: Parsed JSON payload from webhook

        Returns:
            Normalized WebhookEvent or None if event should be ignored
        """
        pass

    @abstractmethod
    def get_supported_events(self) -> List[EventType]:
        """Return list of event types this adapter can handle"""
        pass

    # =========================================================================
    # Utility methods for subclasses
    # =========================================================================

    def _verify_hmac_sha256(
        self,
        payload: bytes,
        signature: str,
        secret: str,
        prefix: str = ""
    ) -> bool:
        """
        Verify HMAC-SHA256 signature (common pattern).

        Args:
            payload: Raw payload bytes
            signature: Signature string (may have prefix like 'sha256=')
            secret: Webhook secret
            prefix: Prefix to strip from signature (e.g., 'sha256=')
        """
        if not secret:
            logger.warning(f"{self.provider_name}: No webhook secret configured, skipping verification")
            return True  # Allow in development, should be strict in production

        try:
            # Remove prefix if present
            if prefix and signature.startswith(prefix):
                signature = signature[len(prefix):]

            expected = hmac.new(
                secret.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()

            return hmac.compare_digest(expected.lower(), signature.lower())

        except Exception as e:
            logger.error(f"{self.provider_name}: Signature verification error: {e}")
            return False

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        """Parse datetime from various formats"""
        if value is None:
            return None

        if isinstance(value, datetime):
            return value

        if isinstance(value, (int, float)):
            # Unix timestamp
            return datetime.utcfromtimestamp(value)

        if isinstance(value, str):
            # Try ISO format
            try:
                return datetime.fromisoformat(value.replace('Z', '+00:00'))
            except ValueError:
                pass

            # Try common formats
            for fmt in [
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%d %H:%M:%S",
            ]:
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue

        logger.warning(f"{self.provider_name}: Could not parse datetime: {value}")
        return None

    def _safe_get(self, data: Dict, *keys, default=None):
        """Safely get nested dictionary value"""
        current = data
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return default
            if current is None:
                return default
        return current
