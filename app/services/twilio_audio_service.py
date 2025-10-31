"""
Twilio Audio Service for Bidirectional Audio Streaming
Handles real-time audio streaming between technician and AI system
"""
import asyncio
import base64
import json
import logging
from typing import Dict, Optional, Any
from datetime import datetime
import audioop

from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Start, Stream

logger = logging.getLogger(__name__)


class TwilioAudioService:
    """
    Manages bidirectional audio streaming with Twilio
    - Receives audio from technician
    - Sends AI-generated audio responses back
    - Handles audio format conversion (mulaw <-> linear PCM)
    """

    def __init__(self, account_sid: str, auth_token: str, phone_number: str):
        self.client = Client(account_sid, auth_token)
        self.phone_number = phone_number
        self.active_streams: Dict[str, Dict[str, Any]] = {}

        # Audio settings for Twilio (8kHz, 8-bit mulaw)
        self.TWILIO_SAMPLE_RATE = 8000
        self.TWILIO_CHANNELS = 1

        # Audio settings for Whisper (16kHz, 16-bit PCM)
        self.WHISPER_SAMPLE_RATE = 16000

        logger.info(f"TwilioAudioService initialized with phone {phone_number}")

    def initiate_call(self, to_number: str, session_id: str, websocket_url: str) -> Dict[str, Any]:
        """
        Initiate an outbound call to the technician

        Args:
            to_number: Phone number to call (technician)
            session_id: Unique session identifier
            websocket_url: Public URL where Twilio will send audio streams

        Returns:
            Call information including call_sid
        """
        try:
            # Create TwiML response for the call
            twiml = self._generate_call_twiml(session_id, websocket_url)

            # Initiate the call
            call = self.client.calls.create(
                to=to_number,
                from_=self.phone_number,
                twiml=str(twiml),
                status_callback=f"{websocket_url}/twilio/status",
                status_callback_event=['initiated', 'ringing', 'answered', 'completed']
            )

            logger.info(f"Call initiated: {call.sid} to {to_number} for session {session_id}")

            return {
                'call_sid': call.sid,
                'session_id': session_id,
                'to_number': to_number,
                'status': 'initiated',
                'created_at': datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to initiate call: {e}")
            raise

    def _generate_call_twiml(self, session_id: str, websocket_url: str) -> VoiceResponse:
        """
        Generate TwiML for the call with bidirectional streaming

        Args:
            session_id: Session identifier
            websocket_url: WebSocket URL for audio streaming

        Returns:
            TwiML VoiceResponse object
        """
        response = VoiceResponse()

        # Greet the technician
        response.say(
            "Bonjour, vous êtes connecté à l'assistant de support technique. Veuillez décrire le problème.",
            language='fr-FR',
            voice='alice'
        )

        # Start bidirectional media stream
        start = Start()
        stream = Stream(
            url=f"{websocket_url}/twilio/media-stream",
            name=session_id
        )
        stream.parameter(name='session_id', value=session_id)
        start.stream(stream)
        response.append(start)

        # Keep the call alive
        response.pause(length=3600)  # 1 hour max

        return response

    async def handle_media_stream(self, websocket, session_id: str):
        """
        Handle incoming WebSocket media stream from Twilio

        Args:
            websocket: WebSocket connection
            session_id: Session identifier
        """
        stream_sid = None
        audio_buffer = []

        try:
            # Register the stream
            self.active_streams[session_id] = {
                'websocket': websocket,
                'stream_sid': None,
                'started_at': datetime.utcnow(),
                'audio_buffer': []
            }

            logger.info(f"Media stream handler started for session {session_id}")

            async for message in websocket:
                try:
                    data = json.loads(message)
                    event_type = data.get('event')

                    if event_type == 'start':
                        stream_sid = data['start']['streamSid']
                        self.active_streams[session_id]['stream_sid'] = stream_sid
                        logger.info(f"Stream started: {stream_sid} for session {session_id}")

                    elif event_type == 'media':
                        # Incoming audio from technician
                        payload = data['media']['payload']

                        # Decode base64 mulaw audio
                        mulaw_audio = base64.b64decode(payload)

                        # Convert mulaw to linear PCM
                        pcm_audio = audioop.ulaw2lin(mulaw_audio, 2)

                        # Resample from 8kHz to 16kHz for Whisper
                        pcm_16k = audioop.ratecv(
                            pcm_audio,
                            2,  # 16-bit
                            self.TWILIO_CHANNELS,
                            self.TWILIO_SAMPLE_RATE,
                            self.WHISPER_SAMPLE_RATE,
                            None
                        )[0]

                        # Buffer the audio
                        audio_buffer.append(pcm_16k)

                        # Process audio chunk (will be sent to transcription service)
                        await self._process_audio_chunk(session_id, pcm_16k)

                    elif event_type == 'stop':
                        logger.info(f"Stream stopped: {stream_sid}")
                        break

                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON from Twilio stream: {message}")
                except Exception as e:
                    logger.error(f"Error processing media message: {e}")

        except Exception as e:
            logger.error(f"Media stream error for session {session_id}: {e}")
        finally:
            # Clean up
            if session_id in self.active_streams:
                del self.active_streams[session_id]
            logger.info(f"Media stream closed for session {session_id}")

    async def _process_audio_chunk(self, session_id: str, audio_data: bytes):
        """
        Process incoming audio chunk
        This will be called for each audio chunk received from Twilio

        Args:
            session_id: Session identifier
            audio_data: PCM audio data (16kHz, 16-bit)
        """
        # Store in session buffer for batching
        if session_id in self.active_streams:
            self.active_streams[session_id]['audio_buffer'].append(audio_data)

            # Check if we have enough audio to transcribe (e.g., 1 second)
            buffer = self.active_streams[session_id]['audio_buffer']
            total_samples = sum(len(chunk) // 2 for chunk in buffer)  # 16-bit = 2 bytes per sample
            duration_seconds = total_samples / self.WHISPER_SAMPLE_RATE

            if duration_seconds >= 1.0:  # Process every 1 second
                # Combine buffer
                combined_audio = b''.join(buffer)

                # Clear buffer
                self.active_streams[session_id]['audio_buffer'] = []

                # Send to enhanced transcription service
                try:
                    from app.services.enhanced_transcription_service import get_enhanced_transcription_service

                    transcription_service = get_enhanced_transcription_service()

                    # Calculate timestamp
                    timestamp = (datetime.utcnow() - self.active_streams[session_id]['started_at']).total_seconds()

                    # Process audio stream
                    result = await transcription_service.process_audio_stream(
                        session_id=session_id,
                        audio_chunk=combined_audio,
                        timestamp=timestamp
                    )

                    if result:
                        logger.info(f"Transcription: {result.get('text', '')[:50]}...")

                except Exception as e:
                    logger.error(f"Error in audio processing: {e}")

                return combined_audio

        return None

    async def send_audio_to_stream(self, session_id: str, audio_data: bytes):
        """
        Send audio back to Twilio stream (AI speaking)

        Args:
            session_id: Session identifier
            audio_data: PCM audio data to send (16kHz, 16-bit)
        """
        if session_id not in self.active_streams:
            logger.warning(f"No active stream for session {session_id}")
            return

        stream_info = self.active_streams[session_id]
        websocket = stream_info['websocket']
        stream_sid = stream_info['stream_sid']

        if not stream_sid:
            logger.warning(f"Stream not yet started for session {session_id}")
            return

        try:
            # Resample from 16kHz to 8kHz for Twilio
            audio_8k = audioop.ratecv(
                audio_data,
                2,  # 16-bit
                self.TWILIO_CHANNELS,
                self.WHISPER_SAMPLE_RATE,
                self.TWILIO_SAMPLE_RATE,
                None
            )[0]

            # Convert linear PCM to mulaw
            mulaw_audio = audioop.lin2ulaw(audio_8k, 2)

            # Encode to base64
            payload = base64.b64encode(mulaw_audio).decode('utf-8')

            # Send to Twilio
            message = {
                'event': 'media',
                'streamSid': stream_sid,
                'media': {
                    'payload': payload
                }
            }

            await websocket.send(json.dumps(message))
            logger.debug(f"Sent audio to stream {stream_sid}")

        except Exception as e:
            logger.error(f"Failed to send audio to stream: {e}")

    def end_call(self, call_sid: str) -> Dict[str, Any]:
        """
        End an active call

        Args:
            call_sid: Twilio call SID

        Returns:
            Call status information
        """
        try:
            call = self.client.calls(call_sid).update(status='completed')

            logger.info(f"Call ended: {call_sid}")

            return {
                'call_sid': call_sid,
                'status': call.status,
                'duration': call.duration
            }

        except Exception as e:
            logger.error(f"Failed to end call {call_sid}: {e}")
            raise

    def get_call_status(self, call_sid: str) -> Dict[str, Any]:
        """
        Get current status of a call

        Args:
            call_sid: Twilio call SID

        Returns:
            Call status information
        """
        try:
            call = self.client.calls(call_sid).fetch()

            from_number = getattr(call, 'from_formatted', None) or getattr(call, 'from_', None) or call.from_
            to_number = getattr(call, 'to_formatted', None) or getattr(call, 'to_', None) or call.to

            return {
                'call_sid': call.sid,
                'status': call.status,
                'direction': call.direction,
                'duration': int(call.duration) if call.duration else 0,
                'from_number': from_number,
                'to_number': to_number
            }

        except Exception as e:
            logger.error(f"Failed to fetch call status for {call_sid}: {e}")
            raise


# Singleton instance
_twilio_service: Optional[TwilioAudioService] = None


def get_twilio_service() -> TwilioAudioService:
    """Get or create Twilio audio service instance"""
    global _twilio_service

    if _twilio_service is None:
        from app.config.twilio_config import get_twilio_settings

        settings = get_twilio_settings()
        _twilio_service = TwilioAudioService(
            account_sid=settings.account_sid,
            auth_token=settings.auth_token,
            phone_number=settings.phone_number
        )

    return _twilio_service
