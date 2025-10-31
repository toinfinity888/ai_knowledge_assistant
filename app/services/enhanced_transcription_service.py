"""
Enhanced Transcription Service with Speaker Diarization
Integrates Twilio audio streaming with Whisper transcription and speaker identification
"""
import asyncio
import logging
import wave
import io
from typing import Dict, Optional, List, Any
from datetime import datetime
import tempfile
import os

from openai import OpenAI

from app.services.speaker_diarization_service import get_diarization_service
from app.services.realtime_transcription_service import get_transcription_service

logger = logging.getLogger(__name__)


class EnhancedTranscriptionService:
    """
    Enhanced transcription with speaker awareness
    Processes audio from Twilio, transcribes with Whisper, identifies speakers
    """

    def __init__(self):
        self.openai_client = OpenAI()
        self.diarization_service = get_diarization_service()
        self.transcription_service = get_transcription_service()

        # Audio buffer management
        self.audio_buffers: Dict[str, Dict] = {}

        # Transcription settings
        self.sample_rate = 16000
        self.channels = 1
        self.sample_width = 2  # 16-bit

        # Buffering settings
        self.buffer_duration = 3.0  # seconds - buffer before transcribing
        self.max_buffer_duration = 10.0  # seconds - force transcription

        logger.info("EnhancedTranscriptionService initialized")

    async def process_audio_stream(
        self,
        session_id: str,
        audio_chunk: bytes,
        timestamp: float
    ) -> Optional[Dict[str, Any]]:
        """
        Process incoming audio chunk from Twilio stream

        Args:
            session_id: Session identifier
            audio_chunk: PCM audio data (16kHz, 16-bit)
            timestamp: Timestamp of audio chunk

        Returns:
            Transcription result if segment complete, None otherwise
        """
        # Initialize buffer if needed
        if session_id not in self.audio_buffers:
            self.audio_buffers[session_id] = {
                'chunks': [],
                'start_time': timestamp,
                'last_chunk_time': timestamp,
                'total_duration': 0.0
            }

        buffer = self.audio_buffers[session_id]

        # Add chunk to buffer
        buffer['chunks'].append(audio_chunk)
        buffer['last_chunk_time']: timestamp

        # Calculate total duration
        total_samples = sum(len(chunk) // self.sample_width for chunk in buffer['chunks'])
        buffer['total_duration'] = total_samples / self.sample_rate

        # Check if we should transcribe
        should_transcribe = (
            buffer['total_duration'] >= self.buffer_duration or
            buffer['total_duration'] >= self.max_buffer_duration
        )

        if should_transcribe:
            result = await self._transcribe_buffer(session_id, timestamp)
            # Clear buffer after transcription
            self.audio_buffers[session_id] = {
                'chunks': [],
                'start_time': timestamp,
                'last_chunk_time': timestamp,
                'total_duration': 0.0
            }
            return result

        return None

    async def _transcribe_buffer(
        self,
        session_id: str,
        current_timestamp: float
    ) -> Optional[Dict[str, Any]]:
        """
        Transcribe buffered audio

        Args:
            session_id: Session identifier
            current_timestamp: Current timestamp

        Returns:
            Transcription result with speaker identification
        """
        if session_id not in self.audio_buffers:
            return None

        buffer = self.audio_buffers[session_id]

        if not buffer['chunks']:
            return None

        try:
            # Combine audio chunks
            combined_audio = b''.join(buffer['chunks'])

            # Detect speaker and voice activity
            speaker_info = self.diarization_service.identify_speaker(
                session_id=session_id,
                audio_data=combined_audio,
                timestamp=buffer['start_time']
            )

            # Skip if no speech detected
            if not speaker_info['is_speech']:
                logger.debug(f"No speech detected in buffer for session {session_id}")
                return None

            # Check if we should process this speaker
            should_process = self.diarization_service.should_process_segment(
                session_id=session_id,
                speaker_role=speaker_info['speaker_role'],
                segment_duration=buffer['total_duration']
            )

            if not should_process:
                logger.debug(
                    f"Skipping segment from {speaker_info['speaker_role']} "
                    f"(duration: {buffer['total_duration']:.2f}s)"
                )
                return None

            # Create WAV file for Whisper
            wav_buffer = self._create_wav_buffer(combined_audio)

            # Transcribe with Whisper
            transcription_result = await self._transcribe_with_whisper(
                wav_buffer,
                language='fr'  # French by default for technicians
            )

            if not transcription_result or not transcription_result.get('text'):
                logger.warning(f"Empty transcription for session {session_id}")
                return None

            # Combine transcription with speaker info
            result = {
                'session_id': session_id,
                'text': transcription_result['text'],
                'speaker_id': speaker_info['speaker_id'],
                'speaker_name': speaker_info['speaker_name'],
                'speaker_role': speaker_info['speaker_role'],
                'confidence': transcription_result.get('confidence', 0.0),
                'speaker_confidence': speaker_info['confidence'],
                'start_time': buffer['start_time'],
                'end_time': current_timestamp,
                'duration': buffer['total_duration'],
                'language': transcription_result.get('language', 'fr'),
                'timestamp': datetime.utcnow().isoformat()
            }

            logger.info(
                f"Transcribed {buffer['total_duration']:.2f}s from {speaker_info['speaker_name']} "
                f"({speaker_info['speaker_role']}): {result['text'][:50]}..."
            )

            # Send to agent processing pipeline
            await self._process_with_agents(result)

            return result

        except Exception as e:
            logger.error(f"Transcription error for session {session_id}: {e}")
            return None

    def _create_wav_buffer(self, pcm_data: bytes) -> io.BytesIO:
        """
        Create WAV file buffer from PCM data

        Args:
            pcm_data: PCM audio data (16kHz, 16-bit)

        Returns:
            BytesIO buffer containing WAV file
        """
        wav_buffer = io.BytesIO()

        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(self.sample_width)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(pcm_data)

        wav_buffer.seek(0)
        wav_buffer.name = "audio.wav"  # Whisper API needs a name
        return wav_buffer

    async def _transcribe_with_whisper(
        self,
        audio_buffer: io.BytesIO,
        language: str = 'fr'
    ) -> Optional[Dict[str, Any]]:
        """
        Transcribe audio using OpenAI Whisper API

        Args:
            audio_buffer: Audio file buffer
            language: Language code (default: French)

        Returns:
            Transcription result
        """
        try:
            # Call Whisper API
            response = self.openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_buffer,
                language=language,
                response_format="verbose_json"
            )

            return {
                'text': response.text,
                'language': response.language,
                'duration': response.duration,
                'confidence': getattr(response, 'confidence', 0.9)  # Not always available
            }

        except Exception as e:
            logger.error(f"Whisper API error: {e}")
            return None

    async def _process_with_agents(self, transcription_result: Dict[str, Any]):
        """
        Process transcription through AI agent pipeline

        Prioritizes technician speech for problem understanding

        Args:
            transcription_result: Transcription with speaker info
        """
        try:
            session_id = transcription_result['session_id']
            text = transcription_result['text']
            speaker_role = transcription_result['speaker_role']
            language = transcription_result.get('language', 'fr')

            # Only process technician speech for now
            # Support agent responses are generated by the system, not transcribed
            if speaker_role != 'technician':
                logger.debug(f"Skipping agent processing for {speaker_role}")
                return

            # Send to agent orchestrator through transcription service
            result = await self.transcription_service.process_transcription_segment(
                session_id=session_id,
                speaker=speaker_role,
                text=text,
                start_time=transcription_result['start_time'],
                end_time=transcription_result['end_time'],
                confidence=transcription_result['confidence'],
                language=language
            )

            logger.info(f"Agent processing complete for session {session_id}")

        except Exception as e:
            logger.error(f"Agent processing error: {e}")

    def initialize_session(
        self,
        session_id: str,
        technician_id: str,
        technician_name: str,
        technician_phone: Optional[str] = None
    ):
        """
        Initialize a session with speaker profiles

        Args:
            session_id: Session identifier
            technician_id: Technician identifier
            technician_name: Technician name
            technician_phone: Technician phone number
        """
        # Register technician speaker
        self.diarization_service.register_speaker(
            session_id=session_id,
            speaker_id=technician_id,
            speaker_name=technician_name,
            speaker_role='technician'
        )

        # Register support agent (AI system)
        self.diarization_service.register_speaker(
            session_id=session_id,
            speaker_id='ai_assistant',
            speaker_name='Assistant IA',
            speaker_role='support_agent'
        )

        logger.info(
            f"Session initialized: {session_id} with technician {technician_name}"
        )

    def end_session(self, session_id: str) -> Dict[str, Any]:
        """
        End a session and get statistics

        Args:
            session_id: Session identifier

        Returns:
            Session statistics
        """
        # Get speaker stats
        stats = self.diarization_service.get_speaker_stats(session_id)

        # Clear buffers
        if session_id in self.audio_buffers:
            del self.audio_buffers[session_id]

        # Clear speaker data
        self.diarization_service.clear_session(session_id)

        logger.info(f"Session ended: {session_id}")

        return stats


# Singleton instance
_enhanced_transcription_service: Optional[EnhancedTranscriptionService] = None


def get_enhanced_transcription_service() -> EnhancedTranscriptionService:
    """Get or create enhanced transcription service instance"""
    global _enhanced_transcription_service

    if _enhanced_transcription_service is None:
        _enhanced_transcription_service = EnhancedTranscriptionService()

    return _enhanced_transcription_service
