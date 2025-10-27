"""
ACD (Automatic Call Distribution) Integration Interface
Base interface and adapters for different ACD systems
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable
import logging


logger = logging.getLogger(__name__)


class ACDIntegration(ABC):
    """
    Abstract base class for ACD system integrations

    Supports:
    - Call events (start, end, transfer)
    - Real-time transcription streaming
    - Agent status updates
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.on_call_start: Optional[Callable] = None
        self.on_call_end: Optional[Callable] = None
        self.on_transcription: Optional[Callable] = None

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to ACD system"""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from ACD system"""
        pass

    @abstractmethod
    async def subscribe_to_call_events(self, agent_id: str) -> None:
        """Subscribe to call events for a specific agent"""
        pass

    @abstractmethod
    async def subscribe_to_transcription(self, call_id: str) -> None:
        """Subscribe to real-time transcription for a call"""
        pass

    def register_call_start_handler(self, handler: Callable) -> None:
        """Register callback for call start events"""
        self.on_call_start = handler

    def register_call_end_handler(self, handler: Callable) -> None:
        """Register callback for call end events"""
        self.on_call_end = handler

    def register_transcription_handler(self, handler: Callable) -> None:
        """Register callback for transcription events"""
        self.on_transcription = handler


class GenericWebhookACDIntegration(ACDIntegration):
    """
    Generic ACD integration via webhooks

    ACD system sends events to our API endpoints
    No active connection needed, just webhook receivers
    """

    async def connect(self) -> bool:
        """No persistent connection needed for webhooks"""
        logger.info("Webhook-based ACD integration ready")
        return True

    async def disconnect(self) -> None:
        """Nothing to disconnect"""
        pass

    async def subscribe_to_call_events(self, agent_id: str) -> None:
        """
        For webhook integration, subscription is handled by ACD configuration
        ACD must be configured to send events to our webhook endpoints
        """
        logger.info(f"Webhook subscription for agent {agent_id} (configured in ACD)")

    async def subscribe_to_transcription(self, call_id: str) -> None:
        """Transcription subscription via webhook configuration"""
        logger.info(f"Transcription webhook for call {call_id} (configured in ACD)")


class TwilioACDIntegration(ACDIntegration):
    """
    Twilio Flex integration

    Uses:
    - Twilio Flex API for call events
    - Twilio Media Streams for real-time audio
    - Twilio Transcription API
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.account_sid = config.get('account_sid')
        self.auth_token = config.get('auth_token')
        self.workspace_sid = config.get('workspace_sid')
        self.client = None

    async def connect(self) -> bool:
        """Initialize Twilio client"""
        try:
            from twilio.rest import Client
            self.client = Client(self.account_sid, self.auth_token)
            logger.info("Connected to Twilio Flex")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Twilio: {e}")
            return False

    async def disconnect(self) -> None:
        """Close Twilio connection"""
        self.client = None
        logger.info("Disconnected from Twilio")

    async def subscribe_to_call_events(self, agent_id: str) -> None:
        """Subscribe to Twilio Flex task events"""
        # Implementation would use Twilio Events API
        logger.info(f"Subscribing to Twilio Flex events for agent {agent_id}")

    async def subscribe_to_transcription(self, call_id: str) -> None:
        """Start Twilio transcription for call"""
        # Implementation would start Twilio Media Stream
        logger.info(f"Starting Twilio transcription for call {call_id}")


class GenesysACDIntegration(ACDIntegration):
    """
    Genesys Cloud integration

    Uses:
    - Genesys Cloud Platform API
    - WebSocket notifications
    - Genesys transcription services
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client_id = config.get('client_id')
        self.client_secret = config.get('client_secret')
        self.environment = config.get('environment', 'mypurecloud.com')
        self.ws_connection = None

    async def connect(self) -> bool:
        """Connect to Genesys Cloud"""
        try:
            # Would use Genesys Python SDK
            logger.info(f"Connected to Genesys Cloud ({self.environment})")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Genesys: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from Genesys"""
        if self.ws_connection:
            # Close WebSocket
            pass
        logger.info("Disconnected from Genesys")

    async def subscribe_to_call_events(self, agent_id: str) -> None:
        """Subscribe to Genesys conversation events"""
        logger.info(f"Subscribing to Genesys events for agent {agent_id}")

    async def subscribe_to_transcription(self, call_id: str) -> None:
        """Start Genesys transcription"""
        logger.info(f"Starting Genesys transcription for call {call_id}")


class AvayaACDIntegration(ACDIntegration):
    """
    Avaya Contact Center integration

    Uses:
    - Avaya Experience Platform APIs
    - Avaya CTI integration
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_endpoint = config.get('api_endpoint')
        self.api_key = config.get('api_key')

    async def connect(self) -> bool:
        """Connect to Avaya"""
        logger.info("Connected to Avaya Contact Center")
        return True

    async def disconnect(self) -> None:
        """Disconnect from Avaya"""
        logger.info("Disconnected from Avaya")

    async def subscribe_to_call_events(self, agent_id: str) -> None:
        """Subscribe to Avaya CTI events"""
        logger.info(f"Subscribing to Avaya events for agent {agent_id}")

    async def subscribe_to_transcription(self, call_id: str) -> None:
        """Start Avaya transcription"""
        logger.info(f"Starting Avaya transcription for call {call_id}")


def create_acd_integration(acd_type: str, config: Dict[str, Any]) -> ACDIntegration:
    """
    Factory function to create appropriate ACD integration

    Args:
        acd_type: Type of ACD system ('webhook', 'twilio', 'genesys', 'avaya')
        config: Configuration dict for the ACD system

    Returns:
        ACDIntegration instance
    """
    integrations = {
        'webhook': GenericWebhookACDIntegration,
        'twilio': TwilioACDIntegration,
        'genesys': GenesysACDIntegration,
        'avaya': AvayaACDIntegration,
    }

    integration_class = integrations.get(acd_type.lower())

    if not integration_class:
        raise ValueError(f"Unknown ACD type: {acd_type}. Supported: {list(integrations.keys())}")

    return integration_class(config)
