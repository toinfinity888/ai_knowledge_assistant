"""
Deepgram-Twilio Bridge Service
Handles bidirectional streaming transcription for Twilio calls using Deepgram Nova-2
"""
import logging
import json
from typing import Dict, Optional, Callable
from datetime import datetime

from app.services.deepgram_streaming_v5 import DeepgramStreamingConnection
from app.services.deepgram_transcription_service import get_deepgram_service

logger = logging.getLogger(__name__)


class DeepgramTwilioBridge:
    """
    Manages Deepgram streaming connections for bidirectional transcription
    - Customer audio (from Twilio Media Streams)
    - Technician audio (from browser getUserMedia)
    """

    def __init__(self):
        """Initialize the bridge service"""
        self.active_connections: Dict[str, Dict[str, any]] = {}
        self.deepgram_service = get_deepgram_service()
        logger.info("DeepgramTwilioBridge initialized")

    def create_customer_stream(
        self,
        session_id: str,
        language: str = 'en',  # TESTING: Changed from 'fr' to 'en' to diagnose empty transcripts
        on_transcript: Optional[Callable] = None
    ) -> Optional[DeepgramStreamingConnection]:
        """
        Create Deepgram streaming connection for customer audio (from Twilio)

        Args:
            session_id: Call session ID
            language: Language code (fr, en, etc.)
            on_transcript: Callback for transcription results

        Returns:
            DeepgramStreamingConnection instance or None if failed
        """
        try:
            logger.info(f"[{session_id}] Creating Deepgram stream for CUSTOMER (Twilio audio)")

            # Create wrapper callback that adds speaker labels
            def customer_transcript_callback(result):
                # Add speaker metadata
                result['speaker_role'] = 'customer'
                result['speaker_label'] = 'Client'
                result['source'] = 'twilio_media_stream'

                logger.info(
                    f"[{session_id}] 📞 Customer: '{result['text'][:50]}...' "
                    f"(is_final={result['is_final']}, conf={result['confidence']:.2f})"
                )

                if on_transcript:
                    on_transcript(result)

            # Create Deepgram connection
            connection = DeepgramStreamingConnection(
                api_key=self.deepgram_service.api_key,
                session_id=f"{session_id}_customer",
                language=language,
                equipment_list=[],
                on_transcript=customer_transcript_callback
            )

            # Connect
            if connection.connect():
                # Store connection
                if session_id not in self.active_connections:
                    self.active_connections[session_id] = {}

                self.active_connections[session_id]['customer'] = {
                    'connection': connection,
                    'created_at': datetime.utcnow(),
                    'language': language,
                    'role': 'customer'
                }

                logger.info(f"[{session_id}] ✅ Customer Deepgram stream established")
                return connection
            else:
                logger.error(f"[{session_id}] ❌ Failed to establish customer Deepgram stream")
                return None

        except Exception as e:
            logger.error(f"[{session_id}] Error creating customer stream: {e}", exc_info=True)
            return None

    def create_technician_stream(
        self,
        session_id: str,
        language: str = 'en',  # TESTING: Changed from 'fr' to 'en' to diagnose empty transcripts
        on_transcript: Optional[Callable] = None
    ) -> Optional[DeepgramStreamingConnection]:
        """
        Create Deepgram streaming connection for technician audio (from browser)

        Args:
            session_id: Call session ID
            language: Language code (fr, en, etc.)
            on_transcript: Callback for transcription results

        Returns:
            DeepgramStreamingConnection instance or None if failed
        """
        try:
            logger.info(f"[{session_id}] Creating Deepgram stream for TECHNICIAN (browser audio)")

            # Create wrapper callback that adds speaker labels
            def technician_transcript_callback(result):
                # Add speaker metadata
                result['speaker_role'] = 'technician'
                result['speaker_label'] = 'Technicien'
                result['source'] = 'browser_media_stream'

                logger.info(
                    f"[{session_id}] 👨‍💼 Technician: '{result['text'][:50]}...' "
                    f"(is_final={result['is_final']}, conf={result['confidence']:.2f})"
                )

                if on_transcript:
                    on_transcript(result)

            # Create Deepgram connection
            connection = DeepgramStreamingConnection(
                api_key=self.deepgram_service.api_key,
                session_id=f"{session_id}_technician",
                language=language,
                equipment_list=[],
                on_transcript=technician_transcript_callback
            )

            # Connect
            if connection.connect():
                # Store connection
                if session_id not in self.active_connections:
                    self.active_connections[session_id] = {}

                self.active_connections[session_id]['technician'] = {
                    'connection': connection,
                    'created_at': datetime.utcnow(),
                    'language': language,
                    'role': 'technician'
                }

                logger.info(f"[{session_id}] ✅ Technician Deepgram stream established")
                return connection
            else:
                logger.error(f"[{session_id}] ❌ Failed to establish technician Deepgram stream")
                return None

        except Exception as e:
            logger.error(f"[{session_id}] Error creating technician stream: {e}", exc_info=True)
            return None

    def send_customer_audio(self, session_id: str, audio_chunk: bytes) -> bool:
        """
        Send customer audio chunk to Deepgram

        Args:
            session_id: Call session ID
            audio_chunk: PCM Int16 audio data

        Returns:
            True if sent successfully
        """
        try:
            if session_id not in self.active_connections:
                return False

            customer_stream = self.active_connections[session_id].get('customer')
            if not customer_stream:
                return False

            connection = customer_stream['connection']
            return connection.send_audio(audio_chunk)

        except Exception as e:
            logger.error(f"[{session_id}] Error sending customer audio: {e}")
            return False

    def send_technician_audio(self, session_id: str, audio_chunk: bytes) -> bool:
        """
        Send technician audio chunk to Deepgram

        Args:
            session_id: Call session ID
            audio_chunk: PCM Int16 audio data

        Returns:
            True if sent successfully
        """
        try:
            if session_id not in self.active_connections:
                return False

            tech_stream = self.active_connections[session_id].get('technician')
            if not tech_stream:
                return False

            connection = tech_stream['connection']
            return connection.send_audio(audio_chunk)

        except Exception as e:
            logger.error(f"[{session_id}] Error sending technician audio: {e}")
            return False

    def close_session(self, session_id: str):
        """
        Close all Deepgram connections for a session

        Args:
            session_id: Call session ID
        """
        try:
            if session_id not in self.active_connections:
                logger.info(f"[{session_id}] No active Deepgram connections to close")
                return

            connections = self.active_connections[session_id]

            # Close customer stream
            if 'customer' in connections:
                try:
                    connections['customer']['connection'].close()
                    logger.info(f"[{session_id}] ✅ Closed customer Deepgram stream")
                except Exception as e:
                    logger.error(f"[{session_id}] Error closing customer stream: {e}")

            # Close technician stream
            if 'technician' in connections:
                try:
                    connections['technician']['connection'].close()
                    logger.info(f"[{session_id}] ✅ Closed technician Deepgram stream")
                except Exception as e:
                    logger.error(f"[{session_id}] Error closing technician stream: {e}")

            # Remove from active connections
            del self.active_connections[session_id]
            logger.info(f"[{session_id}] ✅ Deepgram session cleaned up")

        except Exception as e:
            logger.error(f"[{session_id}] Error closing session: {e}", exc_info=True)

    def get_session_stats(self, session_id: str) -> Dict:
        """
        Get statistics for a session's Deepgram connections

        Args:
            session_id: Call session ID

        Returns:
            Dictionary with connection stats
        """
        if session_id not in self.active_connections:
            return {'active': False}

        connections = self.active_connections[session_id]
        stats = {
            'active': True,
            'session_id': session_id,
            'streams': {}
        }

        for role in ['customer', 'technician']:
            if role in connections:
                stream = connections[role]
                stats['streams'][role] = {
                    'connected': stream['connection'].is_connected,
                    'language': stream['language'],
                    'created_at': stream['created_at'].isoformat()
                }

        return stats


# Singleton instance
_bridge_service: Optional[DeepgramTwilioBridge] = None


def get_deepgram_twilio_bridge() -> DeepgramTwilioBridge:
    """Get or create the Deepgram-Twilio bridge service"""
    global _bridge_service

    if _bridge_service is None:
        _bridge_service = DeepgramTwilioBridge()

    return _bridge_service
