"""
Enterprise Telephony Integrations

This module provides integration with external telephony systems:
- Mode 1: Cloud telephony via webhooks (Aircall, Genesys Cloud, Talkdesk)
- Mode 2: On-premise PBX via SIPREC (Avaya, Cisco, Genesys PureConnect)

The architecture follows a sidecar pattern where we receive copies of
call events and transcriptions without controlling calls directly.
"""

from app.integrations.adapters.base_adapter import (
    BaseWebhookAdapter,
    WebhookEvent,
    EventType,
    TranscriptionChunk,
    CallMetadata,
)
from app.integrations.webhook_processor import WebhookProcessor, get_webhook_processor

__all__ = [
    'BaseWebhookAdapter',
    'WebhookEvent',
    'EventType',
    'TranscriptionChunk',
    'CallMetadata',
    'WebhookProcessor',
    'get_webhook_processor',
]
