"""
Transcription Configuration Management
Provides runtime-configurable parameters for the transcription service
"""
import logging
import json
import os
from typing import Dict, Any
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger(__name__)

# Configuration file path
CONFIG_DIR = Path(__file__).parent
CONFIG_FILE = CONFIG_DIR / 'transcription_config.json'


@dataclass
class TranscriptionConfig:
    """Configuration for transcription service - all parameters can be adjusted at runtime"""

    # RMS (Root Mean Square) Thresholds for silence detection
    min_rms_8k: float = 50.0          # Minimum RMS for 8kHz Twilio audio (technician)
    min_rms_16k: float = 150.0        # Minimum RMS for 16kHz browser audio (agent)
    max_amplitude_silence: float = 300.0  # Maximum amplitude threshold for silence

    # Silero VAD (Voice Activity Detection) Parameters
    vad_threshold: float = 0.5        # Confidence threshold (0-1) - higher = stricter
    vad_min_speech_duration_ms: int = 250   # Minimum speech duration in milliseconds
    vad_min_silence_duration_ms: int = 1000  # Minimum silence between speech segments (1 second)

    # Audio Buffering Parameters
    buffer_duration: float = 3.0      # Seconds to buffer before transcribing
    max_buffer_duration: float = 10.0 # Force transcription after this duration
    min_bytes_8k: int = 48000         # Minimum bytes for 8kHz (3 seconds @ 8kHz, 16-bit)
    min_bytes_16k: int = 96000        # Minimum bytes for 16kHz (3 seconds @ 16kHz, 16-bit)

    # Frame Grouping Parameters (Frontend)
    frontend_pause_threshold: int = 2000  # Pause threshold for Frontend mode (Web Speech API) in ms
    backend_segment_pause: int = 3000     # Pause threshold for Backend mode frame grouping in ms

    # Transcription Backend
    transcription_backend: str = 'whisper'  # 'whisper' or 'deepgram'
    transcription_language: str = 'fr'      # Language code for transcription
    deepgram_use_streaming: bool = True     # Use WebSocket streaming for Deepgram (faster)
    deepgram_show_interim: bool = False     # Show interim results in real-time (Deepgram streaming only)

    # Feature Flags
    bypass_vad: bool = True           # Use simple byte-count triggering instead of VAD
    bypass_min_duration: bool = False # Skip minimum duration checks
    debug_show_hallucinations: bool = False  # Show hallucinated transcriptions for debugging

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return asdict(self)

    def save_to_file(self, filepath: Path = CONFIG_FILE) -> None:
        """Save configuration to JSON file"""
        try:
            with open(filepath, 'w') as f:
                json.dump(self.to_dict(), f, indent=2)
            logger.info(f"Configuration saved to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save configuration to {filepath}: {e}")
            raise

    @classmethod
    def load_from_file(cls, filepath: Path = CONFIG_FILE) -> 'TranscriptionConfig':
        """Load configuration from JSON file"""
        try:
            if filepath.exists():
                with open(filepath, 'r') as f:
                    data = json.load(f)
                config = cls()
                config.update_from_dict(data)
                logger.info(f"Configuration loaded from {filepath}")
                return config
            else:
                logger.info(f"No saved configuration found at {filepath}, using defaults")
                return cls()
        except Exception as e:
            logger.error(f"Failed to load configuration from {filepath}: {e}, using defaults")
            return cls()

    def update_from_dict(self, updates: Dict[str, Any]) -> None:
        """Update configuration from dictionary"""
        for key, value in updates.items():
            if hasattr(self, key):
                # Validate type matches
                expected_type = type(getattr(self, key))
                if not isinstance(value, expected_type):
                    # Try to convert
                    try:
                        value = expected_type(value)
                    except (ValueError, TypeError):
                        logger.warning(f"Cannot convert {key}={value} to {expected_type}")
                        continue

                setattr(self, key, value)
                logger.info(f"Updated config: {key} = {value}")
            else:
                logger.warning(f"Unknown config parameter: {key}")

    def get_parameter_info(self) -> Dict[str, Dict[str, Any]]:
        """Get metadata about each parameter including ranges and descriptions"""
        return {
            'min_rms_8k': {
                'type': 'float',
                'min': 10.0,
                'max': 500.0,
                'step': 10.0,
                'description': 'Minimum RMS for 8kHz phone audio (lower = more sensitive)',
                'unit': 'RMS level'
            },
            'min_rms_16k': {
                'type': 'float',
                'min': 50.0,
                'max': 1000.0,
                'step': 10.0,
                'description': 'Minimum RMS for 16kHz browser audio (lower = more sensitive)',
                'unit': 'RMS level'
            },
            'max_amplitude_silence': {
                'type': 'float',
                'min': 100.0,
                'max': 1000.0,
                'step': 50.0,
                'description': 'Maximum amplitude to consider as silence',
                'unit': 'amplitude'
            },
            'vad_threshold': {
                'type': 'float',
                'min': 0.1,
                'max': 0.9,
                'step': 0.05,
                'description': 'VAD confidence threshold (higher = stricter speech detection)',
                'unit': 'confidence (0-1)'
            },
            'vad_min_speech_duration_ms': {
                'type': 'int',
                'min': 100,
                'max': 1000,
                'step': 50,
                'description': 'Minimum speech duration to process',
                'unit': 'milliseconds'
            },
            'vad_min_silence_duration_ms': {
                'type': 'int',
                'min': 500,
                'max': 3000,
                'step': 100,
                'description': 'Minimum silence between speech segments (pause threshold)',
                'unit': 'milliseconds'
            },
            'buffer_duration': {
                'type': 'float',
                'min': 1.0,
                'max': 10.0,
                'step': 0.5,
                'description': 'Default buffer duration before transcribing',
                'unit': 'seconds'
            },
            'max_buffer_duration': {
                'type': 'float',
                'min': 5.0,
                'max': 30.0,
                'step': 1.0,
                'description': 'Force transcription after this duration',
                'unit': 'seconds'
            },
            'min_bytes_8k': {
                'type': 'int',
                'min': 8000,
                'max': 160000,
                'step': 8000,
                'description': 'Minimum bytes for 8kHz audio (1 sec = 16000 bytes)',
                'unit': 'bytes'
            },
            'min_bytes_16k': {
                'type': 'int',
                'min': 16000,
                'max': 320000,
                'step': 16000,
                'description': 'Minimum bytes for 16kHz audio (1 sec = 32000 bytes)',
                'unit': 'bytes'
            },
            'bypass_vad': {
                'type': 'bool',
                'description': 'Use simple byte-count triggering instead of VAD',
                'unit': 'boolean'
            },
            'bypass_min_duration': {
                'type': 'bool',
                'description': 'Skip minimum duration checks',
                'unit': 'boolean'
            },
            'debug_show_hallucinations': {
                'type': 'bool',
                'description': 'Show hallucinated transcriptions for debugging',
                'unit': 'boolean'
            }
        }


# Singleton instance - load from file if exists, otherwise use defaults
_transcription_config: TranscriptionConfig = TranscriptionConfig.load_from_file()


def get_transcription_config() -> TranscriptionConfig:
    """Get the global transcription configuration instance"""
    return _transcription_config


def update_transcription_config(updates: Dict[str, Any]) -> TranscriptionConfig:
    """Update the global transcription configuration and save to file"""
    config = get_transcription_config()
    config.update_from_dict(updates)
    config.save_to_file()  # Persist changes to disk
    logger.info(f"Transcription configuration updated and saved: {updates}")
    return config


def reset_transcription_config() -> TranscriptionConfig:
    """Reset configuration to defaults and save to file"""
    global _transcription_config
    _transcription_config = TranscriptionConfig()
    _transcription_config.save_to_file()  # Persist defaults to disk
    logger.info("Transcription configuration reset to defaults and saved")
    return _transcription_config
