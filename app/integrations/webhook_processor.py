"""
Webhook Processor for Cloud Telephony Integrations

Handles incoming webhooks from various telephony providers:
1. Validates webhook signatures
2. Routes to appropriate provider adapter
3. Normalizes events to internal schema
4. Creates/updates sessions and forwards to AI pipeline
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Type

from app.models.integration_config import IntegrationConfig, IntegrationProvider
from app.database.postgresql_session import get_db_session
from app.integrations.adapters.base_adapter import (
    BaseWebhookAdapter,
    WebhookEvent,
    EventType,
)

logger = logging.getLogger(__name__)


class WebhookProcessor:
    """
    Central processor for all incoming webhooks.

    Responsibilities:
    - Load adapter for the given integration
    - Verify webhook signature
    - Parse and normalize events
    - Create/update call sessions
    - Forward transcriptions to AI pipeline
    """

    def __init__(self):
        self._adapters: Dict[str, Type[BaseWebhookAdapter]] = {}
        self._adapter_instances: Dict[int, BaseWebhookAdapter] = {}  # By integration_id
        self._register_adapters()

    def _register_adapters(self):
        """Register available adapters"""
        # Import adapters here to avoid circular imports
        try:
            from app.integrations.adapters.aircall_adapter import AircallAdapter
            self._adapters['aircall'] = AircallAdapter
        except ImportError:
            logger.debug("Aircall adapter not available")

        try:
            from app.integrations.adapters.genesys_adapter import GenesysCloudAdapter
            self._adapters['genesys_cloud'] = GenesysCloudAdapter
        except ImportError:
            logger.debug("Genesys Cloud adapter not available")

        try:
            from app.integrations.adapters.talkdesk_adapter import TalkdeskAdapter
            self._adapters['talkdesk'] = TalkdeskAdapter
        except ImportError:
            logger.debug("Talkdesk adapter not available")

        try:
            from app.integrations.adapters.generic_adapter import GenericWebhookAdapter
            self._adapters['generic'] = GenericWebhookAdapter
        except ImportError:
            logger.debug("Generic adapter not available")

        logger.info(f"Registered webhook adapters: {list(self._adapters.keys())}")

    def get_adapter(
        self,
        integration_config: IntegrationConfig
    ) -> Optional[BaseWebhookAdapter]:
        """
        Get or create adapter instance for an integration.

        Args:
            integration_config: The integration configuration

        Returns:
            Adapter instance or None if provider not supported
        """
        # Check cache
        if integration_config.id in self._adapter_instances:
            return self._adapter_instances[integration_config.id]

        # Get adapter class
        provider = integration_config.provider.value if integration_config.provider else None
        adapter_class = self._adapters.get(provider)

        if not adapter_class:
            logger.error(f"No adapter available for provider: {provider}")
            return None

        # Create adapter instance
        config = {
            'webhook_secret': integration_config.webhook_secret,
            'credentials': integration_config.credentials or {},
            'settings': integration_config.settings or {},
            'metadata_mapping': integration_config.metadata_mapping or {},
        }

        adapter = adapter_class(config)
        self._adapter_instances[integration_config.id] = adapter

        return adapter

    def process_webhook(
        self,
        company_id: int,
        provider: str,
        integration_id: str,
        payload: bytes,
        headers: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Process an incoming webhook.

        Args:
            company_id: Company ID from authentication
            provider: Provider name (e.g., 'aircall')
            integration_id: Integration identifier
            payload: Raw request body
            headers: Request headers

        Returns:
            Processing result with status and any errors
        """
        result = {
            "status": "received",
            "provider": provider,
            "integration_id": integration_id,
            "processed": False,
            "error": None,
        }

        try:
            # Load integration config
            with get_db_session() as db:
                integration = db.query(IntegrationConfig).filter(
                    IntegrationConfig.company_id == company_id,
                    IntegrationConfig.integration_id == integration_id,
                    IntegrationConfig.is_active == True,
                ).first()

                if not integration:
                    result["error"] = "Integration not found or inactive"
                    result["status"] = "error"
                    logger.warning(
                        f"Webhook received for unknown integration: "
                        f"company={company_id}, integration={integration_id}"
                    )
                    return result

                # Get adapter
                adapter = self.get_adapter(integration)
                if not adapter:
                    result["error"] = f"No adapter for provider: {provider}"
                    result["status"] = "error"
                    return result

                # Verify signature
                signature = self._extract_signature(headers, provider)
                if signature and not adapter.verify_signature(payload, signature, headers):
                    result["error"] = "Invalid webhook signature"
                    result["status"] = "error"
                    logger.warning(
                        f"Invalid signature for webhook: "
                        f"company={company_id}, provider={provider}"
                    )
                    return result

                # Parse payload
                import json
                try:
                    payload_dict = json.loads(payload.decode('utf-8'))
                except json.JSONDecodeError as e:
                    result["error"] = f"Invalid JSON payload: {e}"
                    result["status"] = "error"
                    return result

                # Parse event
                event = adapter.parse_event(payload_dict)
                if not event:
                    result["status"] = "ignored"
                    result["message"] = "Event type not handled"
                    return result

                # Record event received
                integration.record_event()
                db.commit()

                # Process the event
                process_result = self._process_event(
                    event=event,
                    integration=integration,
                    company_id=company_id,
                    db=db,
                )

                result.update(process_result)
                result["processed"] = True
                result["status"] = "success"
                result["event_type"] = event.event_type.value

        except Exception as e:
            logger.exception(f"Error processing webhook: {e}")
            result["error"] = str(e)
            result["status"] = "error"

        return result

    def _extract_signature(self, headers: Dict[str, str], provider: str) -> Optional[str]:
        """Extract signature from headers based on provider"""
        # Normalize header names to lowercase
        headers_lower = {k.lower(): v for k, v in headers.items()}

        # Provider-specific signature headers
        signature_headers = {
            'aircall': ['x-aircall-signature', 'x-signature'],
            'genesys_cloud': ['x-genesys-signature'],
            'talkdesk': ['x-talkdesk-signature'],
            'generic': ['x-webhook-signature', 'x-signature'],
        }

        for header in signature_headers.get(provider, ['x-signature']):
            if header in headers_lower:
                return headers_lower[header]

        return None

    def _process_event(
        self,
        event: WebhookEvent,
        integration: IntegrationConfig,
        company_id: int,
        db,
    ) -> Dict[str, Any]:
        """
        Process a normalized webhook event.

        Routes to appropriate handler based on event type.
        """
        result = {"event_id": event.external_call_id}

        try:
            if event.event_type == EventType.CALL_STARTED:
                result.update(self._handle_call_started(event, integration, company_id, db))

            elif event.event_type == EventType.CALL_ANSWERED:
                result.update(self._handle_call_answered(event, integration, company_id, db))

            elif event.event_type == EventType.CALL_ENDED:
                result.update(self._handle_call_ended(event, integration, company_id, db))

            elif event.event_type in [EventType.TRANSCRIPTION_PARTIAL, EventType.TRANSCRIPTION_FINAL]:
                result.update(self._handle_transcription(event, integration, company_id, db))

            elif event.event_type == EventType.RECORDING_AVAILABLE:
                result.update(self._handle_recording(event, integration, company_id, db))

            else:
                result["message"] = f"Event type {event.event_type.value} logged but not processed"

        except Exception as e:
            logger.exception(f"Error processing event {event.event_type}: {e}")
            result["error"] = str(e)

        return result

    def _handle_call_started(
        self,
        event: WebhookEvent,
        integration: IntegrationConfig,
        company_id: int,
        db,
    ) -> Dict[str, Any]:
        """Handle call.started event - create session"""
        from app.models.call_session import CallSession, CallStatus

        # Check if session already exists
        existing = db.query(CallSession).filter(
            CallSession.company_id == company_id,
            CallSession.call_id == event.external_call_id,
        ).first()

        if existing:
            logger.info(f"Session already exists for call: {event.external_call_id}")
            return {"session_id": existing.session_id, "action": "existing"}

        # Create new session
        metadata = event.call_metadata
        session = CallSession(
            company_id=company_id,
            call_id=event.external_call_id,
            session_id=event.external_call_id,  # Use external ID as session ID
            status=CallStatus.ACTIVE,
            customer_phone=metadata.caller_number if metadata else None,
            customer_name=metadata.customer_name if metadata else None,
            customer_id=metadata.customer_id if metadata else None,
            agent_id=metadata.agent_id if metadata else None,
            agent_name=metadata.agent_name if metadata else None,
            start_time=event.timestamp,
            acd_metadata={
                "provider": event.provider,
                "integration_id": integration.integration_id,
                "direction": metadata.direction.value if metadata else None,
                "queue": metadata.queue_name if metadata else None,
            },
        )

        db.add(session)
        db.commit()

        # Update integration stats
        integration.record_call()
        db.commit()

        logger.info(f"Created session for call: {event.external_call_id}")

        return {
            "session_id": session.session_id,
            "action": "created",
        }

    def _handle_call_answered(
        self,
        event: WebhookEvent,
        integration: IntegrationConfig,
        company_id: int,
        db,
    ) -> Dict[str, Any]:
        """Handle call.answered event - update session"""
        from app.models.call_session import CallSession

        session = db.query(CallSession).filter(
            CallSession.company_id == company_id,
            CallSession.call_id == event.external_call_id,
        ).first()

        if not session:
            logger.warning(f"No session found for answered call: {event.external_call_id}")
            return {"action": "session_not_found"}

        # Update agent info if provided
        if event.call_metadata:
            if event.call_metadata.agent_id:
                session.agent_id = event.call_metadata.agent_id
            if event.call_metadata.agent_name:
                session.agent_name = event.call_metadata.agent_name

        db.commit()

        return {"session_id": session.session_id, "action": "updated"}

    def _handle_call_ended(
        self,
        event: WebhookEvent,
        integration: IntegrationConfig,
        company_id: int,
        db,
    ) -> Dict[str, Any]:
        """Handle call.ended event - close session"""
        from app.models.call_session import CallSession, CallStatus

        session = db.query(CallSession).filter(
            CallSession.company_id == company_id,
            CallSession.call_id == event.external_call_id,
        ).first()

        if not session:
            logger.warning(f"No session found for ended call: {event.external_call_id}")
            return {"action": "session_not_found"}

        session.status = CallStatus.COMPLETED
        session.end_time = event.timestamp

        if event.call_metadata and event.call_metadata.duration_seconds:
            session.duration_seconds = event.call_metadata.duration_seconds
        elif session.start_time:
            duration = (event.timestamp - session.start_time).total_seconds()
            session.duration_seconds = int(duration)

        db.commit()

        logger.info(f"Closed session for call: {event.external_call_id}")

        return {
            "session_id": session.session_id,
            "action": "closed",
            "duration_seconds": session.duration_seconds,
        }

    def _handle_transcription(
        self,
        event: WebhookEvent,
        integration: IntegrationConfig,
        company_id: int,
        db,
    ) -> Dict[str, Any]:
        """Handle transcription events - store and forward to AI"""
        from app.models.call_session import CallSession, TranscriptionSegment

        session = db.query(CallSession).filter(
            CallSession.company_id == company_id,
            CallSession.call_id == event.external_call_id,
        ).first()

        if not session:
            logger.warning(f"No session for transcription: {event.external_call_id}")
            return {"action": "session_not_found"}

        if not event.transcription:
            return {"action": "no_transcription_data"}

        # Store transcription segment
        segment = TranscriptionSegment(
            session_id=session.id,
            speaker=event.transcription.speaker.value,
            text=event.transcription.text,
            confidence=event.transcription.confidence,
            start_time=event.transcription.start_time,
            end_time=event.transcription.end_time,
            timestamp=event.timestamp,
        )

        db.add(segment)
        db.commit()

        result = {
            "session_id": session.session_id,
            "action": "transcription_stored",
            "is_final": event.transcription.is_final,
            "speaker": event.transcription.speaker.value,
        }

        # For final transcriptions, trigger AI analysis
        if event.transcription.is_final and event.transcription.speaker.value == "customer":
            try:
                self._trigger_ai_analysis(session, event.transcription, db)
                result["ai_triggered"] = True
            except Exception as e:
                logger.error(f"Error triggering AI analysis: {e}")
                result["ai_error"] = str(e)

        return result

    def _handle_recording(
        self,
        event: WebhookEvent,
        integration: IntegrationConfig,
        company_id: int,
        db,
    ) -> Dict[str, Any]:
        """Handle recording.available event - store recording URL"""
        from app.models.call_session import CallSession

        session = db.query(CallSession).filter(
            CallSession.company_id == company_id,
            CallSession.call_id == event.external_call_id,
        ).first()

        if not session:
            return {"action": "session_not_found"}

        # Store recording URL in ACD metadata
        if not session.acd_metadata:
            session.acd_metadata = {}

        session.acd_metadata['recording_url'] = event.recording_url
        db.commit()

        return {
            "session_id": session.session_id,
            "action": "recording_stored",
        }

    def _trigger_ai_analysis(
        self,
        session,
        transcription,
        db,
    ):
        """
        Trigger AI analysis for a transcription.

        This connects to the existing AI pipeline (Agent Orchestrator).
        The transcription service is async, so we need to handle that.
        """
        import asyncio

        # Import here to avoid circular imports
        try:
            from app.services.realtime_transcription_service import get_transcription_service

            service = get_transcription_service()
            if service:
                # The service method is async, need to run it
                async def _run_analysis():
                    return await service.process_transcription_segment(
                        session_id=session.session_id,
                        speaker=transcription.speaker.value,
                        text=transcription.text,
                        start_time=transcription.start_time or 0,
                        end_time=transcription.end_time or 0,
                        confidence=transcription.confidence,
                        language=transcription.language,
                        company_id=session.company_id,
                    )

                # Try to get existing event loop or create new one
                try:
                    loop = asyncio.get_running_loop()
                    # If there's a running loop, schedule the task
                    asyncio.ensure_future(_run_analysis())
                except RuntimeError:
                    # No running loop, create a new one
                    asyncio.run(_run_analysis())

                logger.debug(f"AI analysis triggered for session: {session.session_id}")
            else:
                logger.warning("Transcription service not initialized, skipping AI analysis")

        except Exception as e:
            logger.error(f"Failed to trigger AI analysis: {e}")
            raise


# Singleton instance
_webhook_processor: Optional[WebhookProcessor] = None


def get_webhook_processor() -> WebhookProcessor:
    """Get or create WebhookProcessor singleton"""
    global _webhook_processor
    if _webhook_processor is None:
        _webhook_processor = WebhookProcessor()
    return _webhook_processor
