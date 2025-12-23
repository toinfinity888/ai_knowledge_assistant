#!/usr/bin/env python3
"""
Direct Whisper API test using recorded WAV file
Bypasses all buffering/processing to isolate Whisper API behavior

Usage:
    python test_direct_whisper.py
    python test_direct_whisper.py path/to/recording.wav
    python test_direct_whisper.py --no-prompt  # Test without prompt
    python test_direct_whisper.py --language auto  # Auto-detect language
"""
import os
import sys
import glob
import argparse
from openai import OpenAI
from dotenv import load_dotenv

# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def main():
    parser = argparse.ArgumentParser(
        description="Test Whisper API directly with recorded audio file"
    )
    parser.add_argument(
        'filepath',
        type=str,
        nargs='?',
        help='Path to WAV file (default: latest in audio_recordings/)'
    )
    parser.add_argument(
        '--no-prompt',
        action='store_true',
        help='Do not use prompt (test if prompt is too restrictive)'
    )
    parser.add_argument(
        '--language',
        type=str,
        default='fr',
        help='Language code (fr, en, auto, etc.) - use "auto" for auto-detect'
    )
    parser.add_argument(
        '--temperature',
        type=float,
        default=0.0,
        help='Temperature (0.0 = deterministic, 1.0 = creative)'
    )

    args = parser.parse_args()

    # Load environment
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        print(f"{Colors.RED}❌ Error: OPENAI_API_KEY not found in environment{Colors.ENDC}")
        print(f"   Make sure .env file exists with OPENAI_API_KEY=...")
        return 1

    # Determine which file to use
    if args.filepath:
        recording_path = args.filepath
    else:
        # Find latest recording
        recordings = glob.glob("audio_recordings/technician_*.wav")
        if not recordings:
            print(f"{Colors.RED}❌ Error: No recordings found in audio_recordings/{Colors.ENDC}")
            return 1

        # Sort by modification time, get latest
        recordings.sort(key=os.path.getmtime, reverse=True)
        recording_path = recordings[0]
        print(f"{Colors.CYAN}ℹ️  Using latest recording: {recording_path}{Colors.ENDC}")

    if not os.path.exists(recording_path):
        print(f"{Colors.RED}❌ Error: File not found: {recording_path}{Colors.ENDC}")
        return 1

    # File info
    file_size = os.path.getsize(recording_path)
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'Direct Whisper API Test':^80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}\n")

    print(f"{Colors.CYAN}{Colors.BOLD}📋 File Information{Colors.ENDC}")
    print(f"   Path: {recording_path}")
    print(f"   Size: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")

    # Test parameters
    print(f"\n{Colors.CYAN}{Colors.BOLD}🔧 Test Parameters{Colors.ENDC}")
    print(f"   Model: whisper-1")
    print(f"   Language: {args.language if args.language != 'auto' else 'auto-detect'}")
    print(f"   Temperature: {args.temperature}")
    print(f"   Use Prompt: {not args.no_prompt}")

    # Prepare API call
    client = OpenAI(api_key=api_key)

    # Prompt (if not disabled)
    prompt = None
    if not args.no_prompt:
        prompt = """Vous êtes un transcripteur automatique précis.
•	Transcrivez exactement ce qui est dit par les interlocuteurs.
•	Les interlocuteurs sont : un technicien du centre de contrôle (Technicien) et un employé (Employé).
•	Ne jamais inventer de phrases.
•	Si vous n'entendez rien ou si c'est du silence, ne produisez aucun texte.
•	Conservez les noms, chiffres, codes ou termes techniques tels quels.
•	Ne modifiez pas la grammaire ou le vocabulaire d'origine.
•	Limitez la sortie à seulement le contenu audible, sans interprétation ni ajout."""

    # Make API call
    print(f"\n{Colors.YELLOW}⏳ Calling Whisper API...{Colors.ENDC}")

    try:
        with open(recording_path, 'rb') as audio_file:
            import time
            start_time = time.time()

            # Prepare kwargs
            kwargs = {
                'model': 'whisper-1',
                'file': audio_file,
                'response_format': 'verbose_json',
                'temperature': args.temperature
            }

            # Add language if not auto
            if args.language != 'auto':
                kwargs['language'] = args.language

            # Add prompt if not disabled
            if prompt:
                kwargs['prompt'] = prompt

            response = client.audio.transcriptions.create(**kwargs)

            api_duration = time.time() - start_time

        # Success!
        print(f"{Colors.GREEN}✅ API call completed in {api_duration:.2f}s{Colors.ENDC}")

        # Response details
        print(f"\n{Colors.CYAN}{Colors.BOLD}📊 Whisper Response{Colors.ENDC}")
        print(f"   Response Type: {type(response)}")

        # Check for text
        if hasattr(response, 'text'):
            text = response.text
            if text:
                print(f"   Text Length: {len(text)} characters")
                print(f"   {Colors.GREEN}Text Present: YES ✅{Colors.ENDC}")
            else:
                print(f"   {Colors.RED}Text Present: NO (empty string){Colors.ENDC}")
        else:
            print(f"   {Colors.RED}Text Attribute: MISSING ❌{Colors.ENDC}")
            text = None

        # Language
        if hasattr(response, 'language'):
            print(f"   Detected Language: {response.language}")

        # Duration
        if hasattr(response, 'duration'):
            print(f"   Audio Duration: {response.duration:.2f}s")

        # Segments
        if hasattr(response, 'segments') and response.segments:
            print(f"   Segments: {len(response.segments)}")

        # Show transcription
        print(f"\n{Colors.CYAN}{Colors.BOLD}📝 Transcription Result{Colors.ENDC}")
        print(f"{Colors.BOLD}{'─'*80}{Colors.ENDC}")

        if text:
            print(f"{Colors.GREEN}{text}{Colors.ENDC}")
            print(f"{Colors.BOLD}{'─'*80}{Colors.ENDC}")

            # Show first few segments if available
            if hasattr(response, 'segments') and response.segments:
                print(f"\n{Colors.CYAN}📍 Segments (first 5):{Colors.ENDC}")
                for i, seg in enumerate(response.segments[:5]):
                    start = seg.get('start', 0) if isinstance(seg, dict) else getattr(seg, 'start', 0)
                    end = seg.get('end', 0) if isinstance(seg, dict) else getattr(seg, 'end', 0)
                    seg_text = seg.get('text', '') if isinstance(seg, dict) else getattr(seg, 'text', '')

                    print(f"   [{i+1}] {start:.2f}s - {end:.2f}s: {seg_text}")
        else:
            print(f"{Colors.RED}(empty){Colors.ENDC}")
            print(f"{Colors.BOLD}{'─'*80}{Colors.ENDC}")

            # Explain why it might be empty
            print(f"\n{Colors.YELLOW}⚠️  Possible Reasons for Empty Transcription:{Colors.ENDC}")
            print(f"   1. Audio is silent or very quiet")
            print(f"   2. Audio is too noisy/distorted for Whisper to understand")
            print(f"   3. Wrong language specified (try --language auto)")
            print(f"   4. Prompt too restrictive (try --no-prompt)")
            print(f"   5. Audio format issue (check with analyze_recording.py)")

        print(f"\n{Colors.GREEN}{Colors.BOLD}✅ Test Complete!{Colors.ENDC}\n")
        return 0

    except Exception as e:
        print(f"\n{Colors.RED}❌ ERROR: {type(e).__name__}: {e}{Colors.ENDC}")
        import traceback
        print(f"\n{Colors.RED}Stack Trace:{Colors.ENDC}")
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
