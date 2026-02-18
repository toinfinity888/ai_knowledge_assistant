"""
Telephony Provider Adapters

Each adapter handles provider-specific webhook formats and normalizes
them to our internal event schema.
"""

from app.integrations.adapters.base_adapter import (
    BaseWebhookAdapter,
    WebhookEvent,
    EventType,
    TranscriptionChunk,
    CallMetadata,
)

__all__ = [
    'BaseWebhookAdapter',
    'WebhookEvent',
    'EventType',
    'TranscriptionChunk',
    'CallMetadata',
]
