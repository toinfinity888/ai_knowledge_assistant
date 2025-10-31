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

        # Simple VAD threshold
        self.vad_threshold = 0.01
        self.min_speech_duration = 0.5  # seconds

        logger.info("SpeakerDiarizationService initialized")

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
            speaker_role: Role (e.g., 'technician', 'support_agent')
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
        is_speech = self._detect_voice_activity(audio_data)

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

    def _detect_voice_activity(self, audio_data: bytes) -> bool:
        """
        Simple voice activity detection using energy threshold

        Args:
            audio_data: PCM audio data (16-bit)

        Returns:
            True if speech is detected, False otherwise
        """
        try:
            # Convert bytes to numpy array
            audio_array = np.frombuffer(audio_data, dtype=np.int16)

            # Calculate RMS energy
            rms = np.sqrt(np.mean(audio_array.astype(np.float32) ** 2))

            # Normalize by max int16 value
            normalized_rms = rms / 32768.0

            # Check against threshold
            return normalized_rms > self.vad_threshold

        except Exception as e:
            logger.error(f"VAD error: {e}")
            return False

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
        # Always process technician speech if long enough
        if speaker_role == 'technician':
            return segment_duration >= self.min_speech_duration

        # Process support agent speech only if significant
        if speaker_role == 'support_agent':
            return segment_duration >= 1.0  # Longer threshold for agent

        # Don't process unknown speakers
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

        logger.info(f"Cleared speaker data for session {session_id}")


# Singleton instance
_diarization_service: Optional[SpeakerDiarizationService] = None


def get_diarization_service() -> SpeakerDiarizationService:
    """Get or create speaker diarization service instance"""
    global _diarization_service

    if _diarization_service is None:
        _diarization_service = SpeakerDiarizationService()

    return _diarization_service
