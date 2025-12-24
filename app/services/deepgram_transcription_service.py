"""
Deepgram Transcription Service
Provides real-time transcription using Deepgram's Nova-3 model
Supports both REST API (batch) and WebSocket (streaming) modes
"""
import logging
import io
import os
import httpx
import asyncio
from typing import Optional, Dict, Any, Callable, AsyncIterator

logger = logging.getLogger(__name__)

# Deepgram API configuration
DEEPGRAM_API_KEY = os.getenv('DEEPGRAM_API_KEY', '')
DEEPGRAM_API_URL = 'https://api.deepgram.com/v1/listen'


class DeepgramTranscriptionService:
    """
    Transcription service using Deepgram's Nova-3 model

    Nova-3 features:
    - Highest accuracy for real-time transcription
    - Multi-language support
    - Low latency
    - Smart formatting
    """

    def __init__(self, api_key: str = None):
        """
        Initialize Deepgram service

        Args:
            api_key: Deepgram API key (falls back to env var)
        """
        self.api_key = api_key or DEEPGRAM_API_KEY
        if not self.api_key:
            logger.warning("Deepgram API key not configured. Set DEEPGRAM_API_KEY environment variable.")
        else:
            logger.info("DeepgramTranscriptionService initialized with Nova-3 model")

    async def transcribe(
        self,
        audio_buffer: io.BytesIO,
        language: str = 'fr',
        sample_rate: int = 16000,
        encoding: str = 'linear16',
        channels: int = 1
    ) -> Optional[Dict[str, Any]]:
        """
        Transcribe audio using Deepgram Nova-3

        Args:
            audio_buffer: Audio data as BytesIO (WAV format)
            language: Language code (e.g., 'fr', 'en', 'es')
            sample_rate: Audio sample rate in Hz
            encoding: Audio encoding (linear16 for PCM)
            channels: Number of audio channels

        Returns:
            Dictionary with transcription result:
            {
                'text': str,
                'confidence': float,
                'language': str,
                'words': list (optional),
                'duration': float
            }
        """
        if not self.api_key:
            logger.error("Deepgram API key not configured")
            return None

        try:
            # Read audio data
            audio_buffer.seek(0)
            audio_data = audio_buffer.read()

            # Log diagnostic info
            logger.info(f"🎤 Deepgram: Sending {len(audio_data)} bytes ({len(audio_data)/1024:.1f}KB) to Nova-3")

            # Build query parameters for Nova-3
            params = {
                'model': 'nova-3',           # Latest Nova model
                'language': language,
                'smart_format': 'true',      # Smart formatting
                'punctuate': 'true',         # Add punctuation
                'diarize': 'false',          # We handle diarization separately
                'utterances': 'false',
                'detect_language': 'false',  # We specify language
            }

            # For raw PCM, specify encoding
            if not self._is_wav(audio_data):
                params['encoding'] = encoding
                params['sample_rate'] = str(sample_rate)
                params['channels'] = str(channels)

            # Build URL with query params
            url = DEEPGRAM_API_URL + '?' + '&'.join(f"{k}={v}" for k, v in params.items())

            headers = {
                'Authorization': f'Token {self.api_key}',
                'Content-Type': 'audio/wav' if self._is_wav(audio_data) else f'audio/raw'
            }

            # Make async HTTP request
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    headers=headers,
                    content=audio_data
                )

                if response.status_code != 200:
                    logger.error(f"Deepgram API error: {response.status_code} - {response.text}")
                    return None

                result = response.json()

            # Parse response
            return self._parse_response(result, language)

        except httpx.TimeoutException:
            logger.error("Deepgram API timeout")
            return None
        except Exception as e:
            logger.error(f"Deepgram transcription error: {e}", exc_info=True)
            return None

    def _is_wav(self, audio_data: bytes) -> bool:
        """Check if audio data is WAV format"""
        return audio_data[:4] == b'RIFF' and audio_data[8:12] == b'WAVE'

    def _parse_response(self, response: Dict, language: str) -> Optional[Dict[str, Any]]:
        """
        Parse Deepgram API response

        Args:
            response: Raw API response
            language: Requested language

        Returns:
            Standardized transcription result
        """
        try:
            # Navigate to results
            results = response.get('results', {})
            channels = results.get('channels', [])

            if not channels:
                logger.warning("Deepgram: No channels in response")
                return None

            alternatives = channels[0].get('alternatives', [])

            if not alternatives:
                logger.warning("Deepgram: No alternatives in response")
                return None

            best = alternatives[0]
            text = best.get('transcript', '').strip()
            confidence = best.get('confidence', 0.0)
            words = best.get('words', [])

            # Get metadata
            metadata = response.get('metadata', {})
            duration = metadata.get('duration', 0.0)

            if not text:
                logger.info("Deepgram: Empty transcription (silence or unclear audio)")
                return None

            logger.info(f"🎯 Deepgram Nova-3: '{text[:80]}...' (confidence: {confidence:.2f})")

            return {
                'text': text,
                'confidence': confidence,
                'language': language,
                'words': words,
                'duration': duration,
                'model': 'deepgram-nova-3'
            }

        except Exception as e:
            logger.error(f"Error parsing Deepgram response: {e}")
            return None

    async def transcribe_streaming(
        self,
        session_id: str,
        language: str = 'fr',
        sample_rate: int = 16000,
        encoding: str = 'linear16',
        channels: int = 1,
        on_transcript: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        """
        Start real-time streaming transcription using WebSocket

        This creates a persistent WebSocket connection that can receive
        audio chunks continuously and return interim + final results.

        Args:
            session_id: Session identifier for logging
            language: Language code (e.g., 'fr', 'en', 'es')
            sample_rate: Audio sample rate in Hz
            encoding: Audio encoding (linear16 for PCM)
            channels: Number of audio channels
            on_transcript: Callback function for transcription results

        Returns:
            DeepgramStreamingConnection instance for sending audio

        Example:
            connection = await service.transcribe_streaming(
                session_id='session-123',
                language='fr',
                on_transcript=lambda result: print(result['text'])
            )

            # Send audio chunks
            await connection.send_audio(audio_chunk)

            # When done
            await connection.close()
        """
        if not self.api_key:
            logger.error("Deepgram API key not configured")
            return None

        # Use the new async connection that properly uses async with
        from .deepgram_streaming_async import DeepgramAsyncConnection

        connection = DeepgramAsyncConnection(
            api_key=self.api_key,
            session_id=session_id,
            language=language,
            sample_rate=sample_rate,
            encoding=encoding,
            channels=channels,
            on_transcript=on_transcript
        )

        # Connect (runs in background thread with proper async/await)
        success = connection.connect()
        if not success:
            logger.error(f"[{session_id}] Failed to establish Deepgram connection")
            return None

        return connection


class DeepgramStreamingConnection:
    """
    WebSocket connection for streaming audio to Deepgram Nova-3

    Manages the lifecycle of a WebSocket connection and handles
    interim and final transcription results.

    Uses Deepgram SDK v5.x API with context manager pattern.
    """

    def __init__(
        self,
        api_key: str,
        session_id: str,
        language: str = 'fr',
        sample_rate: int = 16000,
        encoding: str = 'linear16',
        channels: int = 1,
        on_transcript: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        self.api_key = api_key
        self.session_id = session_id
        self.language = language
        self.sample_rate = sample_rate
        self.encoding = encoding
        self.channels = channels
        self.on_transcript = on_transcript

        self.socket = None
        self.context_manager = None
        self.is_connected = False
        self.deepgram_client = None
        self._receiver_thread = None
        self._keepalive_thread = None
        self._stop_receiving = False

    async def connect(self):
        """Establish WebSocket connection to Deepgram"""
        import threading

        try:
            # Import Deepgram SDK
            logger.info(f"[{self.session_id}] Importing Deepgram SDK v5.x...")
            try:
                from deepgram import DeepgramClient
                logger.info(f"[{self.session_id}] Deepgram SDK imported successfully")
            except ImportError as e:
                logger.error(
                    f"Deepgram SDK not installed. Run: pip install deepgram-sdk. Error: {e}"
                )
                return False

            # Create Deepgram client with custom config
            logger.info(f"[{self.session_id}] Creating Deepgram client...")
            from deepgram import DeepgramClientOptions

            # Configure client with longer keepalive timeout
            config = DeepgramClientOptions(
                options={
                    "keepalive": "true",
                    "termination_exception_connect": "true",
                    "termination_exception_send": "true"
                }
            )
            self.deepgram_client = DeepgramClient(api_key=self.api_key, config=config)

            # Create WebSocket connection using v1.connect()
            logger.info(f"[{self.session_id}] Creating WebSocket connection...")
            self.context_manager = self.deepgram_client.listen.v1.connect(
                model='nova-3',
                language=self.language,
                encoding=self.encoding,
                sample_rate=str(self.sample_rate),
                channels=str(self.channels),
                interim_results='true',
                punctuate='true',
                smart_format='true',
                utterance_end_ms='1000',
                # Increase keepalive timeout to prevent early disconnection
                keepalive='true'
            )

            # Enter context manager to get socket
            self.socket = self.context_manager.__enter__()

            if not self.socket:
                logger.error(f"[{self.session_id}] Failed to create Deepgram connection")
                return False

            logger.info(
                f"[{self.session_id}] ✅ Deepgram WebSocket connection established "
                f"(Nova-3, {self.language}, {self.sample_rate}Hz)"
            )

            # Start receiver thread to process incoming transcriptions
            self._stop_receiving = False
            self._receiver_thread = threading.Thread(
                target=self._receive_loop,
                daemon=True,
                name=f"deepgram-receiver-{self.session_id}"
            )
            self._receiver_thread.start()

            # Start keepalive thread to prevent connection timeout
            self._keepalive_thread = threading.Thread(
                target=self._keepalive_loop,
                daemon=True,
                name=f"deepgram-keepalive-{self.session_id}"
            )
            self._keepalive_thread.start()

            self.is_connected = True
            return True

        except Exception as e:
            logger.error(f"[{self.session_id}] Deepgram connection error: {e}", exc_info=True)
            return False

    def _keepalive_loop(self):
        """Background thread to send periodic keepalive messages"""
        import time
        from deepgram.extensions.types.sockets.listen_v1_control_message import ListenV1ControlMessage

        logger.info(f"[{self.session_id}] 💓 Keepalive thread started (interval: 3s)")
        keepalive_count = 0

        while not self._stop_receiving and self.is_connected:
            try:
                # Send keepalive every 3 seconds (Deepgram requires frequent keepalives)
                time.sleep(3)

                if self.socket and self.is_connected and not self._stop_receiving:
                    keepalive_msg = ListenV1ControlMessage(type='KeepAlive')
                    self.socket.send_control(keepalive_msg)
                    keepalive_count += 1
                    logger.info(f"[{self.session_id}] 💓 Keepalive #{keepalive_count} sent successfully")

            except Exception as e:
                if not self._stop_receiving:
                    logger.error(f"[{self.session_id}] ❌ Keepalive error: {e}")
                break

        logger.info(f"[{self.session_id}] 💓 Keepalive thread ended (sent {keepalive_count} keepalives)")

    def _receive_loop(self):
        """Background thread to receive transcription results"""
        logger.info(f"[{self.session_id}] 🎧 Receiver thread started")
        result_count = 0

        try:
            for result in self.socket.recv():
                if self._stop_receiving:
                    break

                result_count += 1
                logger.info(f"[{self.session_id}] 📥 Received result #{result_count}: {type(result).__name__}")
                self._process_result(result)

        except Exception as e:
            if not self._stop_receiving:
                logger.info(f"[{self.session_id}] ⚠️ Receiver stopped with error: {e}")

        logger.info(f"[{self.session_id}] 🎧 Receiver thread ended (processed {result_count} results)")

    def _process_result(self, result):
        """Process a transcription result from Deepgram"""
        try:
            # Log result attributes for debugging
            result_type_name = type(result).__name__
            attrs = [a for a in dir(result) if not a.startswith('_')][:15]
            logger.info(f"[{self.session_id}] 📋 Result attrs: {attrs}")

            # The result is a dict-like object
            # Check for transcript data
            if hasattr(result, 'channel'):
                channel = result.channel
                logger.info(f"[{self.session_id}] 📥 Has channel: {channel is not None}")

                if channel and hasattr(channel, 'alternatives') and channel.alternatives:
                    alternative = channel.alternatives[0]
                    transcript = alternative.transcript if hasattr(alternative, 'transcript') else ''
                    logger.info(f"[{self.session_id}] 📥 Transcript: '{transcript[:50] if transcript else '(empty)'}...'")

                    if transcript:
                        is_final = result.is_final if hasattr(result, 'is_final') else False
                        confidence = alternative.confidence if hasattr(alternative, 'confidence') else 0.0
                        duration = result.duration if hasattr(result, 'duration') else 0.0

                        transcription_result = {
                            'text': transcript,
                            'confidence': confidence,
                            'language': self.language,
                            'is_final': is_final,
                            'duration': duration,
                            'model': 'deepgram-nova-3-streaming'
                        }

                        result_type = "FINAL" if is_final else "interim"
                        logger.info(
                            f"[{self.session_id}] 🎯 Deepgram {result_type}: "
                            f"'{transcript[:50]}...' (conf: {confidence:.2f})"
                        )

                        if self.on_transcript:
                            logger.info(f"[{self.session_id}] 📤 Calling on_transcript callback...")
                            self.on_transcript(transcription_result)
                            logger.info(f"[{self.session_id}] 📤 Callback completed")
                        else:
                            logger.warning(f"[{self.session_id}] ⚠️ No on_transcript callback set!")
                    else:
                        logger.info(f"[{self.session_id}] 📥 Empty transcript (silence), skipping")
                else:
                    logger.info(f"[{self.session_id}] 📥 No alternatives in channel (or channel is None)")
            else:
                logger.info(f"[{self.session_id}] 📥 Result type '{result_type_name}' has no channel - might be metadata")

        except Exception as e:
            logger.error(f"[{self.session_id}] Error processing transcript: {e}", exc_info=True)

    async def send_audio(self, audio_chunk: bytes):
        """
        Send audio chunk to Deepgram

        Args:
            audio_chunk: Raw PCM audio bytes
        """
        if not self.is_connected or not self.socket:
            logger.warning(f"[{self.session_id}] Cannot send audio - not connected")
            return False

        try:
            self.socket.send_media(audio_chunk)
            return True
        except Exception as e:
            logger.error(f"[{self.session_id}] Error sending audio: {e}")
            return False

    async def close(self):
        """Close WebSocket connection"""
        self._stop_receiving = True

        if self.context_manager:
            try:
                self.context_manager.__exit__(None, None, None)
                logger.info(f"[{self.session_id}] Deepgram connection closed")
            except Exception as e:
                logger.debug(f"[{self.session_id}] Error closing connection: {e}")

        self.is_connected = False
        self.socket = None
        self.context_manager = None


# Singleton instance
_deepgram_service: Optional[DeepgramTranscriptionService] = None


def get_deepgram_service() -> DeepgramTranscriptionService:
    """Get or create Deepgram service instance"""
    global _deepgram_service

    if _deepgram_service is None:
        _deepgram_service = DeepgramTranscriptionService()

    return _deepgram_service
