#!/usr/bin/env python3
"""
Audio Recording Analysis Tool

This script analyzes WAV recordings from Twilio calls to help debug
audio quality issues and transcription problems.

Usage:
    python analyze_recording.py <path_to_wav_file>
    python analyze_recording.py audio_recordings/technician_*.wav

Features:
- Display audio file metadata (duration, sample rate, channels)
- Calculate RMS levels across the entire file
- Detect silence segments
- Show amplitude statistics
- Visualize waveform (if matplotlib available)
- Test transcription with Whisper API (if OpenAI key available)
"""

import sys
import wave
import struct
import argparse
from pathlib import Path
import numpy as np

# ANSI colors for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(text):
    """Print colored header"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text:^80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}\n")


def print_section(text):
    """Print colored section"""
    print(f"\n{Colors.CYAN}{Colors.BOLD}{text}{Colors.ENDC}")
    print(f"{Colors.CYAN}{'-'*len(text)}{Colors.ENDC}")


def analyze_audio_file(filepath: Path):
    """
    Analyze a WAV audio file and print statistics

    Args:
        filepath: Path to WAV file
    """
    print_header(f"Audio Recording Analysis: {filepath.name}")

    try:
        with wave.open(str(filepath), 'rb') as wav:
            # Extract metadata
            n_channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            framerate = wav.getframerate()
            n_frames = wav.getnframes()
            duration = n_frames / framerate

            print_section("📋 File Information")
            print(f"  File: {filepath}")
            print(f"  Size: {filepath.stat().st_size / 1024 / 1024:.2f} MB")
            print(f"  Modified: {filepath.stat().st_mtime}")

            print_section("🎵 Audio Format")
            print(f"  Channels: {n_channels} ({'Mono' if n_channels == 1 else 'Stereo'})")
            print(f"  Sample Rate: {framerate} Hz ({framerate/1000:.0f} kHz)")
            print(f"  Bit Depth: {sample_width * 8} bits")
            print(f"  Duration: {duration:.2f} seconds ({duration/60:.2f} minutes)")
            print(f"  Total Frames: {n_frames:,}")

            # Read all audio data
            print_section("📊 Reading Audio Data")
            print(f"  Reading {n_frames:,} frames...")
            audio_data = wav.readframes(n_frames)
            print(f"  ✓ Read {len(audio_data):,} bytes")

            # Unpack to samples
            print(f"  Unpacking to 16-bit signed integers...")
            format_char = f'{n_frames * n_channels}h'  # h = signed short (16-bit)
            samples = struct.unpack(format_char, audio_data)
            samples_array = np.array(samples)
            print(f"  ✓ Unpacked {len(samples):,} samples")

            # Calculate statistics
            print_section("📈 Audio Statistics")

            # RMS
            rms = np.sqrt(np.mean(np.square(samples_array)))
            print(f"  RMS Level: {rms:.1f}")

            # RMS quality assessment
            if rms < 10:
                rms_status = f"{Colors.RED}VERY QUIET - Silent or near-silent{Colors.ENDC}"
            elif rms < 100:
                rms_status = f"{Colors.YELLOW}QUIET - Below technician threshold (100){Colors.ENDC}"
            elif rms < 500:
                rms_status = f"{Colors.YELLOW}MODERATE - Below normal speech range{Colors.ENDC}"
            elif rms < 2000:
                rms_status = f"{Colors.GREEN}GOOD - Normal speech range{Colors.ENDC}"
            elif rms < 5000:
                rms_status = f"{Colors.YELLOW}LOUD - Upper normal range{Colors.ENDC}"
            else:
                rms_status = f"{Colors.RED}VERY LOUD - Possible clipping{Colors.ENDC}"

            print(f"  Status: {rms_status}")

            # Amplitude
            min_amplitude = np.min(samples_array)
            max_amplitude = np.max(samples_array)
            abs_max = max(abs(min_amplitude), abs(max_amplitude))
            print(f"\n  Min Amplitude: {min_amplitude}")
            print(f"  Max Amplitude: {max_amplitude}")
            print(f"  Absolute Max: {abs_max}")

            # Clipping check
            clipping_threshold = 32767 * 0.95  # 95% of max 16-bit value
            if abs_max > clipping_threshold:
                print(f"  {Colors.RED}⚠️  WARNING: Possible clipping detected!{Colors.ENDC}")

            # Mean and standard deviation
            mean = np.mean(samples_array)
            std = np.std(samples_array)
            print(f"\n  Mean: {mean:.2f}")
            print(f"  Standard Deviation: {std:.2f}")

            # Zero crossings (indicates frequency content)
            zero_crossings = np.sum(np.diff(np.sign(samples_array)) != 0)
            zcr = zero_crossings / len(samples_array)
            print(f"\n  Zero Crossings: {zero_crossings:,}")
            print(f"  Zero Crossing Rate: {zcr:.6f}")

            # Silence detection (RMS in 1-second windows)
            print_section("🔇 Silence Detection")
            window_size = framerate  # 1 second windows
            n_windows = n_frames // window_size

            silence_threshold = 100  # Same as technician threshold
            silent_windows = 0

            print(f"  Analyzing {n_windows} windows of 1 second each...")
            print(f"  Silence threshold: RMS < {silence_threshold}")

            for i in range(n_windows):
                start_idx = i * window_size * n_channels
                end_idx = (i + 1) * window_size * n_channels
                window_samples = samples_array[start_idx:end_idx]
                window_rms = np.sqrt(np.mean(np.square(window_samples)))

                if window_rms < silence_threshold:
                    silent_windows += 1

            silence_percentage = (silent_windows / n_windows) * 100
            speech_percentage = 100 - silence_percentage

            print(f"\n  Silent windows: {silent_windows} / {n_windows} ({silence_percentage:.1f}%)")
            print(f"  Speech windows: {n_windows - silent_windows} / {n_windows} ({speech_percentage:.1f}%)")

            if silence_percentage > 80:
                print(f"  {Colors.RED}⚠️  WARNING: Mostly silence - check microphone!{Colors.ENDC}")
            elif silence_percentage > 50:
                print(f"  {Colors.YELLOW}⚠️  High silence percentage - verify audio quality{Colors.ENDC}")
            else:
                print(f"  {Colors.GREEN}✓ Good speech-to-silence ratio{Colors.ENDC}")

            # Transcription quality assessment
            print_section("🎤 Transcription Quality Assessment")

            if rms < 100:
                print(f"  {Colors.RED}❌ LOW: Audio too quiet for reliable transcription{Colors.ENDC}")
                print(f"     Recommendation: Ask technician to speak louder or use better microphone")
            elif silence_percentage > 80:
                print(f"  {Colors.RED}❌ LOW: Mostly silence detected{Colors.ENDC}")
                print(f"     Recommendation: Verify call is connected and microphone is working")
            elif abs_max > clipping_threshold:
                print(f"  {Colors.YELLOW}⚠️  MODERATE: Possible clipping may affect quality{Colors.ENDC}")
                print(f"     Recommendation: Reduce input volume slightly")
            else:
                print(f"  {Colors.GREEN}✓ GOOD: Audio should transcribe well{Colors.ENDC}")
                print(f"     RMS: {rms:.1f} | Speech: {speech_percentage:.1f}% | No clipping")

    except Exception as e:
        print(f"\n{Colors.RED}❌ Error analyzing file: {e}{Colors.ENDC}")
        return False

    return True


def plot_waveform(filepath: Path):
    """
    Plot waveform visualization (requires matplotlib)

    Args:
        filepath: Path to WAV file
    """
    try:
        import matplotlib.pyplot as plt

        print_section("📊 Generating Waveform Visualization")

        with wave.open(str(filepath), 'rb') as wav:
            framerate = wav.getframerate()
            n_frames = wav.getnframes()
            audio_data = wav.readframes(n_frames)
            samples = np.array(struct.unpack(f'{n_frames}h', audio_data))

        # Create time axis
        time_axis = np.arange(len(samples)) / framerate

        # Plot
        plt.figure(figsize=(14, 6))
        plt.plot(time_axis, samples, linewidth=0.5)
        plt.title(f'Waveform: {filepath.name}', fontsize=14, fontweight='bold')
        plt.xlabel('Time (seconds)', fontsize=12)
        plt.ylabel('Amplitude', fontsize=12)
        plt.grid(True, alpha=0.3)
        plt.axhline(y=0, color='r', linestyle='--', alpha=0.3)

        # Add RMS threshold lines
        plt.axhline(y=100, color='orange', linestyle='--', alpha=0.5, label='Technician threshold (RMS 100)')
        plt.axhline(y=-100, color='orange', linestyle='--', alpha=0.5)
        plt.legend()

        plt.tight_layout()
        print(f"  ✓ Displaying plot...")
        plt.show()

    except ImportError:
        print(f"  {Colors.YELLOW}⚠️  matplotlib not installed - skipping visualization{Colors.ENDC}")
        print(f"     Install with: pip install matplotlib")
    except Exception as e:
        print(f"  {Colors.RED}❌ Error creating plot: {e}{Colors.ENDC}")


def test_transcription(filepath: Path, language: str = "fr"):
    """
    Test transcription using OpenAI Whisper API

    Args:
        filepath: Path to WAV file
        language: Language code (fr, en, etc.)
    """
    try:
        from openai import OpenAI
        from dotenv import load_dotenv
        import os
        load_dotenv()

        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        print_section("🤖 Testing Whisper Transcription")
        print(f"  Language: {language}")
        print(f"  Sending to Whisper API...")

        client = OpenAI(api_key=OPENAI_API_KEY)
        with open(filepath, 'rb') as audio_file:
            result = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language=language
            )

        text = result.text.strip()

        if text:
            print(f"\n  {Colors.GREEN}✓ Transcription successful:{Colors.ENDC}")
            print(f"  {Colors.BOLD}\"{text}\"{Colors.ENDC}")
            print(f"\n  Length: {len(text)} characters")
        else:
            print(f"  {Colors.YELLOW}⚠️  Empty transcription returned{Colors.ENDC}")
            print(f"     Possible causes: silence, non-speech audio, or wrong language")

    except ImportError:
        print(f"  {Colors.YELLOW}⚠️  OpenAI library not installed - skipping transcription test{Colors.ENDC}")
        print(f"     Install with: pip install openai")
    except Exception as e:
        print(f"  {Colors.RED}❌ Error testing transcription: {e}{Colors.ENDC}")
        if "api_key" in str(e).lower():
            print(f"     Make sure OPENAI_API_KEY environment variable is set")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze audio recordings from Twilio calls",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze a single recording
  python analyze_recording.py audio_recordings/technician_MZ123_20251110.wav

  # Analyze with visualization
  python analyze_recording.py audio_recordings/technician_MZ123_20251110.wav --plot

  # Analyze and test transcription
  python analyze_recording.py audio_recordings/technician_MZ123_20251110.wav --transcribe --language en

  # Analyze latest recording
  python analyze_recording.py audio_recordings/technician_*.wav
        """
    )

    parser.add_argument(
        'filepath',
        type=str,
        help='Path to WAV file to analyze'
    )

    parser.add_argument(
        '--plot',
        action='store_true',
        help='Show waveform visualization (requires matplotlib)'
    )

    parser.add_argument(
        '--transcribe',
        action='store_true',
        help='Test transcription with Whisper API (requires OpenAI API key)'
    )

    parser.add_argument(
        '--language',
        type=str,
        default='fr',
        help='Language code for transcription (default: fr)'
    )

    args = parser.parse_args()

    # Resolve filepath
    filepath = Path(args.filepath)

    if not filepath.exists():
        print(f"{Colors.RED}❌ Error: File not found: {filepath}{Colors.ENDC}")
        return 1

    # Analyze audio
    success = analyze_audio_file(filepath)

    if not success:
        return 1

    # Optional: plot waveform
    if args.plot:
        plot_waveform(filepath)

    # Optional: test transcription
    if args.transcribe:
        test_transcription(filepath, language=args.language)

    print(f"\n{Colors.GREEN}{Colors.BOLD}Analysis complete!{Colors.ENDC}\n")
    return 0


if __name__ == '__main__':
    sys.exit(main())
