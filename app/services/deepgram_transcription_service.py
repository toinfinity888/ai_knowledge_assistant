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
            DeepgramAsyncConnection instance for sending audio

        Example:
            connection = await service.transcribe_streaming(
                session_id='session-123',
                language='fr',
                on_transcript=lambda result: print(result['text'])
            )

            # Send audio chunks
            connection.send_audio(audio_chunk)

            # When done
            connection.close()
        """
        if not self.api_key:
            logger.error("Deepgram API key not configured")
            return None

        # Use the async connection class (which uses sync SDK internally)
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

        # Connect (synchronous call - runs in current thread)
        success = connection.connect()
        if not success:
            logger.error(f"[{session_id}] Failed to establish Deepgram connection")
            return None

        return connection


# Singleton instance
_deepgram_service: Optional[DeepgramTranscriptionService] = None


def get_deepgram_service() -> DeepgramTranscriptionService:
    """Get or create Deepgram service instance"""
    global _deepgram_service

    if _deepgram_service is None:
        _deepgram_service = DeepgramTranscriptionService()

    return _deepgram_service