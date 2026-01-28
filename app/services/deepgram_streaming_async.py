"""
Threaded Deepgram streaming connection for SDK v5.3.0
Uses the official event-based pattern with EventType.MESSAGE callbacks
"""
import logging
import threading
import time
from typing import Callable, Dict, Any, Optional
from queue import Queue, Empty

from deepgram.core.events import EventType
from deepgram.extensions.types.sockets import ListenV1SocketClientResponse

logger = logging.getLogger(__name__)


class DeepgramThreadedConnection:
    """
    Real-time WebSocket connection for Deepgram Nova-3 streaming transcription
    Compatible with deepgram-sdk v5.3.0
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

    def connect(self) -> bool:
        """
        Establish WebSocket connection to Deepgram
        Returns True if connection successful
        """
        try:
            print(f"🔧 [STEP 1] Importing DeepgramClient...")
            from deepgram import DeepgramClient

            print(f"🔧 [STEP 2] Creating Deepgram client...")
            logger.info(f"[{self.session_id}] Creating Deepgram client...")
            client = DeepgramClient(api_key=self.api_key)

            # SDK v5.3.0 uses connect() with string parameters
            print(f"🔧 [STEP 3] Calling client.listen.v1.connect()...")
            logger.info(f"[{self.session_id}] Creating WebSocket connection...")

            # Build keywords list with weights
            keywords_param = ','.join([f"{item}:2" for item in self.equipment_list]) if self.equipment_list else None

            print(f"🔧 [STEP 4] Creating context manager...")
            print(f"   📊 Parameters: model=nova-3, language={self.language}, sample_rate=16000")
            print(f"   📊 Features: interim_results=true, utterance_end_ms=1000")
            print(f"   📊 ATOMIC MESSAGE HANDLING enabled for continuous interim results")
            self._context_manager = client.listen.v1.connect(
                model='nova-3',
                language=self.language,
                encoding='linear16',
                sample_rate='16000',
                channels='1',
                interim_results='true',
                punctuate='true',
                smart_format='true',
                utterance_end_ms='1000',
                vad_events='false',
                keywords=keywords_param
            )

            # Enter synchronous context manager
            print(f"🔧 [STEP 5] Entering context manager (this may take a few seconds)...")
            try:
                self._socket = self._context_manager.__enter__()
                print(f"🔧 [STEP 6] ✅ Context manager entered successfully!")
            except Exception as enter_error:
                print(f"❌ ERROR entering context manager: {enter_error}")
                logger.error(f"[{self.session_id}] Error entering context manager: {enter_error}", exc_info=True)
                return False

            if not self._socket:
                print(f"❌ Socket is None after __enter__()")
                logger.error(f"[{self.session_id}] Failed to create Deepgram connection")
                return False

            self.is_connected = True
            print(f"✅ CONNECTION ESTABLISHED!")
            logger.info(
                f"[{self.session_id}] ✅ Deepgram connection established "
                f"(Nova-3, {self.language}, 16kHz, interim_results=true)"
            )

            # Start background threads
            self._stop_event.clear()

            print(f"🧵 [STEP 7] Creating receiver thread...")
            self._receiver_thread = threading.Thread(
                target=self._receive_loop,
                daemon=True,
                name=f"deepgram-receiver-{self.session_id}"
            )
            print(f"🧵 [STEP 8] Starting receiver thread...")
            self._receiver_thread.start()
            print(f"🧵 [STEP 9] Receiver thread alive: {self._receiver_thread.is_alive()}")

            print(f"🧵 [STEP 10] Creating sender thread...")
            self._sender_thread = threading.Thread(
                target=self._sender_loop,
                daemon=True,
                name=f"deepgram-sender-{self.session_id}"
            )
            print(f"🧵 [STEP 11] Starting sender thread...")
            self._sender_thread.start()
            print(f"🧵 [STEP 12] Sender thread alive: {self._sender_thread.is_alive()}")

            print(f"🧵 [STEP 13] Creating keepalive thread...")
            self._keepalive_thread = threading.Thread(
                target=self._keepalive_loop,
                daemon=True,
                name=f"deepgram-keepalive-{self.session_id}"
            )
            print(f"🧵 [STEP 14] Starting keepalive thread...")
            self._keepalive_thread.start()
            print(f"🧵 [STEP 15] Keepalive thread alive: {self._keepalive_thread.is_alive()}")

            print(f"✅ [STEP 16] ALL THREADS STARTED!")
            return True

        except Exception as e:
            logger.error(f"[{self.session_id}] Deepgram connection failed: {e}", exc_info=True)
            self.is_connected = False
            return False

    def _receive_loop(self):
        """Background thread to receive transcription results"""
        print(f"🎧 RECEIVER THREAD EXECUTING! Session: {self.session_id}")
        logger.info(f"[{self.session_id}] 🎧 Receiver thread started")
        result_count = 0
        interim_count = 0
        final_count = 0

        try:
            print(f"🎧 Entering recv() loop, waiting for results from Deepgram...")

            # SDK v5.3.0 returns individual field tuples - collect them into complete messages
            current_message = {}

            for field_tuple in self._socket.recv():
                if self._stop_event.is_set():
                    break

                try:
                    # Each result is a (key, value) tuple representing one field
                    if not isinstance(field_tuple, tuple) or len(field_tuple) != 2:
                        continue

                    key, value = field_tuple
                    print(f"🔧 Received tuple: ({key}, {str(value)[:100]}...)" if len(str(value)) > 100 else f"🔧 Received tuple: ({key}, {value})")

                    # CRITICAL: Reset buffer on 'type' key to prevent "First Chunk Lock"
                    # This ensures no stale data from previous messages contaminates new ones
                    if key == 'type':
                        current_message = {key: value}  # Reset and start fresh
                        print(f"🎧 NEW MESSAGE STARTED: type={value}")
                    else:
                        current_message[key] = value

                    # CRITICAL: Process Results immediately when 'channel' arrives
                    # This eliminates the "lag-behind" effect - no waiting for next message
                    if key == 'channel':
                        print(f"🎧 PROCESSING MESSAGE (channel received): {current_message}")
                        result_count += 1

                        try:
                            was_interim = self._process_result(current_message)

                            if was_interim:
                                interim_count += 1
                            else:
                                final_count += 1
                        except Exception as process_error:
                            logger.error(
                                f"[{self.session_id}] Pydantic validation or processing failed: {process_error}",
                                exc_info=True
                            )
                            print(f"❌ Processing error (Pydantic validation?): {process_error}")

                except Exception as e:
                    logger.error(f"[{self.session_id}] Error processing field: {e}", exc_info=True)
                    print(f"❌ Error: {e}")
                    continue

            # Log summary
            if result_count > 0:
                logger.debug(
                        f"[{self.session_id}] 📥 Results: {result_count} total "
                        f"(interim: {interim_count}, final: {final_count})"
                    )

        except Exception as e:
            if not self._stop_event.is_set():
                logger.error(f"[{self.session_id}] Receiver error: {e}", exc_info=True)

        logger.info(
            f"[{self.session_id}] 🎧 Receiver ended "
            f"(total: {result_count}, interim: {interim_count}, final: {final_count})"
        )

    def _sender_loop(self):
        """Background thread to send audio chunks from queue"""
        print(f"🎤 SENDER THREAD EXECUTING! Session: {self.session_id}")
        logger.info(f"[{self.session_id}] 🎤 Sender thread started")
        audio_count = 0

        try:
            while not self._stop_event.is_set():
                try:
                    audio_chunk = self._audio_queue.get(timeout=0.1)

                    if audio_chunk is None:  # Poison pill
                        break

                    if self._socket and self.is_connected:
                        # Quick audio level check
                        import struct
                        import numpy as np
                        try:
                            samples = struct.unpack(f'{len(audio_chunk)//2}h', audio_chunk)
                            if len(samples) > 0:
                                rms = float(np.sqrt(np.mean(np.square(samples))))
                                max_amp = float(max(abs(s) for s in samples))
                                print(f"📡 Sending {len(audio_chunk)} bytes (RMS: {rms:.1f}, Max: {max_amp:.0f})")
                            else:
                                print(f"📡 Sending {len(audio_chunk)} bytes")
                        except:
                            print(f"📡 Sending {len(audio_chunk)} bytes")

                        self._socket.send_media(audio_chunk)
                        audio_count += 1

                except Empty:
                    continue
                except Exception as e:
                    if not self._stop_event.is_set():
                        logger.error(f"[{self.session_id}] Sender error: {e}")

        except Exception as e:
            if not self._stop_event.is_set():
                logger.error(f"[{self.session_id}] Sender loop error: {e}", exc_info=True)

        logger.info(f"[{self.session_id}] 🎤 Sender ended (sent {audio_count} chunks)")

    def _keepalive_loop(self):
        """Background thread to send periodic keepalive messages"""
        print(f"💓 KEEPALIVE THREAD EXECUTING! Session: {self.session_id}")
        logger.info(f"[{self.session_id}] 💓 Keepalive thread started (interval: 3s)")
        keepalive_count = 0

        try:
            from deepgram.extensions.types.sockets.listen_v1_control_message import ListenV1ControlMessage
        except ImportError:
            logger.warning(f"[{self.session_id}] Could not import ListenV1ControlMessage, keepalive disabled")
            return

        while not self._stop_event.is_set():
            try:
                time.sleep(3)

                if self._socket and self.is_connected and not self._stop_event.is_set():
                    keepalive_msg = ListenV1ControlMessage(type='KeepAlive')
                    self._socket.send_control(keepalive_msg)
                    keepalive_count += 1

                    if keepalive_count % 10 == 0:
                        logger.debug(f"[{self.session_id}] 💓 Keepalive #{keepalive_count}")

            except Exception as e:
                if not self._stop_event.is_set():
                    logger.error(f"[{self.session_id}] Keepalive error: {e}")
                break

        logger.info(f"[{self.session_id}] 💓 Keepalive ended (sent {keepalive_count})")

    def _process_result(self, result: dict) -> bool:
        """
        Process a transcription result from Deepgram (SDK v5.3.0 dict format)
        Returns True if this was an interim result, False if final
        """
        try:
            # Check result type
            result_type = result.get('type', '')

            # Log ALL events with full details for debugging
            print(f"🎧 Event received: {result_type}")
            print(f"   Full message: {result}")
            logger.info(f"[{self.session_id}] Event: {result_type}, Data: {result}")

            # Skip non-transcription events (SpeechStarted, etc.)
            if result_type != 'Results':
                print(f"🎧 Skipping non-Results event: {result_type}")
                return False

            # Get channel data (SDK v5.3.0 returns Pydantic objects, not dicts)
            channel = result.get('channel')
            if not channel:
                return False

            # Access Pydantic object attributes (not dict methods)
            alternatives = channel.alternatives if hasattr(channel, 'alternatives') else []
            if not alternatives:
                print(f"⚠️ No alternatives in channel")
                return False

            # Get first alternative (also a Pydantic object)
            alternative = alternatives[0]
            transcript = alternative.transcript.strip() if hasattr(alternative, 'transcript') else ''

            # Get flags
            is_final = result.get('is_final', False)
            speech_final = result.get('speech_final', False)

            if transcript:
                confidence = alternative.confidence if hasattr(alternative, 'confidence') else 0.0

                transcription_result = {
                    'text': transcript,
                    'confidence': confidence,
                    'language': self.language,
                    'is_final': is_final,
                    'speech_final': speech_final,  # Utterance boundary detection
                    'model': 'deepgram-nova-3-streaming'
                }

                result_label = "FINAL" if is_final else "INTERIM"
                speech_status = " [SPEECH_FINAL]" if speech_final else ""
                print(
                    f"🎯 {result_label}{speech_status}: "
                    f"'{transcript[:80]}{'...' if len(transcript) > 80 else ''}' "
                    f"(conf: {confidence:.2f})"
                )
                logger.info(
                    f"[{self.session_id}] 🎯 {result_label}{speech_status}: "
                    f"'{transcript[:80]}{'...' if len(transcript) > 80 else ''}' "
                    f"(conf: {confidence:.2f})"
                )

                if self.on_transcript:
                    self.on_transcript(transcription_result)

                return not is_final

            return not is_final

        except Exception as e:
            logger.error(f"[{self.session_id}] Error processing result: {e}", exc_info=True)
            print(f"❌ Error processing result: {e}")
            return False

    def send_audio(self, audio_chunk: bytes) -> bool:
        """
        Queue audio chunk for sending to Deepgram
        Called from sync context - puts audio in queue for sender thread
        """
        if not self.is_connected:
            print(f"❌ send_audio called but not connected!")
            return False

        try:
            print(f"📤 Queueing audio chunk: {len(audio_chunk)} bytes")
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

        self._socket = None
        self._context_manager = None
        logger.info(f"[{self.session_id}] Connection closed")
