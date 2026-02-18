"""
Integration Module Tests

Tests for the cloud telephony integration system including:
- Webhook adapters (Aircall, Generic)
- Webhook processor
- Event parsing and normalization
"""
import pytest
import json
import hmac
import hashlib
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock

# Load environment variables before importing app modules
from dotenv import load_dotenv
load_dotenv()

# Import integration components
from app.integrations.adapters.base_adapter import (
    EventType,
    Speaker,
    CallDirection,
    CallMetadata,
    TranscriptionChunk,
    WebhookEvent,
)
from app.integrations.adapters.aircall_adapter import AircallAdapter
from app.integrations.adapters.generic_adapter import GenericWebhookAdapter


class TestEventTypes:
    """Test event type enums"""

    def test_event_type_values(self):
        assert EventType.CALL_STARTED.value == "call.started"
        assert EventType.CALL_ENDED.value == "call.ended"
        assert EventType.TRANSCRIPTION_FINAL.value == "transcription.final"

    def test_speaker_values(self):
        assert Speaker.CUSTOMER.value == "customer"
        assert Speaker.AGENT.value == "agent"

    def test_call_direction_values(self):
        assert CallDirection.INBOUND.value == "inbound"
        assert CallDirection.OUTBOUND.value == "outbound"


class TestCallMetadata:
    """Test CallMetadata dataclass"""

    def test_basic_metadata(self):
        metadata = CallMetadata(
            external_call_id="test-123",
            direction=CallDirection.INBOUND,
            caller_number="+33612345678",
            agent_id="agent-1"
        )
        assert metadata.external_call_id == "test-123"
        assert metadata.direction == CallDirection.INBOUND
        assert metadata.caller_number == "+33612345678"

    def test_to_dict(self):
        metadata = CallMetadata(
            external_call_id="test-123",
            direction=CallDirection.OUTBOUND,
        )
        result = metadata.to_dict()
        assert result["external_call_id"] == "test-123"
        assert result["direction"] == "outbound"


class TestTranscriptionChunk:
    """Test TranscriptionChunk dataclass"""

    def test_basic_transcription(self):
        chunk = TranscriptionChunk(
            external_call_id="test-123",
            text="Hello, how can I help?",
            speaker=Speaker.AGENT,
            is_final=True,
            confidence=0.95
        )
        assert chunk.text == "Hello, how can I help?"
        assert chunk.speaker == Speaker.AGENT
        assert chunk.is_final is True

    def test_to_dict(self):
        chunk = TranscriptionChunk(
            external_call_id="test-123",
            text="Test",
            speaker=Speaker.CUSTOMER,
        )
        result = chunk.to_dict()
        assert result["text"] == "Test"
        assert result["speaker"] == "customer"


class TestAircallAdapter:
    """Test Aircall webhook adapter"""

    @pytest.fixture
    def adapter(self):
        config = {
            "webhook_secret": "test-secret",
            "settings": {"webhook_token": "test-token"},
        }
        return AircallAdapter(config)

    def test_provider_name(self, adapter):
        assert adapter.provider_name == "aircall"

    def test_supported_events(self, adapter):
        events = adapter.get_supported_events()
        assert EventType.CALL_STARTED in events
        assert EventType.CALL_ENDED in events
        assert EventType.CALL_ANSWERED in events

    def test_parse_call_created(self, adapter):
        payload = {
            "resource": "call",
            "event": "call.created",
            "timestamp": 1609459200,
            "token": "test-token",
            "data": {
                "id": 123456,
                "direction": "inbound",
                "status": "initial",
                "started_at": 1609459100,
                "raw_digits": "+33612345678",
                "user": {
                    "id": 789,
                    "name": "John Doe",
                    "email": "john@company.com"
                },
                "contact": {
                    "id": 456,
                    "first_name": "Jane",
                    "last_name": "Customer"
                },
                "number": {
                    "id": 111,
                    "name": "Support Line",
                    "digits": "+33123456789"
                },
                "tags": ["support"]
            }
        }

        event = adapter.parse_event(payload)

        assert event is not None
        assert event.event_type == EventType.CALL_STARTED
        assert event.external_call_id == "123456"
        assert event.provider == "aircall"
        assert event.call_metadata is not None
        assert event.call_metadata.direction == CallDirection.INBOUND
        assert event.call_metadata.agent_name == "John Doe"
        assert event.call_metadata.customer_name == "Jane Customer"

    def test_parse_call_ended(self, adapter):
        payload = {
            "resource": "call",
            "event": "call.ended",
            "timestamp": 1609459300,
            "data": {
                "id": 123456,
                "direction": "inbound",
                "status": "done",
                "started_at": 1609459100,
                "answered_at": 1609459110,
                "ended_at": 1609459300,
                "duration": 190,
                "recording": "https://example.com/recording.mp3",
                "user": {"id": 789, "name": "John"},
                "number": {"id": 111}
            }
        }

        event = adapter.parse_event(payload)

        assert event is not None
        assert event.event_type == EventType.CALL_ENDED
        assert event.recording_url == "https://example.com/recording.mp3"
        assert event.call_metadata.duration_seconds == 190

    def test_parse_non_call_resource(self, adapter):
        payload = {
            "resource": "user",
            "event": "user.created",
            "data": {}
        }

        event = adapter.parse_event(payload)
        assert event is None

    def test_verify_signature_with_token(self, adapter):
        payload = json.dumps({"token": "test-token"}).encode()
        # Token verification should pass
        assert adapter.verify_signature(payload, "", {}) is True

    def test_verify_signature_with_hmac(self, adapter):
        payload = b'{"test": "data"}'
        secret = "test-secret"
        signature = "sha256=" + hmac.new(
            secret.encode(), payload, hashlib.sha256
        ).hexdigest()

        result = adapter.verify_signature(payload, signature, {})
        assert result is True


class TestGenericWebhookAdapter:
    """Test Generic webhook adapter"""

    @pytest.fixture
    def adapter(self):
        config = {"webhook_secret": "test-secret"}
        return GenericWebhookAdapter(config)

    def test_provider_name(self, adapter):
        assert adapter.provider_name == "generic"

    def test_supported_events(self, adapter):
        events = adapter.get_supported_events()
        # Generic adapter supports all event types
        assert len(events) == len(EventType)

    def test_parse_call_started(self, adapter):
        payload = {
            "event_type": "call.started",
            "call_id": "test-call-123",
            "timestamp": "2024-01-15T10:30:00Z",
            "data": {
                "direction": "inbound",
                "caller_number": "+33612345678",
                "agent_id": "agent-42",
                "agent_name": "Support Agent",
                "customer_name": "Test Customer"
            }
        }

        event = adapter.parse_event(payload)

        assert event is not None
        assert event.event_type == EventType.CALL_STARTED
        assert event.external_call_id == "test-call-123"
        assert event.call_metadata.caller_number == "+33612345678"
        assert event.call_metadata.agent_id == "agent-42"

    def test_parse_transcription_final(self, adapter):
        payload = {
            "event_type": "transcription.final",
            "call_id": "test-call-123",
            "timestamp": "2024-01-15T10:31:00Z",
            "data": {
                "text": "I need help with my alarm system",
                "speaker": "customer",
                "confidence": 0.95,
                "language": "en",
                "start_time": 5.0,
                "end_time": 8.5
            }
        }

        event = adapter.parse_event(payload)

        assert event is not None
        assert event.event_type == EventType.TRANSCRIPTION_FINAL
        assert event.transcription is not None
        assert event.transcription.text == "I need help with my alarm system"
        assert event.transcription.speaker == Speaker.CUSTOMER
        assert event.transcription.is_final is True
        assert event.transcription.confidence == 0.95

    def test_parse_call_ended(self, adapter):
        payload = {
            "event_type": "call.ended",
            "call_id": "test-call-123",
            "timestamp": "2024-01-15T10:35:00Z",
            "data": {
                "duration": 300,
                "end_time": "2024-01-15T10:35:00Z"
            }
        }

        event = adapter.parse_event(payload)

        assert event is not None
        assert event.event_type == EventType.CALL_ENDED

    def test_event_type_mapping_variations(self, adapter):
        """Test that various event type formats are properly mapped"""
        variations = [
            ("call.started", EventType.CALL_STARTED),
            ("call.start", EventType.CALL_STARTED),
            ("call.begin", EventType.CALL_STARTED),
            ("call.ended", EventType.CALL_ENDED),
            ("call.end", EventType.CALL_ENDED),
            ("call.hangup", EventType.CALL_ENDED),
            ("transcription", EventType.TRANSCRIPTION_FINAL),
            ("transcription.final", EventType.TRANSCRIPTION_FINAL),
        ]

        for event_str, expected in variations:
            result = adapter._map_event_type(event_str)
            assert result == expected, f"Failed for {event_str}"

    def test_speaker_mapping(self, adapter):
        """Test speaker role mapping"""
        payload_customer = {
            "event_type": "transcription.final",
            "call_id": "test",
            "data": {"text": "test", "speaker": "caller"}
        }
        event = adapter.parse_event(payload_customer)
        assert event.transcription.speaker == Speaker.CUSTOMER

        payload_agent = {
            "event_type": "transcription.final",
            "call_id": "test",
            "data": {"text": "test", "speaker": "representative"}
        }
        event = adapter.parse_event(payload_agent)
        assert event.transcription.speaker == Speaker.AGENT

    def test_verify_signature(self, adapter):
        payload = b'{"test": "data"}'
        secret = "test-secret"
        signature = hmac.new(
            secret.encode(), payload, hashlib.sha256
        ).hexdigest()

        result = adapter.verify_signature(payload, signature, {})
        assert result is True

    def test_missing_call_id(self, adapter):
        payload = {
            "event_type": "call.started",
            "data": {}
        }
        event = adapter.parse_event(payload)
        assert event is None


class TestWebhookProcessor:
    """Test the webhook processor"""

    @pytest.fixture
    def processor(self):
        from app.integrations.webhook_processor import WebhookProcessor
        return WebhookProcessor()

    def test_adapters_registered(self, processor):
        """Verify adapters are registered"""
        assert "aircall" in processor._adapters
        assert "generic" in processor._adapters

    def test_get_adapter_creates_instance(self, processor):
        """Test adapter instance creation"""
        # Create a mock integration config
        mock_config = Mock()
        mock_config.id = 1
        mock_config.provider = Mock()
        mock_config.provider.value = "generic"
        mock_config.webhook_secret = "test-secret"
        mock_config.credentials = {}
        mock_config.settings = {}
        mock_config.metadata_mapping = {}

        adapter = processor.get_adapter(mock_config)

        assert adapter is not None
        assert adapter.provider_name == "generic"
        # Should be cached
        assert processor._adapter_instances[1] == adapter


class TestIntegrationEndToEnd:
    """End-to-end integration tests"""

    def test_aircall_to_normalized_event(self):
        """Test complete flow from Aircall payload to normalized event"""
        adapter = AircallAdapter({"webhook_secret": None})

        # Simulate Aircall webhook
        aircall_payload = {
            "resource": "call",
            "event": "call.created",
            "timestamp": 1609459200,
            "data": {
                "id": 999,
                "direction": "inbound",
                "raw_digits": "+33612345678",
                "user": {"id": 1, "name": "Agent Smith"},
                "contact": {"first_name": "John", "last_name": "Doe"},
                "number": {"digits": "+33123456789", "name": "Support"}
            }
        }

        event = adapter.parse_event(aircall_payload)

        # Verify normalized structure
        assert isinstance(event, WebhookEvent)
        assert event.event_type == EventType.CALL_STARTED
        assert event.external_call_id == "999"
        assert event.provider == "aircall"

        # Verify metadata extraction
        assert event.call_metadata.caller_number == "+33612345678"
        assert event.call_metadata.agent_name == "Agent Smith"
        assert event.call_metadata.customer_name == "John Doe"

    def test_generic_transcription_flow(self):
        """Test transcription event handling"""
        adapter = GenericWebhookAdapter({})

        # Start call
        start_event = adapter.parse_event({
            "event_type": "call.started",
            "call_id": "flow-test",
            "data": {"agent_id": "agent-1", "direction": "inbound"}
        })
        assert start_event.event_type == EventType.CALL_STARTED

        # Receive transcription
        trans_event = adapter.parse_event({
            "event_type": "transcription.final",
            "call_id": "flow-test",
            "data": {
                "text": "My alarm keeps going off",
                "speaker": "customer",
                "confidence": 0.92
            }
        })
        assert trans_event.event_type == EventType.TRANSCRIPTION_FINAL
        assert trans_event.transcription.text == "My alarm keeps going off"
        assert trans_event.transcription.speaker == Speaker.CUSTOMER

        # End call
        end_event = adapter.parse_event({
            "event_type": "call.ended",
            "call_id": "flow-test",
            "data": {"duration": 120}
        })
        assert end_event.event_type == EventType.CALL_ENDED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
