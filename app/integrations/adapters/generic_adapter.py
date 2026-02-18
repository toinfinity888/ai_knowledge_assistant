"""
Generic Webhook Adapter

Handles webhooks from custom telephony integrations using a standardized format.
This is useful for clients who want to build their own integration layer.

Expected webhook format:
{
    "event_type": "call.started" | "call.ended" | "transcription" | ...,
    "call_id": "external-call-id",
    "timestamp": "2024-01-15T10:30:00Z",  // ISO format
    "data": {
        // Event-specific data
    }
}
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from app.integrations.adapters.base_adapter import (
    BaseWebhookAdapter,
    WebhookEvent,
    EventType,
    CallMetadata,
    TranscriptionChunk,
    CallDirection,
    Speaker,
)

logger = logging.getLogger(__name__)


class GenericWebhookAdapter(BaseWebhookAdapter):
    """
    Generic adapter for custom webhook integrations.

    Clients can send webhooks in our standardized format,
    making it easy to integrate any telephony system.
    """

    @property
    def provider_name(self) -> str:
        return "generic"

    def get_supported_events(self) -> List[EventType]:
        return list(EventType)  # Supports all event types

    def verify_signature(
        self,
        payload: bytes,
        signature: str,
        headers: Dict[str, str]
    ) -> bool:
        """Verify HMAC-SHA256 signature"""
        if not self.webhook_secret:
            logger.warning("Generic: No webhook secret configured")
            return True

        if not signature:
            return False

        return self._verify_hmac_sha256(
            payload=payload,
            signature=signature,
            secret=self.webhook_secret,
            prefix=""  # No prefix expected
        )

    def parse_event(self, payload: Dict[str, Any]) -> Optional[WebhookEvent]:
        """
        Parse generic webhook payload.

        Expected format:
        {
            "event_type": "call.started",
            "call_id": "abc123",
            "timestamp": "2024-01-15T10:30:00Z",
            "data": {
                "caller_number": "+33612345678",
                "agent_id": "agent-42",
                ...
            }
        }
        """
        try:
            event_type_str = payload.get('event_type', '')
            call_id = payload.get('call_id')
            timestamp_str = payload.get('timestamp')
            data = payload.get('data', {})

            if not call_id:
                logger.warning("Generic: Missing call_id in payload")
                return None

            # Map event type
            event_type = self._map_event_type(event_type_str)
            if event_type == EventType.UNKNOWN:
                logger.debug(f"Generic: Unknown event type: {event_type_str}")
                return None

            # Parse timestamp
            timestamp = self._parse_datetime(timestamp_str) or datetime.now(timezone.utc)

            # Parse based on event type
            call_metadata = None
            transcription = None
            recording_url = None

            if event_type in [EventType.CALL_STARTED, EventType.CALL_ANSWERED, EventType.CALL_ENDED]:
                call_metadata = self._parse_call_metadata(call_id, data)

            if event_type in [EventType.TRANSCRIPTION_PARTIAL, EventType.TRANSCRIPTION_FINAL]:
                transcription = self._parse_transcription(call_id, data, event_type)

            if event_type == EventType.RECORDING_AVAILABLE:
                recording_url = data.get('recording_url')

            return WebhookEvent(
                event_type=event_type,
                external_call_id=str(call_id),
                timestamp=timestamp,
                provider=self.provider_name,
                call_metadata=call_metadata,
                transcription=transcription,
                recording_url=recording_url,
                raw_payload=payload,
            )

        except Exception as e:
            logger.exception(f"Generic: Error parsing webhook: {e}")
            return None

    def _map_event_type(self, event_type_str: str) -> EventType:
        """Map string event type to EventType enum"""
        # Normalize: lowercase and replace underscores with dots
        normalized = event_type_str.lower().replace('_', '.')

        # Direct mapping
        for event_type in EventType:
            if event_type.value == normalized:
                return event_type

        # Fuzzy matching for common variations
        mappings = {
            'call.start': EventType.CALL_STARTED,
            'call.begin': EventType.CALL_STARTED,
            'call.initiated': EventType.CALL_STARTED,
            'call.answer': EventType.CALL_ANSWERED,
            'call.connected': EventType.CALL_ANSWERED,
            'call.end': EventType.CALL_ENDED,
            'call.complete': EventType.CALL_ENDED,
            'call.completed': EventType.CALL_ENDED,
            'call.hangup': EventType.CALL_ENDED,
            'call.terminated': EventType.CALL_ENDED,
            'transcription': EventType.TRANSCRIPTION_FINAL,
            'transcript': EventType.TRANSCRIPTION_FINAL,
            'transcription.partial': EventType.TRANSCRIPTION_PARTIAL,
            'transcription.final': EventType.TRANSCRIPTION_FINAL,
            'transcription.complete': EventType.TRANSCRIPTION_FINAL,
            'recording': EventType.RECORDING_AVAILABLE,
            'recording.ready': EventType.RECORDING_AVAILABLE,
            'recording.completed': EventType.RECORDING_AVAILABLE,
        }

        return mappings.get(normalized, EventType.UNKNOWN)

    def _parse_call_metadata(self, call_id: str, data: Dict[str, Any]) -> CallMetadata:
        """Parse call metadata from generic data format"""
        # Direction
        direction_str = data.get('direction', 'inbound').lower()
        if direction_str in ['out', 'outbound', 'outgoing']:
            direction = CallDirection.OUTBOUND
        elif direction_str in ['internal']:
            direction = CallDirection.INTERNAL
        else:
            direction = CallDirection.INBOUND

        return CallMetadata(
            external_call_id=str(call_id),
            direction=direction,
            caller_number=data.get('caller_number') or data.get('from_number') or data.get('from'),
            callee_number=data.get('callee_number') or data.get('to_number') or data.get('to'),
            agent_id=data.get('agent_id') or data.get('user_id'),
            agent_name=data.get('agent_name') or data.get('user_name'),
            agent_email=data.get('agent_email') or data.get('user_email'),
            customer_id=data.get('customer_id') or data.get('contact_id'),
            customer_name=data.get('customer_name') or data.get('contact_name'),
            queue_id=data.get('queue_id'),
            queue_name=data.get('queue_name') or data.get('queue'),
            skills=data.get('skills') or data.get('tags') or [],
            started_at=self._parse_datetime(data.get('started_at') or data.get('start_time')),
            answered_at=self._parse_datetime(data.get('answered_at') or data.get('answer_time')),
            ended_at=self._parse_datetime(data.get('ended_at') or data.get('end_time')),
            duration_seconds=data.get('duration') or data.get('duration_seconds'),
            provider_metadata=data.get('metadata') or {},
        )

    def _parse_transcription(
        self,
        call_id: str,
        data: Dict[str, Any],
        event_type: EventType
    ) -> TranscriptionChunk:
        """Parse transcription from generic data format"""
        # Speaker
        speaker_str = (data.get('speaker') or data.get('role') or 'unknown').lower()
        if speaker_str in ['agent', 'user', 'representative', 'support']:
            speaker = Speaker.AGENT
        elif speaker_str in ['customer', 'caller', 'client', 'contact']:
            speaker = Speaker.CUSTOMER
        elif speaker_str in ['system', 'ivr', 'bot']:
            speaker = Speaker.SYSTEM
        else:
            speaker = Speaker.UNKNOWN

        return TranscriptionChunk(
            external_call_id=str(call_id),
            text=data.get('text') or data.get('transcript') or '',
            speaker=speaker,
            is_final=event_type == EventType.TRANSCRIPTION_FINAL,
            start_time=data.get('start_time'),
            end_time=data.get('end_time'),
            confidence=data.get('confidence'),
            language=data.get('language') or data.get('lang'),
            provider_metadata=data.get('metadata') or {},
        )
