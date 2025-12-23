"""
Speaker Diarization Service
Identifies who is speaking (technician vs. support agent) in real-time
Prioritizes technician's speech for problem understanding
"""
import logging
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import io

logger = logging.getLogger(__name__)


class SpeakerDiarizationService:
    """
    Performs speaker diarization to identify speakers in audio
    Uses simple voice activity detection and speaker embeddings
    """

    def __init__(self):
        self.speaker_profiles: Dict[str, Dict] = {}
        self.current_speaker: Optional[str] = None
        self.speaker_history: List[Dict] = []

        # VAD thresholds
        self.vad_threshold = 0.03  # Minimum RMS to consider as speech (normalized 0-1)
        self.silence_threshold = 0.01  # RMS below this = silence
        self.min_speech_duration = 0.8  # Minimum duration to consider as valid speech (seconds)
        self.silence_duration_to_segment = 0.5  # Duration of silence to trigger segmentation (seconds)

        # Minimum average RMS for the entire segment to be transcribed (speaker-specific)
        # Below these thresholds, audio is likely too quiet for Whisper to transcribe accurately
        #
        # AGENT (browser microphone with 2.5x gain applied in frontend):
        #   - Silence: ~50, Background noise: ~100-150, Quiet speech: ~200-300, Normal speech: ~400+
        #   - Threshold: 200.0 (accounting for frontend 2.5x gain amplification)
        #
        # TECHNICIAN (phone call, 8kHz mulaw upsampled to 16kHz PCM):
        #   - Phone audio typically quieter, compressed by carrier
        #   - No frontend gain applied
        #   - Threshold: 10.0 (very low to catch mulaw-decoded audio)
        self.min_segment_rms_agent = 200.0  # Agent microphone (with 2.5x gain)
        self.min_segment_rms_technician = 2.0  # Technician phone (VERY LOW for mulaw audio)

        # VAD state tracking per session
        self.vad_state: Dict[str, Dict] = {}  # session_id -> {is_speaking, silence_start, rms_samples, etc}

        logger.info("SpeakerDiarizationService initialized with VAD-based segmentation")

    def get_min_rms_for_speaker(self, session_id: str) -> float:
        """
        Get the appropriate minimum RMS threshold based on speaker type

        Args:
            session_id: Session identifier (can be "session_123_agent" or "session_123_technician")

        Returns:
            Minimum RMS threshold for the speaker
        """
        # Check if session_id contains speaker identifier
        if '_agent' in session_id:
            return self.min_segment_rms_agent
        elif '_technician' in session_id:
            return self.min_segment_rms_technician
        else:
            # Default to technician threshold (more permissive) if unclear
            logger.warning(f"Could not determine speaker type from session_id '{session_id}', using technician threshold")
            return self.min_segment_rms_technician

    def register_speaker(
        self,
        session_id: str,
        speaker_id: str,
        speaker_name: str,
        speaker_role: str,
        audio_sample: Optional[bytes] = None
    ):
        """
        Register a speaker profile

        Args:
            session_id: Session identifier
            speaker_id: Unique speaker identifier
            speaker_name: Speaker's name
            speaker_role: Role ('technician' for phone caller, 'agent' for browser support)
            audio_sample: Optional audio sample for voice profile
        """
        key = f"{session_id}:{speaker_id}"

        self.speaker_profiles[key] = {
            'speaker_id': speaker_id,
            'speaker_name': speaker_name,
            'speaker_role': speaker_role,
            'session_id': session_id,
            'registered_at': datetime.utcnow(),
            'embedding': None  # Will be computed if audio_sample provided
        }

        logger.info(f"Registered speaker: {speaker_name} ({speaker_role}) for session {session_id}")

    def identify_speaker(
        self,
        session_id: str,
        audio_data: bytes,
        timestamp: float
    ) -> Dict[str, any]:
        """
        Identify which speaker is talking in the audio segment

        For MVP: We'll use a simple heuristic based on call direction
        - Audio from phone line = technician
        - Audio from system = support agent (AI)

        For production: Can be enhanced with actual speaker embeddings

        Args:
            session_id: Session identifier
            audio_data: Audio data to analyze
            timestamp: Timestamp of audio segment

        Returns:
            Speaker identification result
        """
        # Simple voice activity detection
        is_speech, rms = self._detect_voice_activity(audio_data)

        if not is_speech:
            return {
                'session_id': session_id,
                'timestamp': timestamp,
                'is_speech': False,
                'speaker_id': None,
                'speaker_name': None,
                'speaker_role': None,
                'confidence': 0.0
            }

        # For Twilio integration:
        # All incoming audio is from technician (phone line)
        # We'll identify based on registered speakers for this session
        technician = self._get_speaker_by_role(session_id, 'technician')

        if technician:
            result = {
                'session_id': session_id,
                'timestamp': timestamp,
                'is_speech': True,
                'speaker_id': technician['speaker_id'],
                'speaker_name': technician['speaker_name'],
                'speaker_role': technician['speaker_role'],
                'confidence': 0.95  # High confidence for phone line audio
            }

            # Track current speaker
            self.current_speaker = technician['speaker_id']

            # Add to history
            self.speaker_history.append({
                **result,
                'detected_at': datetime.utcnow()
            })

            return result

        # Unknown speaker
        return {
            'session_id': session_id,
            'timestamp': timestamp,
            'is_speech': True,
            'speaker_id': 'unknown',
            'speaker_name': 'Unknown',
            'speaker_role': 'unknown',
            'confidence': 0.5
        }

    def _detect_voice_activity(self, audio_data: bytes) -> tuple[bool, float]:
        """
        Simple voice activity detection using energy threshold

        Args:
            audio_data: PCM audio data (16-bit)

        Returns:
            Tuple of (is_speech: bool, normalized_rms: float)
        """
        try:
            # Convert bytes to numpy array
            audio_array = np.frombuffer(audio_data, dtype=np.int16)

            # Calculate RMS energy
            rms = np.sqrt(np.mean(audio_array.astype(np.float32) ** 2))

            # Normalize by max int16 value
            normalized_rms = rms / 32768.0

            # Check against threshold
            is_speech = normalized_rms > self.vad_threshold

            logger.debug(f"VAD: RMS={rms:.1f}, normalized={normalized_rms:.4f}, is_speech={is_speech}")

            return is_speech, normalized_rms

        except Exception as e:
            logger.error(f"VAD error: {e}")
            return False, 0.0

    def check_speech_ended(
        self,
        session_id: str,
        audio_data: bytes,
        chunk_duration: float,
        current_timestamp: float
    ) -> tuple[bool, str, float]:
        """
        Check if speech has ended based on VAD (Voice Activity Detection)

        Args:
            session_id: Session identifier
            audio_data: Current audio chunk
            chunk_duration: Duration of current chunk in seconds
            current_timestamp: Current timestamp

        Returns:
            Tuple of (should_segment: bool, reason: str, pause_duration_ms: float)
        """
        # Detect voice activity in current chunk
        is_speech, rms = self._detect_voice_activity(audio_data)

        # Initialize VAD state if needed
        if session_id not in self.vad_state:
            self.vad_state[session_id] = {
                'is_speaking': False,
                'silence_start': None,
                'last_speech_timestamp': None,
                'speech_start': None,
                'rms_samples': []  # Track RMS values during speech
            }

        state = self.vad_state[session_id]

        # Calculate absolute RMS (not normalized) for segment quality check
        import numpy as np
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        absolute_rms = np.sqrt(np.mean(audio_array.astype(np.float32) ** 2))

        # Speech detected
        if is_speech:
            if not state['is_speaking']:
                # Transition: silence → speech
                logger.info(f"[{session_id}] 🗣️ Speech started (RMS={absolute_rms:.1f})")
                state['speech_start'] = current_timestamp
                state['rms_samples'] = []  # Reset RMS tracking for new segment

            # Track RMS during speech for segment quality assessment
            state['rms_samples'].append(absolute_rms)
            state['is_speaking'] = True
            state['last_speech_timestamp'] = current_timestamp
            state['silence_start'] = None
            return False, "speech_ongoing", 0.0

        # Silence detected
        else:
            if state['is_speaking']:
                # Transition: speech → silence
                if state['silence_start'] is None:
                    state['silence_start'] = current_timestamp
                    logger.info(f"[{session_id}] 🤐 Silence started (RMS={rms:.4f})")

                # Check if we've had enough silence to segment
                silence_duration = current_timestamp - state['silence_start']

                if silence_duration >= self.silence_duration_to_segment:
                    # Speech has ended - check if segment quality is good enough for transcription
                    if state['rms_samples']:
                        avg_rms = np.mean(state['rms_samples'])
                        max_rms = np.max(state['rms_samples'])

                        logger.info(f"[{session_id}] ✂️ Speech ended after {silence_duration:.2f}s of silence")
                        logger.info(f"[{session_id}] 📊 Segment RMS stats: avg={avg_rms:.1f}, max={max_rms:.1f}, samples={len(state['rms_samples'])}")

                        # Get speaker-specific RMS threshold
                        min_rms_threshold = self.get_min_rms_for_speaker(session_id)

                        # Check if average RMS is high enough for transcription
                        if avg_rms < min_rms_threshold:
                            logger.warning(f"[{session_id}] ⚠️ Segment RMS too low ({avg_rms:.1f} < {min_rms_threshold}) - SKIPPING Whisper call to avoid hallucinations")
                            state['is_speaking'] = False
                            state['silence_start'] = None
                            state['rms_samples'] = []
                            return True, f"rms_too_low_{avg_rms:.1f}", silence_duration * 1000
                        else:
                            logger.info(f"[{session_id}] ✅ Segment RMS acceptable ({avg_rms:.1f} >= {min_rms_threshold}) - SEGMENTING for transcription")
                            state['is_speaking'] = False
                            state['silence_start'] = None
                            state['rms_samples'] = []
                            return True, f"silence_threshold_reached_{silence_duration:.2f}s_rms_{avg_rms:.1f}", silence_duration * 1000
                    else:
                        # No RMS samples collected (shouldn't happen, but handle gracefully)
                        logger.warning(f"[{session_id}] ⚠️ No RMS samples collected during segment - SKIPPING")
                        state['is_speaking'] = False
                        state['silence_start'] = None
                        return True, "no_rms_data", 0.0
                else:
                    logger.debug(f"[{session_id}] 🤫 In silence period: {silence_duration:.2f}s / {self.silence_duration_to_segment}s")
                    return False, f"silence_accumulating_{silence_duration:.2f}s", silence_duration * 1000

            # Still in silence (no active speech)
            return False, "no_active_speech", 0.0

    def _get_speaker_by_role(self, session_id: str, role: str) -> Optional[Dict]:
        """
        Get speaker profile by role for a session

        Args:
            session_id: Session identifier
            role: Speaker role to find

        Returns:
            Speaker profile or None
        """
        for key, profile in self.speaker_profiles.items():
            if profile['session_id'] == session_id and profile['speaker_role'] == role:
                return profile
        return None

    def get_speaker_stats(self, session_id: str) -> Dict[str, any]:
        """
        Get speaking statistics for a session

        Args:
            session_id: Session identifier

        Returns:
            Statistics about who spoke when
        """
        session_history = [
            entry for entry in self.speaker_history
            if entry['session_id'] == session_id
        ]

        if not session_history:
            return {
                'session_id': session_id,
                'total_segments': 0,
                'speakers': {}
            }

        # Count segments per speaker
        speaker_counts = {}
        for entry in session_history:
            speaker_id = entry['speaker_id']
            if speaker_id not in speaker_counts:
                speaker_counts[speaker_id] = {
                    'speaker_name': entry['speaker_name'],
                    'speaker_role': entry['speaker_role'],
                    'segment_count': 0,
                    'first_spoke': entry['detected_at'],
                    'last_spoke': entry['detected_at']
                }

            speaker_counts[speaker_id]['segment_count'] += 1
            speaker_counts[speaker_id]['last_spoke'] = entry['detected_at']

        return {
            'session_id': session_id,
            'total_segments': len(session_history),
            'speakers': speaker_counts
        }

    def prioritize_technician_speech(
        self,
        session_id: str,
        segments: List[Dict]
    ) -> List[Dict]:
        """
        Prioritize technician's speech segments over others

        Args:
            session_id: Session identifier
            segments: List of speech segments with speaker info

        Returns:
            Sorted segments with technician first
        """
        technician_segments = []
        other_segments = []

        for segment in segments:
            if segment.get('speaker_role') == 'technician':
                technician_segments.append(segment)
            else:
                other_segments.append(segment)

        # Return technician segments first, then others
        return technician_segments + other_segments

    def should_process_segment(
        self,
        session_id: str,
        speaker_role: str,
        segment_duration: float
    ) -> bool:
        """
        Determine if a speech segment should be processed for AI analysis

        Prioritizes technician speech and filters out very short segments

        Args:
            session_id: Session identifier
            speaker_role: Role of the speaker
            segment_duration: Duration of segment in seconds

        Returns:
            True if segment should be processed, False otherwise
        """
        logger.info(f"[{session_id}] 🔍 should_process_segment: role='{speaker_role}', duration={segment_duration:.2f}s")

        # Always process technician speech if long enough
        if speaker_role == 'technician':
            result = segment_duration >= self.min_speech_duration
            logger.info(f"[{session_id}] ✅ technician role: duration {segment_duration:.2f}s >= {self.min_speech_duration}s? {result}")
            return result

        # Process agent speech (support person in browser)
        if speaker_role == 'agent':
            result = segment_duration >= self.min_speech_duration
            logger.info(f"[{session_id}] ✅ agent role: duration {segment_duration:.2f}s >= {self.min_speech_duration}s? {result}")
            return result

        # Don't process unknown speakers
        logger.warning(f"[{session_id}] ❌ Unknown speaker_role '{speaker_role}' - REJECTING segment!")
        return False

    def clear_session(self, session_id: str):
        """
        Clear speaker data for a session

        Args:
            session_id: Session identifier
        """
        # Remove speaker profiles
        keys_to_remove = [
            key for key in self.speaker_profiles.keys()
            if self.speaker_profiles[key]['session_id'] == session_id
        ]

        for key in keys_to_remove:
            del self.speaker_profiles[key]

        # Remove history
        self.speaker_history = [
            entry for entry in self.speaker_history
            if entry['session_id'] != session_id
        ]

        # Remove VAD state
        if session_id in self.vad_state:
            del self.vad_state[session_id]

        logger.info(f"Cleared speaker data and VAD state for session {session_id}")


# Singleton instance
_diarization_service: Optional[SpeakerDiarizationService] = None


def get_diarization_service() -> SpeakerDiarizationService:
    """Get or create speaker diarization service instance"""
    global _diarization_service

    if _diarization_service is None:
        _diarization_service = SpeakerDiarizationService()

    return _diarization_service
