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
import torch
import torchaudio

from app.services.speaker_diarization_service import get_diarization_service
from app.services.realtime_transcription_service import get_transcription_service
from app.services.deepgram_transcription_service import get_deepgram_service
from app.config.transcription_config import get_transcription_config

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
        self.deepgram_service = get_deepgram_service()

        # Get configuration instance (singleton)
        self.config = get_transcription_config()

        # Initialize Silero VAD model for speech detection
        try:
            model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                onnx=False
            )
            self.vad_model = model
            self.vad_utils = utils
            (self.get_speech_timestamps, _, _, _, _) = utils
            logger.info("✅ Silero VAD model loaded successfully")
        except Exception as e:
            logger.error(f"❌ Failed to load Silero VAD model: {e}")
            self.vad_model = None
            self.vad_utils = None
            self.get_speech_timestamps = None

        # Audio buffer management
        self.audio_buffers: Dict[str, Dict] = {}

        # Streaming connections for Deepgram WebSocket
        self.streaming_connections: Dict[str, Any] = {}

        # Transcription settings
        self.sample_rate = 16000  # Default sample rate for WAV files (Whisper native rate)
        self.channels = 1 # mono
        self.sample_width = 2  # 16-bit

        logger.info(f"EnhancedTranscriptionService initialized with config:")
        logger.info(f"  Backend: {self.config.transcription_backend}, Language: {self.config.transcription_language}")
        logger.info(f"  Deepgram streaming: {self.config.deepgram_use_streaming}")
        logger.info(f"  VAD bypass: {self.config.bypass_vad}, min_duration bypass: {self.config.bypass_min_duration}")
        logger.info(f"  Silence detection: min_rms_8k={self.config.min_rms_8k}, min_rms_16k={self.config.min_rms_16k}")
        logger.info(f"  Buffer durations: buffer={self.config.buffer_duration}s, max={self.config.max_buffer_duration}s")
        logger.info(f"  VAD parameters: threshold={self.config.vad_threshold}, min_speech={self.config.vad_min_speech_duration_ms}ms")

    async def process_audio_stream(
        self,
        session_id: str,
        audio_chunk: bytes,
        timestamp: float,
        speaker: str = 'technician',
        sample_rate: int = None
    ) -> Optional[Dict[str, Any]]:
        """
        Process incoming audio chunk - buffer and transcribe when ready.

        This is the ONLY place where audio buffering happens.
        Twilio audio service passes chunks directly here.

        Args:
            session_id: Session identifier
            audio_chunk: PCM audio data (8kHz or 16kHz, 16-bit)
            timestamp: Timestamp of audio chunk
            speaker: Speaker identifier ('technician' for customer, 'agent' for support agent)
            sample_rate: Audio sample rate (8000 for technician/Twilio, 16000 for agent/browser)

        Returns:
            Transcription result if segment complete, None otherwise
        """
        # ========================================
        # DEEPGRAM STREAMING MODE
        # ========================================
        # If Deepgram streaming is enabled, send audio directly to WebSocket
        # instead of buffering (much lower latency)
        if (self.config.transcription_backend == 'deepgram' and
            self.config.deepgram_use_streaming):

            buffer_key = f"{session_id}_{speaker}"

            # Check if streaming connection exists for this session
            if buffer_key in self.streaming_connections:
                connection = self.streaming_connections[buffer_key]

                # Send audio chunk directly to Deepgram WebSocket
                await connection.send_audio(audio_chunk)

                # Streaming results are handled via callback
                # No return value needed here - transcriptions come via on_transcript callback
                return None
            else:
                # No streaming connection - fall through to buffered mode
                logger.warning(
                    f"[{buffer_key}] Deepgram streaming enabled but no connection found. "
                    f"Call initialize_session() first or falling back to buffered mode."
                )

        # ========================================
        # BUFFERED MODE (Whisper or Deepgram REST)
        # ========================================
        # Use separate buffer keys for each speaker to avoid interference
        buffer_key = f"{session_id}_{speaker}"

        # Determine sample rate: use provided value, or default based on speaker
        # Technician audio from Twilio is 8kHz, Agent audio from browser is 16kHz
        effective_sample_rate = sample_rate if sample_rate else (8000 if speaker == 'technician' else 16000)

        # Initialize buffer if needed
        if buffer_key not in self.audio_buffers:
            self.audio_buffers[buffer_key] = {
                'chunks': [],
                'start_time': timestamp,
                'last_chunk_time': timestamp,
                'total_duration': 0.0,
                'waiting_for_speech': True,  # Skip initial silence/noise
                'initial_skip_start': timestamp,  # Track when session started for 0.5s hard skip
                'sample_rate': effective_sample_rate
            }
            logger.info(f"[{buffer_key}] 🆕 Created new audio buffer for {speaker} - will skip first 0.5s unconditionally")

        buffer = self.audio_buffers[buffer_key]

        # Add chunk to buffer
        buffer['chunks'].append(audio_chunk) # Store raw PCM data
        buffer['last_chunk_time'] = timestamp

        # Calculate total duration using the buffer's actual sample rate
        buffer_sample_rate = buffer.get('sample_rate', effective_sample_rate)
        total_samples = sum(len(chunk) // self.sample_width for chunk in buffer['chunks'])  # total samples across all chunks
        buffer['total_duration'] = total_samples / buffer_sample_rate                       # in seconds
        chunk_duration = len(audio_chunk) // self.sample_width / buffer_sample_rate         # duration of current chunk in seconds

        # Calculate total bytes in buffer
        total_bytes = sum(len(chunk) for chunk in buffer['chunks'])

        # Log progress every 25 chunks (reduced verbosity)
        if len(buffer['chunks']) % 25 == 0:
            logger.info(f"[{buffer_key}] 📦 Buffer progress: {len(buffer['chunks'])} chunks, {buffer['total_duration']:.2f}s, {total_bytes} bytes")

        # ========================================
        # BYPASS VAD: Simple byte-count triggering (like app_fixed.py)
        # ========================================
        if self.config.bypass_vad:
            # Determine minimum bytes based on sample rate
            min_bytes = self.config.min_bytes_8k if buffer_sample_rate == 8000 else self.config.min_bytes_16k

            if total_bytes >= min_bytes:
                logger.info(f"[{buffer_key}] ✂️ SIMPLE TRIGGER: {total_bytes} bytes >= {min_bytes} bytes (~3 seconds)")
                result = await self._transcribe_buffer(session_id, timestamp, speaker, pause_duration_ms=0.0)

                # Clear buffer after transcription
                self.audio_buffers[buffer_key] = {
                    'chunks': [],
                    'start_time': timestamp,
                    'last_chunk_time': timestamp,
                    'total_duration': 0.0,
                    'waiting_for_speech': False,
                    'initial_skip_start': buffer.get('initial_skip_start', timestamp),
                    'sample_rate': effective_sample_rate
                }
                logger.info(f"[{buffer_key}] 🔄 Buffer cleared after transcription")
                return result
            else:
                logger.debug(f"[{buffer_key}] ⏳ Buffering: {total_bytes}/{min_bytes} bytes")
                return None

        # ========================================
        # VAD-BASED SEGMENTATION (original logic)
        # ========================================
        # Use VAD to detect if speech has ended
        # Use buffer_key (session_id_speaker) to keep VAD state separate per speaker
        should_segment, reason, pause_duration_ms = self.diarization_service.check_speech_ended(
            session_id=buffer_key,  # Use speaker-specific session ID for independent VAD
            audio_data=audio_chunk,
            chunk_duration=chunk_duration,
            current_timestamp=timestamp
        )

        # Also force transcription if buffer gets too long (safety fallback)
        force_transcribe = buffer['total_duration'] >= self.config.max_buffer_duration

        if force_transcribe:
            logger.warning(f"[{buffer_key}] ⚠️ Max buffer duration reached ({buffer['total_duration']:.2f}s >= {self.config.max_buffer_duration}s) - FORCE transcribing (pause={pause_duration_ms:.0f}ms)")
            should_segment = True
            reason = "max_duration_exceeded"
            # Keep the pause_duration_ms from VAD - don't reset it!

        if should_segment:
            # Preserve initial_skip_start across buffer resets (only skip first 0.5s of session, not after each segment)
            prev_initial_skip = buffer.get('initial_skip_start', timestamp)

            # Check if segment was rejected due to low RMS
            if reason.startswith("rms_too_low"):
                logger.warning(f"[{buffer_key}] ⏭️ Segment rejected due to low RMS - discarding without transcription")
                # Clear buffer but don't call Whisper
                # Keep waiting_for_speech=True to continue skipping noise
                self.audio_buffers[buffer_key] = {
                    'chunks': [],
                    'start_time': timestamp,
                    'last_chunk_time': timestamp,
                    'total_duration': 0.0,
                    'waiting_for_speech': True,  # Continue waiting for real speech
                    'initial_skip_start': prev_initial_skip,  # Preserve original session start time
                    'sample_rate': effective_sample_rate  # Preserve sample rate
                }
                return None

            # Ensure we have minimum speech duration
            if buffer['total_duration'] >= self.diarization_service.min_speech_duration:
                logger.info(f"[{buffer_key}] ✂️ VAD-based segmentation triggered: reason={reason}, duration={buffer['total_duration']:.2f}s, pause={pause_duration_ms:.0f}ms, speaker={speaker}")
                result = await self._transcribe_buffer(session_id, timestamp, speaker, pause_duration_ms)
                # Clear buffer after transcription - wait for next speech
                self.audio_buffers[buffer_key] = {
                    'chunks': [],
                    'start_time': timestamp,
                    'last_chunk_time': timestamp,
                    'total_duration': 0.0,
                    'waiting_for_speech': True,  # Wait for next speech segment
                    'initial_skip_start': prev_initial_skip,  # Preserve original session start time
                    'sample_rate': effective_sample_rate  # Preserve sample rate
                }
                logger.info(f"[{buffer_key}] 🔄 Buffer cleared after transcription - waiting for next speech")
                return result
            else:
                logger.info(f"[{buffer_key}] ⏭️ Segment too short ({buffer['total_duration']:.2f}s < {self.diarization_service.min_speech_duration}s) - discarding")
                # Clear buffer but don't transcribe - continue waiting
                self.audio_buffers[buffer_key] = {
                    'chunks': [],
                    'start_time': timestamp,
                    'last_chunk_time': timestamp,
                    'total_duration': 0.0,
                    'waiting_for_speech': True,  # Continue waiting for real speech
                    'initial_skip_start': prev_initial_skip,  # Preserve original session start time
                    'sample_rate': effective_sample_rate  # Preserve sample rate
                }
        else:
            logger.info(f"[{buffer_key}] ⏳ Buffering: {buffer['total_duration']:.2f}s, VAD status: {reason}")

        return None

    def _validate_speech_with_silero_vad(
        self,
        pcm_data: bytes,
        sample_rate: int,
        session_id: str
    ) -> bool:
        """
        Use Silero VAD to validate if audio contains actual speech.

        Args:
            pcm_data: PCM audio data (16-bit)
            sample_rate: Sample rate of audio (8000 or 16000 Hz)
            session_id: Session identifier for logging

        Returns:
            True if speech is detected, False otherwise
        """
        if self.vad_model is None or self.get_speech_timestamps is None:
            logger.warning(f"[{session_id}] ⚠️ Silero VAD not available, skipping validation")
            return True  # If VAD not available, assume it's speech

        try:
            import struct
            import numpy as np

            # Convert PCM bytes to numpy array
            samples = struct.unpack(f'{len(pcm_data)//2}h', pcm_data)
            audio_np = np.array(samples, dtype=np.float32) / 32768.0  # Normalize to [-1, 1]

            # Convert to torch tensor
            audio_tensor = torch.from_numpy(audio_np)

            # Resample if needed (Silero VAD works best at 16kHz)
            if sample_rate != 16000:
                logger.info(f"[{session_id}] 🔄 Resampling audio from {sample_rate}Hz to 16000Hz for VAD")
                resampler = torchaudio.transforms.Resample(
                    orig_freq=sample_rate,
                    new_freq=16000
                )
                audio_tensor = resampler(audio_tensor)

            # Get speech timestamps from Silero VAD
            speech_timestamps = self.get_speech_timestamps(
                audio_tensor,
                self.vad_model,
                sampling_rate=16000,
                threshold=self.config.vad_threshold,  # Confidence threshold (0-1)
                min_speech_duration_ms=self.config.vad_min_speech_duration_ms,  # Minimum speech duration
                min_silence_duration_ms=self.config.vad_min_silence_duration_ms  # Minimum silence between speech
            )

            # Check if any speech was detected
            has_speech = len(speech_timestamps) > 0

            if has_speech:
                # Calculate total speech duration
                total_speech_ms = sum(
                    timestamp['end'] - timestamp['start']
                    for timestamp in speech_timestamps
                )
                total_duration_ms = len(audio_tensor) / 16000 * 1000
                speech_ratio = total_speech_ms / total_duration_ms if total_duration_ms > 0 else 0

                logger.info(
                    f"[{session_id}] ✅ Silero VAD: Speech detected - "
                    f"{len(speech_timestamps)} segments, "
                    f"{total_speech_ms:.0f}ms speech / {total_duration_ms:.0f}ms total "
                    f"({speech_ratio:.1%})"
                )
            else:
                logger.warning(
                    f"[{session_id}] 🔇 Silero VAD: NO SPEECH detected - "
                    f"skipping Whisper transcription"
                )

            return has_speech

        except Exception as e:
            logger.error(f"[{session_id}] ❌ Silero VAD error: {e}", exc_info=True)
            return True  # On error, assume it's speech to avoid blocking valid audio

    async def _transcribe_buffer(
        self,
        session_id: str,
        current_timestamp: float,
        speaker: str = 'technician',
        pause_duration_ms: float = 0.0
    ) -> Optional[Dict[str, Any]]:
        """
        Transcribe buffered audio

        Args:
            session_id: Session identifier
            current_timestamp: Current timestamp
            speaker: Speaker identifier ('technician' or 'agent')
            pause_duration_ms: Duration of pause before this segment in milliseconds

        Returns:
            Transcription result with speaker identification and pause duration
        """
        # Use same buffer key pattern as process_audio_stream
        buffer_key = f"{session_id}_{speaker}"

        if buffer_key not in self.audio_buffers:
            return None

        buffer = self.audio_buffers[buffer_key]

        if not buffer['chunks']:
            return None

        try:
            # Combine audio chunks
            combined_audio = b''.join(buffer['chunks'])
            speaker_label = 'TECHNICIAN' if speaker == 'technician' else 'AGENT'
            logger.info(f"[{session_id}] 🎯 {speaker_label}: Combined {len(buffer['chunks'])} chunks = {len(combined_audio)} bytes, duration={buffer['total_duration']:.2f}s")

            # ========================================
            # SILENCE DETECTION - Skip if audio is too quiet
            # ========================================
            import struct
            import numpy as np

            try:
                # Calculate RMS and max amplitude of the combined audio
                samples = struct.unpack(f'{len(combined_audio)//2}h', combined_audio)
                if len(samples) > 0:
                    audio_rms = np.sqrt(np.mean(np.square(samples)))
                    max_amplitude = max(abs(s) for s in samples)

                    # Get threshold based on sample rate
                    audio_sample_rate = buffer.get('sample_rate', 8000)
                    min_rms = self.config.min_rms_8k if audio_sample_rate == 8000 else self.config.min_rms_16k

                    logger.info(f"[{session_id}] 🔊 {speaker_label} Audio levels: RMS={audio_rms:.1f} (min={min_rms}), MaxAmp={max_amplitude} (silence_threshold={self.config.max_amplitude_silence})")

                    # Skip if audio is silence (below both RMS and amplitude thresholds)
                    if audio_rms < min_rms and max_amplitude < self.config.max_amplitude_silence:
                        logger.warning(f"[{session_id}] 🔇 {speaker_label} SILENCE - Skipping (RMS={audio_rms:.1f} < {min_rms}, MaxAmp={max_amplitude} < {self.config.max_amplitude_silence})")
                        return None

                    # Additional check: if RMS is very low, skip regardless of amplitude
                    if audio_rms < min_rms * 0.5:  # Less than 50% of threshold
                        logger.warning(f"[{session_id}] 🔇 {speaker_label} VERY LOW RMS - Skipping (RMS={audio_rms:.1f} < {min_rms * 0.5})")
                        return None

                    logger.info(f"[{session_id}] ✅ {speaker_label} Audio passed RMS check")

            except Exception as rms_error:
                logger.warning(f"[{session_id}] Could not calculate audio levels: {rms_error}")
                # Continue with transcription if we can't check RMS

            # ========================================
            # SILERO VAD VALIDATION - Confirm actual speech before Whisper
            # ========================================
            logger.info(f"[{session_id}] 🔍 Running Silero VAD validation...")
            has_speech = self._validate_speech_with_silero_vad(
                pcm_data=combined_audio,
                sample_rate=audio_sample_rate,
                session_id=session_id
            )

            if not has_speech:
                logger.warning(
                    f"[{session_id}] 🚫 {speaker_label} Silero VAD detected NO SPEECH - "
                    f"skipping Whisper transcription"
                )
                return None

            logger.info(f"[{session_id}] ✅ {speaker_label} Silero VAD confirmed speech - proceeding to Whisper")

            # Use explicit speaker if provided, otherwise detect via diarization
            if speaker in ['technician', 'agent']:
                # Speaker explicitly provided (from WebSocket stream)
                speaker_name = 'Agent' if speaker == 'agent' else 'Technicien'
                speaker_info = {
                    'speaker_id': speaker,
                    'speaker_name': speaker_name,
                    'speaker_role': speaker,
                    'confidence': 1.0,
                    'is_speech': True
                }
                logger.info(f"[{session_id}] ✅ Using explicit speaker: role='{speaker}', name='{speaker_name}'")
            else:
                # Detect speaker and voice activity via diarization
                speaker_info = self.diarization_service.identify_speaker(
                    session_id=session_id,
                    audio_data=combined_audio,
                    timestamp=buffer['start_time']
                )
                logger.info(f"[{session_id}] Diarization result: {speaker_info}")

            # Skip if no speech detected
            if not speaker_info.get('is_speech', False):
                logger.warning(f"[{session_id}] No speech detected in buffer (is_speech={speaker_info.get('is_speech')})")
                return None

            # Check if we should process this speaker (can be bypassed)
            if self.config.bypass_min_duration:
                logger.info(f"[{session_id}] ⏩ BYPASSING min duration check (bypass_min_duration=True)")
                should_process = True
            else:
                logger.info(f"[{session_id}] 🔍 Checking if speaker should be processed: role={speaker_info['speaker_role']}, duration={buffer['total_duration']:.2f}s")
                should_process = self.diarization_service.should_process_segment(
                    session_id=session_id,
                    speaker_role=speaker_info['speaker_role'],
                    segment_duration=buffer['total_duration']
                )
                logger.info(f"[{session_id}] 🔍 Should process result: {should_process}")

            if not should_process:
                logger.warning(
                    f"[{session_id}] ⚠️ SKIPPING segment from {speaker_info['speaker_role']} "
                    f"(duration: {buffer['total_duration']:.2f}s) - should_process_segment returned False!"
                )
                return None
            else:
                logger.info(f"[{session_id}] ✅ Speaker {speaker_info['speaker_role']} WILL be processed")

            # Create WAV file for Whisper (use sample rate from buffer)
            audio_sample_rate = buffer.get('sample_rate')
            if audio_sample_rate is None:
                logger.warning(f"[{session_id}] ⚠️ Buffer missing sample_rate! Defaulting based on speaker: {speaker}")
                audio_sample_rate = 8000 if speaker == 'technician' else 16000

            # Log the exact parameters being used for WAV creation
            logger.info(f"[{session_id}] 📊 WAV creation params: sample_rate={audio_sample_rate}Hz, bytes={len(combined_audio)}, speaker={speaker}")
            logger.info(f"[{session_id}] 📊 Expected duration: {len(combined_audio) / 2 / audio_sample_rate:.2f}s (bytes/2/sample_rate)")

            wav_buffer = self._create_wav_buffer(combined_audio, sample_rate=audio_sample_rate)
            logger.info(f"[{session_id}] ✅ Created WAV buffer at {audio_sample_rate}Hz")

            # Get transcription backend from config
            backend = self.config.transcription_backend
            language = self.config.transcription_language

            # Transcribe with selected backend
            logger.info(f"[{session_id}] 🎤 Sending {len(combined_audio)} bytes to {backend.upper()} API...")

            if backend == 'deepgram':
                # Use Deepgram Nova-3
                transcription_result = await self.deepgram_service.transcribe(
                    wav_buffer,
                    language=language,
                    sample_rate=audio_sample_rate
                )
            else:
                # Default to Whisper
                transcription_result = await self._transcribe_with_whisper(
                    wav_buffer,
                    language=language
                )

            if not transcription_result:
                logger.warning(f"[{session_id}] {backend.upper()} API returned None")
                return None

            if not transcription_result.get('text'):
                logger.warning(f"[{session_id}] {backend.upper()} returned empty text: {transcription_result}")
                return None

            logger.info(f"[{session_id}] {backend.upper()} transcription: '{transcription_result.get('text')[:100]}'...")

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
                'timestamp': datetime.utcnow().isoformat(),
                'pause_duration_ms': pause_duration_ms  # Pause before this segment
            }

            logger.info(
                f"[{session_id}] ✅ Transcription result created: "
                f"speaker_role='{result['speaker_role']}', speaker_name='{result['speaker_name']}', "
                f"text='{result['text'][:50]}...'"
            )

            # Send to agent processing pipeline
            await self._process_with_agents(result)

            return result

        except Exception as e:
            logger.error(f"Transcription error for session {session_id}: {e}")
            return None

    def _create_wav_buffer(self, pcm_data: bytes, sample_rate: int = None) -> io.BytesIO:
        """
        Create WAV file buffer from PCM data

        Args:
            pcm_data: PCM audio data (8kHz or 16kHz, 16-bit)
            sample_rate: Sample rate of audio (8000 for Twilio, 16000 for browser)

        Returns:
            BytesIO buffer containing WAV file
        """
        # Use provided sample rate or default
        effective_sample_rate = sample_rate if sample_rate else self.sample_rate

        # Calculate expected properties
        num_samples = len(pcm_data) // self.sample_width
        expected_duration = num_samples / effective_sample_rate

        logger.info(f"📼 _create_wav_buffer: {len(pcm_data)} bytes PCM → {num_samples} samples at {effective_sample_rate}Hz = {expected_duration:.2f}s")

        wav_buffer = io.BytesIO()

        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(self.sample_width)
            wav_file.setframerate(effective_sample_rate)  # Use actual sample rate
            wav_file.writeframes(pcm_data)

        wav_buffer.seek(0)
        wav_buffer.name = "audio.wav"  # Whisper API needs a name
        return wav_buffer

    def _is_hallucination(self, text: str) -> bool:
        """
        Detect common Whisper hallucinations

        Whisper sometimes produces hallucinated text instead of actual transcriptions,
        especially with unclear audio. Common patterns include:
        - Bullet points or repeated characters
        - Subtitle credits
        - Music descriptions
        - Thank you messages

        Args:
            text: Transcription text to check

        Returns:
            True if text appears to be hallucination, False otherwise
        """
        if not text or not text.strip():
            return True

        # Pattern 1: All or mostly bullets
        bullet_ratio = text.count('•') / len(text) if len(text) > 0 else 0
        if bullet_ratio > 0.5:
            logger.warning(f"🚫 Detected bullet hallucination (bullet ratio: {bullet_ratio:.2%})")
            return True

        # Pattern 2: Repeated characters (low diversity)
        text_no_spaces = text.replace(' ', '').replace('\n', '').replace('\t', '')
        if len(text_no_spaces) > 0:
            unique_chars = len(set(text_no_spaces))
            char_diversity = unique_chars / len(text_no_spaces)
            if unique_chars < 5 or char_diversity < 0.1:
                logger.warning(f"🚫 Detected repeated character hallucination (unique chars: {unique_chars}, diversity: {char_diversity:.2%})")
                return True

        # Pattern 3: Common hallucination phrases
        # These are typical outputs when Whisper processes silence or low-quality audio
        hallucinations = [
            # Subtitle/credits hallucinations
            "sous-titres par",
            "sous-titrage par",
            "subtitle by",
            "subtitled by",
            "sous-titres réalisés",
            "amara.org",
            "générique",
            "credits",
            "❤️ par SousTitreur.com",

            # Thank you/goodbye hallucinations (common with silence)
            "merci d'avoir regardé",
            "merci de regarder",
            "thanks for watching",
            "thank you for watching",
            "à bientôt",
            "à la prochaine",
            "et je vous dis à bientôt",
            "pour une nouvelle vidéo",

            # Music/sound hallucinations
            "♪♪♪",
            "♪ music ♪",
            "music playing",
            "[musique]",
            "[music]",
            "applause",
            "applaudissements",
            "[applaudissements]",
            "[silence]",
            "[bruit]",
            "[noise]",

            # Repeated/stuck phrases
            "je vous remercie",
            "bonne journée",
            "c'est tout",
            "c'est ça",
            "et voilà",
        ]

        # Pattern 4: Very short text (less than 3 words often = hallucination)
        words = text.strip().split()
        if len(words) <= 2 and len(text.strip()) < 15:
            logger.warning(f"🚫 Detected short text hallucination (words: {len(words)}, chars: {len(text.strip())}): '{text}'")
            return True

        # Pattern 5: Single word repeated
        if len(words) >= 2 and len(set(words)) == 1:
            logger.warning(f"🚫 Detected single word repeated hallucination: '{text}'")
            return True

        text_lower = text.lower().strip()

        # Check exact match for short phrases (avoid filtering real speech)
        short_hallucinations = [
            "merci.", "au revoir.", "bonjour.", "oui.", "non.", "ok.",
            "d'accord.", "voilà.", "alors.", "euh...", "...", "hum.", "hmm.",
            "merci", "au revoir", "bonjour", "oui", "non", "ok",
        ]
        if text_lower in short_hallucinations:
            logger.warning(f"🚫 Detected exact short hallucination: '{text}'")
            return True

        for phrase in hallucinations:
            if phrase in text_lower:
                logger.warning(f"🚫 Detected hallucination phrase: '{phrase}'")
                return True

        alnum_count = sum(c.isalnum() for c in text)
        ratio = alnum_count / len(text)

        if ratio < 0.3:  # менее 30% букв или цифр
            logger.warning(f"🚫 Detected non-alphanumeric hallucination (alnum ratio: {ratio:.2%})")
            return True

        return False

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
            # ========================================
            # DIAGNOSTIC LOGGING - AUDIO VERIFICATION
            # ========================================
            import struct
            import numpy as np

            # Get buffer size
            audio_buffer.seek(0, 2)  # Seek to end
            buffer_size = audio_buffer.tell()
            audio_buffer.seek(0)  # Reset to beginning

            prompt = "Transcribe the audio exactly as it is spoken. Do not add punctuation, do not complete unfinished sentences, and do not hallucinate background noise as words. Minimalist verbatim transcription only"

            logger.info(f"🔍 WHISPER DIAGNOSTIC - Audio buffer size: {buffer_size} bytes ({buffer_size / 1024:.2f} KB)")

            # ========================================
            # CALL WHISPER API
            # ========================================
            logger.info(f"🎯 Calling Whisper API with model=whisper-1, language={language}")

            # NOTE: Prompt removed due to causing hallucinations
            # Previous prompt with bullet points caused Whisper to output only bullets (•••)
            # Testing showed that WITHOUT prompt, Whisper transcribes correctly
            # See WHISPER_ISSUE_RESOLVED.md for details

            import time
            start_time = time.time()

        
            optimized_prompt = (
                "Technical support conversation, real-time streaming, technical terms, "
                "fragmented speech, incomplete sentences Transcription only, no corrections."
            )

            response = self.openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_buffer,
                language=language,
                prompt=optimized_prompt,
                response_format="verbose_json",
                temperature=0.0
            )

            api_duration = time.time() - start_time

            # ========================================
            # DIAGNOSTIC LOGGING - API RESPONSE
            # ========================================
            logger.info(f"🔍 WHISPER DIAGNOSTIC - API call completed in {api_duration:.2f}s")
            logger.info(f"🔍 WHISPER DIAGNOSTIC - Full response object type: {type(response)}")
            logger.info(f"🔍 WHISPER DIAGNOSTIC - Response attributes: {dir(response)}")

            # Log all response fields
            response_dict = {}
            if hasattr(response, 'text'):
                response_dict['text'] = response.text
                logger.info(f"🔍 WHISPER DIAGNOSTIC - response.text: '{response.text}'")
            else:
                logger.error(f"❌ WHISPER DIAGNOSTIC - Response has NO 'text' attribute!")

            if hasattr(response, 'language'):
                response_dict['language'] = response.language
                logger.info(f"🔍 WHISPER DIAGNOSTIC - response.language: '{response.language}'")
            else:
                logger.warning(f"⚠️ WHISPER DIAGNOSTIC - Response has NO 'language' attribute")

            if hasattr(response, 'duration'):
                response_dict['duration'] = response.duration
                logger.info(f"🔍 WHISPER DIAGNOSTIC - response.duration: {response.duration}s")
            else:
                logger.warning(f"⚠️ WHISPER DIAGNOSTIC - Response has NO 'duration' attribute")

            if hasattr(response, 'segments'):
                logger.info(f"🔍 WHISPER DIAGNOSTIC - response.segments count: {len(response.segments) if response.segments else 0}")

            # Check for empty or None response
            if not hasattr(response, 'text'):
                logger.error(f"❌ WHISPER DIAGNOSTIC - Response object is missing 'text' field - API may have returned error!")
                logger.error(f"❌ WHISPER DIAGNOSTIC - Full response: {response}")
                return None

            if response.text is None:
                logger.error(f"❌ WHISPER DIAGNOSTIC - response.text is None (not empty string, but None type)")
                logger.error(f"❌ WHISPER DIAGNOSTIC - This suggests Whisper could not process the audio")
                return None

            logger.info(f"🎯 Whisper API response: text='{response.text}', language={response.language}, duration={response.duration}")

            # Check for empty response
            if not response.text or response.text.strip() == '':
                logger.warning(f"⚠️ WHISPER DIAGNOSTIC - Whisper returned EMPTY text!")
                logger.warning(f"⚠️ WHISPER DIAGNOSTIC - This could mean:")
                logger.warning(f"   1. Audio is silent or too quiet")
                logger.warning(f"   2. Audio is too noisy/distorted")
                logger.warning(f"   3. Wrong language specified")
                logger.warning(f"   4. Audio format issue")
                logger.warning(f"⚠️ WHISPER DIAGNOSTIC - Full response: {response_dict}")
                return None

            # Check for hallucinations
            if self._is_hallucination(response.text):
                logger.warning(f"⚠️ WHISPER DIAGNOSTIC - Detected hallucination, discarding transcription")
                logger.warning(f"⚠️ WHISPER DIAGNOSTIC - Hallucinated text: '{response.text[:100]}...'")
                logger.warning(f"⚠️ WHISPER DIAGNOSTIC - This usually means audio quality is too low or unclear")
                logger.warning(f"⚠️ WHISPER DIAGNOSTIC - Possible causes:")
                logger.warning(f"   1. Audio is too quiet (check RMS levels in logs)")
                logger.warning(f"   2. Audio is mostly noise/silence")
                logger.warning(f"   3. Wrong audio track is being transcribed")
                logger.warning(f"   4. Microphone is not working properly")

                # DEBUG MODE: Return hallucination anyway if debug flag is set
                if self.config.debug_show_hallucinations:
                    logger.warning(f"🐛 DEBUG MODE: Returning hallucination for debugging (debug_show_hallucinations=True)")
                    # Add a debug marker to the text
                    result = {
                        'text': f"[HALLUCINATION - AUDIO QUALITY ISSUE] {response.text}",
                        'language': response.language,
                        'duration': response.duration,
                        'confidence': 0.0,  # Mark as low confidence
                        'is_hallucination': True
                    }
                    logger.warning(f"🐛 DEBUG: Returning marked hallucination for debugging")
                    return result
                return None

            # Valid transcription
            result = {
                'text': response.text + '',
                'language': response.language,
                'duration': response.duration,
                'confidence': getattr(response, 'confidence', 0.9)  # Not always available
            }

            logger.info(f"✅ WHISPER DIAGNOSTIC - Valid transcription received ({len(response.text)} chars)")
            return result

        except Exception as e:
            logger.error(f"❌ WHISPER API EXCEPTION: {type(e).__name__}: {e}", exc_info=True)
            logger.error(f"❌ WHISPER DIAGNOSTIC - Exception occurred during API call or response processing")
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

    async def initialize_session(
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

        # Initialize Deepgram streaming connections if enabled
        if (self.config.transcription_backend == 'deepgram' and
            self.config.deepgram_use_streaming):

            logger.info(
                f"[{session_id}] Initializing Deepgram streaming connections..."
            )

            # Create streaming connection for technician
            technician_key = f"{session_id}_technician"
            technician_connection = await self.deepgram_service.transcribe_streaming(
                session_id=technician_key,
                language=self.config.transcription_language,
                sample_rate=8000,  # Twilio audio is 8kHz
                on_transcript=self._create_streaming_callback(session_id, 'technician')
            )

            if technician_connection and technician_connection.is_connected:
                self.streaming_connections[technician_key] = technician_connection
                logger.info(f"✅ Deepgram streaming ready for technician ({technician_key})")
            else:
                logger.error(f"❌ Failed to initialize Deepgram streaming for technician")

            # Create streaming connection for agent (browser audio is 16kHz)
            agent_key = f"{session_id}_agent"
            agent_connection = await self.deepgram_service.transcribe_streaming(
                session_id=agent_key,
                language=self.config.transcription_language,
                sample_rate=16000,  # Browser audio is 16kHz
                on_transcript=self._create_streaming_callback(session_id, 'agent')
            )

            if agent_connection and agent_connection.is_connected:
                self.streaming_connections[agent_key] = agent_connection
                logger.info(f"✅ Deepgram streaming ready for agent ({agent_key})")
            else:
                logger.error(f"❌ Failed to initialize Deepgram streaming for agent")

        logger.info(
            f"Session initialized: {session_id} with technician {technician_name}"
        )

    def _create_streaming_callback(self, session_id: str, speaker: str):
        """
        Create callback function for Deepgram streaming results

        Args:
            session_id: Session identifier
            speaker: Speaker role ('technician' or 'agent')

        Returns:
            Callback function that handles transcription results
        """
        def on_transcript(result: Dict[str, Any]):
            """Handle streaming transcription result"""
            try:
                is_final = result.get('is_final', False)
                text = result.get('text', '')
                confidence = result.get('confidence', 0.0)

                # Only process final results (interim results are for UI feedback only)
                if is_final and text:
                    logger.info(
                        f"[{session_id}] 📝 Streaming FINAL result ({speaker}): "
                        f"'{text[:80]}...' (conf: {confidence:.2f})"
                    )

                    # Create transcription result in expected format
                    speaker_name = 'Agent' if speaker == 'agent' else 'Technicien'
                    transcription_result = {
                        'session_id': session_id,
                        'text': text,
                        'speaker_id': speaker,
                        'speaker_name': speaker_name,
                        'speaker_role': speaker,
                        'confidence': confidence,
                        'speaker_confidence': 1.0,
                        'start_time': timestamp if 'timestamp' in locals() else 0.0,
                        'end_time': timestamp if 'timestamp' in locals() else 0.0,
                        'duration': result.get('duration', 0.0),
                        'language': result.get('language', self.config.transcription_language),
                        'timestamp': datetime.utcnow().isoformat(),
                        'pause_duration_ms': 0.0  # Streaming mode doesn't track pauses
                    }

                    # Process with agents (async call needs to be scheduled)
                    asyncio.create_task(self._process_with_agents(transcription_result))

                elif not is_final and text:
                    # Interim result - log for debugging
                    logger.debug(
                        f"[{session_id}] 💭 Streaming interim ({speaker}): '{text[:50]}...'"
                    )

            except Exception as e:
                logger.error(f"[{session_id}] Error in streaming callback: {e}", exc_info=True)

        return on_transcript

    async def end_session(self, session_id: str) -> Dict[str, Any]:
        """
        End a session and get statistics

        Args:
            session_id: Session identifier

        Returns:
            Session statistics
        """
        # Close Deepgram streaming connections if any
        streaming_keys_to_delete = [
            key for key in self.streaming_connections.keys()
            if key.startswith(f"{session_id}_")
        ]
        for stream_key in streaming_keys_to_delete:
            connection = self.streaming_connections[stream_key]
            try:
                await connection.close()
                logger.info(f"✅ Closed Deepgram streaming connection: {stream_key}")
            except Exception as e:
                logger.error(f"Error closing streaming connection {stream_key}: {e}")
            del self.streaming_connections[stream_key]

        # Get speaker stats
        stats = self.diarization_service.get_speaker_stats(session_id)

        # Clear speaker-specific buffers (session_id_technician, session_id_agent)
        buffers_to_delete = [key for key in self.audio_buffers.keys() if key.startswith(f"{session_id}_")]
        for buffer_key in buffers_to_delete:
            del self.audio_buffers[buffer_key]
            logger.info(f"Cleared buffer: {buffer_key}")

        # Clear speaker data from diarization service (also clear VAD state for both speakers)
        self.diarization_service.clear_session(session_id)
        self.diarization_service.clear_session(f"{session_id}_technician")
        self.diarization_service.clear_session(f"{session_id}_agent")

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
