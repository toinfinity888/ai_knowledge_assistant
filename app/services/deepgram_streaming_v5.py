"""
Deepgram Streaming Connection for SDK v5.3.0
Uses the OFFICIAL event-based pattern with EventType callbacks
Based on: https://github.com/deepgram/deepgram-python-sdk/blob/main/examples/streaming/async_microphone/main.py
"""
import logging
import threading
import time
from typing import Callable, Dict, Any, Optional
from queue import Queue, Empty

from deepgram import DeepgramClient
from deepgram.core.events import EventType
from deepgram.extensions.types.sockets import ListenV1SocketClientResponse

logger = logging.getLogger(__name__)


class DeepgramStreamingConnection:
    """
    Real-time WebSocket connection for Deepgram Nova-3 streaming transcription
    Compatible with deepgram-sdk v5.3.0 using official event-based pattern
    """

    def __init__(
        self,
        api_key: str,
        session_id: str,
        language: str = 'fr',
        equipment_list: list = None,
        on_transcript: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        self.api_key = api_key
        self.session_id = session_id
        self.language = language
        self.on_transcript = on_transcript
        self.equipment_list = equipment_list or []

        self.is_connected = False
        self._connection = None
        self._context_manager = None
        self._audio_queue = Queue()
        self._stop_event = threading.Event()

        # Threads
        self._listening_thread = None
        self._sender_thread = None

        # Stats
        self._result_count = 0
        self._interim_count = 0
        self._final_count = 0

    def connect(self) -> bool:
        """
        Establish WebSocket connection to Deepgram using official event-based pattern
        Returns True if connection successful
        """
        try:
            logger.info(f"[{self.session_id}] Creating Deepgram client...")
            client = DeepgramClient(api_key=self.api_key)

            # Build keywords list with weights
            keywords_param = ','.join([f"{item}:2" for item in self.equipment_list]) if self.equipment_list else None

            # Determine sample rate and encoding based on audio source
            # Twilio phone audio: 8kHz PCM (converted from mulaw)
            # Browser audio: 16kHz PCM
            # BOTH use linear16 encoding since we convert mulaw to PCM before sending
            is_phone = 'customer' in self.session_id
            if is_phone:
                sample_rate_str = '8000'
                encoding_str = 'linear16'  # Phone sends PCM (converted from mulaw) at 8kHz
            else:
                sample_rate_str = '16000'
                encoding_str = 'linear16'  # Browser sends PCM at 16kHz

            # Create connection context manager
            self._context_manager = client.listen.v1.connect(
                model='nova-2',
                language=self.language,
                encoding=encoding_str,
                sample_rate=sample_rate_str,
                channels='1',
                interim_results='true'
            )

            # Enter context manager
            try:
                self._connection = self._context_manager.__enter__()
            except Exception as enter_error:
                logger.error(f"[{self.session_id}] Error entering context manager: {enter_error}", exc_info=True)
                return False

            if not self._connection:
                logger.error(f"[{self.session_id}] Failed to create Deepgram connection")
                return False

            # Register event handlers (OFFICIAL PATTERN)
            self._connection.on(EventType.OPEN, self._on_open)
            self._connection.on(EventType.MESSAGE, self._on_message)
            self._connection.on(EventType.CLOSE, self._on_close)
            self._connection.on(EventType.ERROR, self._on_error)

            self.is_connected = True
            logger.info(
                f"[{self.session_id}] ✅ Deepgram connection established "
                f"(Nova-2, {self.language}, {sample_rate_str}Hz, interim_results=true, event-based)"
            )

            # Start background threads
            self._stop_event.clear()

            # Start listening thread (calls connection.start_listening())
            self._listening_thread = threading.Thread(
                target=self._listening_loop,
                daemon=True,
                name=f"deepgram-listening-{self.session_id}"
            )
            self._listening_thread.start()

            # Start sender thread
            self._sender_thread = threading.Thread(
                target=self._sender_loop,
                daemon=True,
                name=f"deepgram-sender-{self.session_id}"
            )
            self._sender_thread.start()

            return True

        except Exception as e:
            logger.error(f"[{self.session_id}] Deepgram connection failed: {e}", exc_info=True)
            self.is_connected = False
            return False

    def _listening_loop(self):
        """
        Background thread that calls connection.start_listening()
        This is required by the official SDK pattern
        """
        logger.info(f"[{self.session_id}] Listening thread started")

        try:
            self._connection.start_listening()
        except Exception as e:
            if not self._stop_event.is_set():
                logger.error(f"[{self.session_id}] Listening thread error: {e}", exc_info=True)

        logger.info(
            f"[{self.session_id}] Listening thread ended "
            f"(total: {self._result_count}, interim: {self._interim_count}, final: {self._final_count})"
        )

    def _on_open(self, _):
        """Event handler for connection open"""
        logger.info(f"[{self.session_id}] WebSocket connection opened")

    def _on_message(self, message: ListenV1SocketClientResponse):
        """
        Event handler for incoming messages (OFFICIAL PATTERN)
        Receives full Pydantic objects, not tuples
        """
        try:
            # Get message type
            msg_type = getattr(message, "type", "Unknown")

            # Skip non-Results messages
            if msg_type != "Results":
                return

            # Access Pydantic object attributes
            if not hasattr(message, 'channel'):
                return

            channel = message.channel

            if not hasattr(channel, 'alternatives') or not channel.alternatives:
                return

            # Get transcript
            alternative = channel.alternatives[0]
            transcript = alternative.transcript.strip() if hasattr(alternative, 'transcript') else ''

            if not transcript:
                return

            # Get flags
            is_final = message.is_final if hasattr(message, 'is_final') else False
            speech_final = message.speech_final if hasattr(message, 'speech_final') else False
            confidence = alternative.confidence if hasattr(alternative, 'confidence') else 0.0

            # Update stats
            self._result_count += 1
            if is_final:
                self._final_count += 1
            else:
                self._interim_count += 1

            result_label = "FINAL" if is_final else "INTERIM"
            speech_status = " [SPEECH_FINAL]" if speech_final else ""
            logger.info(
                f"[{self.session_id}] {result_label}{speech_status}: "
                f"'{transcript[:80]}{'...' if len(transcript) > 80 else ''}' "
                f"(conf: {confidence:.2f})"
            )

            # Call user callback
            if self.on_transcript:
                transcription_result = {
                    'text': transcript,
                    'confidence': confidence,
                    'language': self.language,
                    'is_final': is_final,
                    'speech_final': speech_final,
                    'model': 'deepgram-nova-3-streaming'
                }
                self.on_transcript(transcription_result)

        except Exception as e:
            logger.error(f"[{self.session_id}] Error processing message: {e}", exc_info=True)

    def _on_close(self, _):
        """Event handler for connection close"""
        logger.info(f"[{self.session_id}] WebSocket connection closed")
        self.is_connected = False

    def _on_error(self, error):
        """Event handler for errors"""
        logger.error(f"[{self.session_id}] Deepgram error: {error}")

    def _sender_loop(self):
        """Background thread to send audio chunks from queue"""
        logger.info(f"[{self.session_id}] Sender thread started")
        audio_count = 0

        try:
            while not self._stop_event.is_set():
                try:
                    audio_chunk = self._audio_queue.get(timeout=0.1)

                    if audio_chunk is None:  # Poison pill
                        break

                    if self._connection and self.is_connected:
                        self._connection.send_media(audio_chunk)
                        audio_count += 1

                except Empty:
                    continue
                except Exception as e:
                    if not self._stop_event.is_set():
                        logger.error(f"[{self.session_id}] Sender error: {e}")

        except Exception as e:
            if not self._stop_event.is_set():
                logger.error(f"[{self.session_id}] Sender loop error: {e}", exc_info=True)

        logger.info(f"[{self.session_id}] Sender ended (sent {audio_count} chunks)")

    def send_audio(self, audio_chunk: bytes) -> bool:
        """
        Queue audio chunk for sending to Deepgram
        Called from sync context - puts audio in queue for sender thread
        """
        if not self.is_connected:
            return False

        try:
            self._audio_queue.put(audio_chunk, timeout=0.1)
            return True
        except Exception as e:
            logger.error(f"[{self.session_id}] Error queueing audio: {e}")
            return False

    def close(self):
        """Close the connection properly"""
        logger.info(f"[{self.session_id}] Closing connection...")

        self._stop_event.set()
        self._audio_queue.put(None)  # Poison pill for sender thread
        self.is_connected = False

        # Close the context manager
        if self._context_manager:
            try:
                self._context_manager.__exit__(None, None, None)
                logger.info(f"[{self.session_id}] Context manager closed")
            except Exception as e:
                logger.debug(f"[{self.session_id}] Error closing context manager: {e}")

        self._connection = None
        self._context_manager = None
        logger.info(f"[{self.session_id}] Connection closed")
