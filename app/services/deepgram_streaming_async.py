"""
Async-based Deepgram streaming connection that properly uses the SDK v5 API.

This implementation uses async/await properly with context managers to avoid keepalive timeout issues.
"""
import asyncio
import logging
import threading
from typing import Callable, Dict, Any, Optional
from queue import Queue, Empty

logger = logging.getLogger(__name__)


class DeepgramAsyncConnection:
    """
    Async WebSocket connection for streaming audio to Deepgram Nova-3.

    Runs in a dedicated event loop thread and properly uses async with to avoid
    keepalive timeout issues that occur when manually calling __enter__/__exit__.
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

        self.is_connected = False
        self._loop = None
        self._loop_thread = None
        self._audio_queue = Queue()
        self._stop_event = threading.Event()

    async def _run_connection(self):
        """Main async function that runs the connection using proper async with"""
        try:
            from deepgram import DeepgramClient

            logger.info(f"[{self.session_id}] Creating async Deepgram connection...")

            # Create client (SDK v5.x handles keepalive automatically)
            client = DeepgramClient(api_key=self.api_key)

            # Use async with to properly manage the connection
            # SDK v5.x handles keepalive automatically when using context manager
            # IMPORTANT: Use boolean True/False instead of strings 'true'/'false'
            async with client.listen.v1.connect(
                model='nova-3',
                language=self.language,
                encoding=self.encoding,
                sample_rate=str(self.sample_rate),
                channels=str(self.channels),
                interim_results=True,      # FIXED: boolean instead of string
                punctuate=True,            # FIXED: boolean instead of string
                smart_format=True,         # FIXED: boolean instead of string
                utterance_end_ms='1000'
            ) as connection:

                logger.info(
                    f"[{self.session_id}] ✅ Deepgram connection established "
                    f"(Nova-3, {self.language}, {self.sample_rate}Hz, interim_results=True)"
                )
                self.is_connected = True

                # Start concurrent tasks for receiving, keepalive, and audio sending
                await asyncio.gather(
                    self._receive_loop(connection),
                    self._keepalive_loop(connection),
                    self._audio_sender_loop(connection),
                    return_exceptions=True
                )

        except Exception as e:
            logger.error(f"[{self.session_id}] Connection error: {e}", exc_info=True)
        finally:
            self.is_connected = False
            logger.info(f"[{self.session_id}] Connection closed")

    def connect(self):
        """Start the async connection in a background thread"""
        def run_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._run_connection())

        self._loop_thread = threading.Thread(target=run_loop, daemon=True)
        self._loop_thread.start()

        # Wait a bit for connection to establish
        import time
        for _ in range(20):  # Wait up to 2 seconds
            if self.is_connected:
                return True
            time.sleep(0.1)

        return self.is_connected

    async def _receive_loop(self, connection):
        """Async loop to receive transcription results"""
        logger.info(f"[{self.session_id}] 🎧 Async receiver started")
        result_count = 0
        interim_count = 0
        final_count = 0

        try:
            # Properly iterate over received messages
            for result in connection.recv():
                if self._stop_event.is_set():
                    break

                result_count += 1
                
                # Process result asynchronously
                was_interim = await self._process_result(result)
                
                if was_interim:
                    interim_count += 1
                else:
                    final_count += 1
                    
                # Log every 10th result or when we have a final result
                if result_count % 10 == 0 or not was_interim:
                    logger.info(
                        f"[{self.session_id}] 📥 Results so far: {result_count} total "
                        f"(interim: {interim_count}, final: {final_count})"
                    )

        except Exception as e:
            if not self._stop_event.is_set():
                logger.error(f"[{self.session_id}] Receiver error: {e}", exc_info=True)

        logger.info(
            f"[{self.session_id}] 🎧 Receiver ended "
            f"(total: {result_count}, interim: {interim_count}, final: {final_count})"
        )

    async def _keepalive_loop(self, connection):
        """Async loop to send keepalive messages every 3 seconds"""
        from deepgram.extensions.types.sockets.listen_v1_control_message import ListenV1ControlMessage

        logger.info(f"[{self.session_id}] 💓 Keepalive started (interval: 3s)")
        keepalive_count = 0

        try:
            while not self._stop_event.is_set():
                await asyncio.sleep(3)

                if self.is_connected and not self._stop_event.is_set():
                    keepalive_msg = ListenV1ControlMessage(type='KeepAlive')
                    connection.send_control(keepalive_msg)
                    keepalive_count += 1
                    if keepalive_count % 10 == 0:  # Log every 10th keepalive
                        logger.info(f"[{self.session_id}] 💓 Keepalive #{keepalive_count} sent")

        except Exception as e:
            if not self._stop_event.is_set():
                logger.error(f"[{self.session_id}] Keepalive error: {e}", exc_info=True)

        logger.info(f"[{self.session_id}] 💓 Keepalive ended (sent {keepalive_count} keepalives)")

    async def _audio_sender_loop(self, connection):
        """Async loop to send audio chunks from queue"""
        logger.info(f"[{self.session_id}] 🎤 Audio sender started")
        audio_count = 0

        try:
            while not self._stop_event.is_set():
                # Check queue for audio chunks
                try:
                    audio_chunk = self._audio_queue.get(timeout=0.1)

                    if audio_chunk is None:  # Poison pill to stop
                        break

                    connection.send_media(audio_chunk)
                    audio_count += 1

                except Empty:
                    # No audio in queue, continue
                    await asyncio.sleep(0.01)
                    continue

        except Exception as e:
            if not self._stop_event.is_set():
                logger.error(f"[{self.session_id}] Audio sender error: {e}", exc_info=True)

        logger.info(f"[{self.session_id}] 🎤 Audio sender ended (sent {audio_count} chunks)")

    async def _process_result(self, result) -> bool:
        """
        Process a transcription result from Deepgram
        
        Returns:
            True if this was an interim result, False if final
        """
        try:
            # Check if result has transcript data
            if hasattr(result, 'channel') and result.channel:
                channel = result.channel

                if hasattr(channel, 'alternatives') and channel.alternatives:
                    alternative = channel.alternatives[0]
                    transcript = alternative.transcript if hasattr(alternative, 'transcript') else ''

                    # Get is_final status
                    is_final = result.is_final if hasattr(result, 'is_final') else False

                    # IMPORTANT: Send both interim and final results
                    # Let the callback decide whether to display interim results
                    if transcript:
                        confidence = alternative.confidence if hasattr(alternative, 'confidence') else 0.0

                        transcription_result = {
                            'text': transcript,
                            'confidence': confidence,
                            'language': self.language,
                            'is_final': is_final,
                            'model': 'deepgram-nova-3-streaming'
                        }

                        result_type = "FINAL" if is_final else "interim"
                        logger.info(
                            f"[{self.session_id}] 🎯 Deepgram {result_type}: "
                            f"'{transcript[:50]}{'...' if len(transcript) > 50 else ''}' "
                            f"(conf: {confidence:.2f})"
                        )

                        if self.on_transcript:
                            # Call callback in executor to avoid blocking
                            loop = asyncio.get_event_loop()
                            await loop.run_in_executor(None, self.on_transcript, transcription_result)
                        else:
                            logger.warning(f"[{self.session_id}] ⚠️ No on_transcript callback set!")
                        
                        return not is_final  # Return True if interim
                    else:
                        # Empty transcript - this is normal for interim results while processing
                        if not is_final:
                            logger.debug(f"[{self.session_id}] 📥 Empty interim result (processing...)")
                        return not is_final

            return False

        except Exception as e:
            logger.error(f"[{self.session_id}] Error processing result: {e}", exc_info=True)
            return False

    def send_audio(self, audio_chunk: bytes):
        """Send audio chunk (called from sync context) - puts in queue for async sender"""
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
        logger.info(f"[{self.session_id}] Closing async connection...")
        self._stop_event.set()
        self._audio_queue.put(None)  # Poison pill
        self.is_connected = False