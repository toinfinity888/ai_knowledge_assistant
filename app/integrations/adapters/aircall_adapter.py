"""
Aircall Webhook Adapter

Handles webhooks from Aircall cloud telephony platform.
Documentation: https://developer.aircall.io/api-references/#webhooks

Supported events:
- call.created, call.ringing, call.answered, call.ended
- call.transferred, call.hungup
- call.commented (post-call notes)
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


class AircallAdapter(BaseWebhookAdapter):
    """
    Adapter for Aircall webhooks.

    Aircall webhook payload format:
    {
        "resource": "call",
        "event": "call.ended",
        "timestamp": 1609459200,
        "token": "webhook_token",
        "data": {
            "id": 123456,
            "direct_link": "https://...",
            "direction": "inbound",
            "status": "done",
            "started_at": 1609459100,
            "answered_at": 1609459110,
            "ended_at": 1609459200,
            "duration": 90,
            "raw_digits": "+33612345678",
            "user": {
                "id": 789,
                "name": "John Doe",
                "email": "john@company.com"
            },
            "contact": {
                "id": 456,
                "first_name": "Jane",
                "last_name": "Customer",
                "phone_numbers": [{"value": "+33612345678"}]
            },
            "number": {
                "id": 111,
                "name": "Support Line",
                "digits": "+33123456789"
            },
            "tags": ["support", "billing"],
            "recording": "https://...",
            "voicemail": null,
            "asset": null
        }
    }
    """

    @property
    def provider_name(self) -> str:
        return "aircall"

    def get_supported_events(self) -> List[EventType]:
        return [
            EventType.CALL_STARTED,
            EventType.CALL_RINGING,
            EventType.CALL_ANSWERED,
            EventType.CALL_ENDED,
            EventType.CALL_TRANSFERRED,
            EventType.RECORDING_AVAILABLE,
        ]

    def verify_signature(
        self,
        payload: bytes,
        signature: str,
        headers: Dict[str, str]
    ) -> bool:
        """
        Verify Aircall webhook signature.

        Aircall uses a token-based verification where the token
        in the payload must match the configured webhook token.
        For enhanced security, they also support HMAC signatures.
        """
        # Method 1: Token verification (simpler)
        webhook_token = self.config.get('settings', {}).get('webhook_token')
        if webhook_token:
            try:
                import json
                payload_dict = json.loads(payload.decode('utf-8'))
                if payload_dict.get('token') == webhook_token:
                    return True
            except Exception:
                pass

        # Method 2: HMAC-SHA256 signature
        if self.webhook_secret and signature:
            return self._verify_hmac_sha256(
                payload=payload,
                signature=signature,
                secret=self.webhook_secret,
                prefix="sha256="
            )

        # If no verification configured, allow (development mode)
        if not self.webhook_secret and not webhook_token:
            logger.warning("Aircall: No webhook verification configured")
            return True

        return False

    def parse_event(self, payload: Dict[str, Any]) -> Optional[WebhookEvent]:
        """Parse Aircall webhook payload into normalized event"""
        try:
            resource = payload.get('resource')
            event_name = payload.get('event', '')
            timestamp = payload.get('timestamp')
            data = payload.get('data', {})

            if resource != 'call':
                logger.debug(f"Aircall: Ignoring non-call resource: {resource}")
                return None

            # Map Aircall event to our event type
            event_type = self._map_event_type(event_name)
            if event_type == EventType.UNKNOWN:
                logger.debug(f"Aircall: Ignoring unmapped event: {event_name}")
                return None

            # Extract call ID
            call_id = str(data.get('id', ''))
            if not call_id:
                logger.warning("Aircall: Missing call ID in payload")
                return None

            # Parse timestamp
            event_time = self._parse_datetime(timestamp) or datetime.now(timezone.utc)

            # Build call metadata
            call_metadata = self._parse_call_metadata(data)

            # Check for recording
            recording_url = data.get('recording')

            # Create event
            event = WebhookEvent(
                event_type=event_type,
                external_call_id=call_id,
                timestamp=event_time,
                provider=self.provider_name,
                call_metadata=call_metadata,
                recording_url=recording_url if event_type == EventType.CALL_ENDED else None,
                raw_payload=payload,
            )

            return event

        except Exception as e:
            logger.exception(f"Aircall: Error parsing webhook: {e}")
            return None

    def _map_event_type(self, event_name: str) -> EventType:
        """Map Aircall event name to our EventType"""
        mapping = {
            'call.created': EventType.CALL_STARTED,
            'call.ringing': EventType.CALL_RINGING,
            'call.answered': EventType.CALL_ANSWERED,
            'call.ended': EventType.CALL_ENDED,
            'call.hungup': EventType.CALL_ENDED,
            'call.transferred': EventType.CALL_TRANSFERRED,
            'call.voicemail_left': EventType.CALL_ENDED,
        }
        return mapping.get(event_name, EventType.UNKNOWN)

    def _parse_call_metadata(self, data: Dict[str, Any]) -> CallMetadata:
        """Parse call metadata from Aircall data"""
        # Direction
        direction_str = data.get('direction', 'inbound')
        direction = CallDirection.INBOUND if direction_str == 'inbound' else CallDirection.OUTBOUND

        # User (agent) info
        user = data.get('user') or {}
        agent_id = str(user.get('id', '')) if user.get('id') else None
        agent_name = user.get('name')
        agent_email = user.get('email')

        # Contact (customer) info
        contact = data.get('contact') or {}
        customer_id = str(contact.get('id', '')) if contact.get('id') else None
        customer_name = None
        if contact.get('first_name') or contact.get('last_name'):
            customer_name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()

        # Phone numbers
        caller_number = data.get('raw_digits')
        number_info = data.get('number') or {}
        callee_number = number_info.get('digits')

        # Timing
        started_at = self._parse_datetime(data.get('started_at'))
        answered_at = self._parse_datetime(data.get('answered_at'))
        ended_at = self._parse_datetime(data.get('ended_at'))
        duration = data.get('duration')

        # Tags as skills
        tags = data.get('tags') or []

        return CallMetadata(
            external_call_id=str(data.get('id', '')),
            direction=direction,
            caller_number=caller_number,
            callee_number=callee_number,
            agent_id=agent_id,
            agent_name=agent_name,
            agent_email=agent_email,
            customer_id=customer_id,
            customer_name=customer_name,
            queue_name=number_info.get('name'),
            skills=tags,
            started_at=started_at,
            answered_at=answered_at,
            ended_at=ended_at,
            duration_seconds=duration,
            provider_metadata={
                'direct_link': data.get('direct_link'),
                'status': data.get('status'),
                'number_id': number_info.get('id'),
                'user_availability': user.get('availability'),
            }
        )


class AircallTranscriptionAdapter(BaseWebhookAdapter):
    """
    Adapter for Aircall Transcription webhooks.

    Aircall's AI transcription sends separate webhooks with
    transcription data. This adapter handles those events.

    Note: Aircall transcription is an add-on feature.
    """

    @property
    def provider_name(self) -> str:
        return "aircall_transcription"

    def get_supported_events(self) -> List[EventType]:
        return [
            EventType.TRANSCRIPTION_PARTIAL,
            EventType.TRANSCRIPTION_FINAL,
        ]

    def verify_signature(
        self,
        payload: bytes,
        signature: str,
        headers: Dict[str, str]
    ) -> bool:
        """Use same verification as main Aircall adapter"""
        if self.webhook_secret and signature:
            return self._verify_hmac_sha256(
                payload=payload,
                signature=signature,
                secret=self.webhook_secret,
                prefix="sha256="
            )
        return True

    def parse_event(self, payload: Dict[str, Any]) -> Optional[WebhookEvent]:
        """
        Parse Aircall transcription webhook.

        Expected format (varies by Aircall version):
        {
            "event": "transcription.completed",
            "call_id": 123456,
            "transcription": {
                "segments": [
                    {
                        "speaker": "agent",
                        "text": "Hello, how can I help?",
                        "start_time": 0.5,
                        "end_time": 2.1,
                        "confidence": 0.95
                    },
                    ...
                ]
            }
        }
        """
        try:
            event_name = payload.get('event', '')
            call_id = str(payload.get('call_id', ''))

            if not call_id:
                return None

            if 'transcription' not in event_name.lower():
                return None

            transcription_data = payload.get('transcription', {})
            segments = transcription_data.get('segments', [])

            if not segments:
                return None

            # For now, combine all segments into one event
            # In a more sophisticated implementation, we'd emit multiple events
            full_text = ' '.join(seg.get('text', '') for seg in segments)

            # Determine primary speaker
            speaker_counts = {}
            for seg in segments:
                spk = seg.get('speaker', 'unknown')
                speaker_counts[spk] = speaker_counts.get(spk, 0) + 1

            primary_speaker = max(speaker_counts, key=speaker_counts.get) if speaker_counts else 'unknown'
            speaker = Speaker.AGENT if primary_speaker == 'agent' else Speaker.CUSTOMER

            transcription = TranscriptionChunk(
                external_call_id=call_id,
                text=full_text,
                speaker=speaker,
                is_final=True,
                start_time=segments[0].get('start_time') if segments else None,
                end_time=segments[-1].get('end_time') if segments else None,
                confidence=sum(s.get('confidence', 0) for s in segments) / len(segments) if segments else None,
                provider_metadata={'segment_count': len(segments)}
            )

            return WebhookEvent(
                event_type=EventType.TRANSCRIPTION_FINAL,
                external_call_id=call_id,
                timestamp=datetime.now(timezone.utc),
                provider=self.provider_name,
                transcription=transcription,
                raw_payload=payload,
            )

        except Exception as e:
            logger.exception(f"Aircall Transcription: Error parsing webhook: {e}")
            return None
