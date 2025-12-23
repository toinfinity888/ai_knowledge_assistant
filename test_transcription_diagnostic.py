"""
Diagnostic script to test transcription service
This script helps identify where transcription is failing
"""
import asyncio
import logging
import sys
import os
import wave
import struct

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

async def test_transcription_service():
    """Test the enhanced transcription service with sample audio"""
    try:
        from app.services.enhanced_transcription_service import get_enhanced_transcription_service

        logger.info("=" * 70)
        logger.info("TRANSCRIPTION SERVICE DIAGNOSTIC TEST")
        logger.info("=" * 70)

        # Get service
        service = get_enhanced_transcription_service()
        logger.info(f"✓ Got transcription service")
        logger.info(f"  - VAD bypass: {service.bypass_vad}")
        logger.info(f"  - Min bytes (8kHz): {service.min_bytes_8k}")
        logger.info(f"  - Min bytes (16kHz): {service.min_bytes_16k}")
        logger.info(f"  - Buffer duration: {service.buffer_duration}s")
        logger.info(f"  - Max buffer duration: {service.max_buffer_duration}s")

        # Create test audio (3 seconds of 8kHz silence with some noise)
        sample_rate = 8000
        duration = 3.0  # seconds
        num_samples = int(sample_rate * duration)

        logger.info(f"\n📊 Creating test audio:")
        logger.info(f"  - Sample rate: {sample_rate} Hz")
        logger.info(f"  - Duration: {duration} seconds")
        logger.info(f"  - Num samples: {num_samples}")

        # Create audio with some noise (not pure silence)
        import random
        samples = [random.randint(-100, 100) for _ in range(num_samples)]
        audio_data = struct.pack(f'{num_samples}h', *samples)

        bytes_per_sample = 2  # 16-bit
        total_bytes = len(audio_data)
        logger.info(f"  - Total bytes: {total_bytes}")
        logger.info(f"  - Expected bytes for 3s: {sample_rate * bytes_per_sample * duration}")

        # Test 1: Check if we can create WAV buffer
        logger.info(f"\n[TEST 1] Creating WAV buffer...")
        wav_buffer = service._create_wav_buffer(audio_data, sample_rate=sample_rate)
        logger.info(f"✓ WAV buffer created: {wav_buffer.tell()} bytes")

        # Test 2: Process audio in small chunks (simulate Twilio)
        logger.info(f"\n[TEST 2] Processing audio in chunks...")
        session_id = "test-session-001"
        chunk_size = 640  # 640 bytes = 320 samples = 40ms @ 8kHz (typical Twilio chunk)
        chunks_sent = 0
        transcription_received = False

        # Initialize session
        service.initialize_session(
            session_id=session_id,
            technician_id="tech-001",
            technician_name="Test Technician"
        )
        logger.info(f"✓ Session initialized: {session_id}")

        # Send chunks
        for i in range(0, total_bytes, chunk_size):
            chunk = audio_data[i:i+chunk_size]
            timestamp = (i / bytes_per_sample) / sample_rate

            logger.info(f"  Sending chunk {chunks_sent + 1}: {len(chunk)} bytes at {timestamp:.3f}s")

            result = await service.process_audio_stream(
                session_id=session_id,
                audio_chunk=chunk,
                timestamp=timestamp,
                speaker='technician',
                sample_rate=sample_rate
            )

            chunks_sent += 1

            if result:
                transcription_received = True
                logger.info(f"✓ ✓ ✓ TRANSCRIPTION RECEIVED!")
                logger.info(f"  Text: '{result.get('text', 'NO TEXT')}'")
                logger.info(f"  Speaker: {result.get('speaker_name', 'UNKNOWN')}")
                logger.info(f"  Duration: {result.get('duration', 0):.2f}s")
                break

        logger.info(f"\n📊 Test Results:")
        logger.info(f"  - Chunks sent: {chunks_sent}")
        logger.info(f"  - Total bytes sent: {chunks_sent * chunk_size}")
        logger.info(f"  - Transcription received: {transcription_received}")

        # Check buffer state
        buffer_key = f"{session_id}_technician"
        if buffer_key in service.audio_buffers:
            buffer = service.audio_buffers[buffer_key]
            buffer_bytes = sum(len(chunk) for chunk in buffer['chunks'])
            logger.info(f"\n📦 Buffer state:")
            logger.info(f"  - Chunks in buffer: {len(buffer['chunks'])}")
            logger.info(f"  - Bytes in buffer: {buffer_bytes}")
            logger.info(f"  - Duration: {buffer.get('total_duration', 0):.2f}s")
            logger.info(f"  - Min bytes threshold: {service.min_bytes_8k}")
            logger.info(f"  - Threshold reached: {buffer_bytes >= service.min_bytes_8k}")
        else:
            logger.warning(f"⚠️  No buffer found for {buffer_key}")

        # Test 3: Test Whisper API directly
        logger.info(f"\n[TEST 3] Testing Whisper API directly...")
        try:
            # Create a longer test audio with actual speech-like patterns
            logger.info(f"  Creating speech-like audio (5 seconds)...")
            speech_duration = 5.0
            speech_samples = int(sample_rate * speech_duration)

            # Generate audio with varying amplitude (simulates speech)
            import math
            speech_data = []
            for i in range(speech_samples):
                # Mix of frequencies to simulate speech
                freq1 = 200 + 100 * math.sin(i / 100)  # Fundamental
                freq2 = 400 + 200 * math.sin(i / 200)  # Harmonic
                amplitude = 1000 + 500 * math.sin(i / 1000)  # Varying amplitude
                sample = int(amplitude * (math.sin(2 * math.pi * freq1 * i / sample_rate) +
                                         0.5 * math.sin(2 * math.pi * freq2 * i / sample_rate)))
                speech_data.append(max(-32767, min(32767, sample)))

            speech_audio = struct.pack(f'{speech_samples}h', *speech_data)
            logger.info(f"  - Speech audio created: {len(speech_audio)} bytes")

            # Create WAV and test Whisper
            wav_buffer = service._create_wav_buffer(speech_audio, sample_rate=sample_rate)
            logger.info(f"  - WAV buffer created: {wav_buffer.tell()} bytes")

            logger.info(f"  - Calling Whisper API...")
            whisper_result = await service._transcribe_with_whisper(wav_buffer, language='fr')

            if whisper_result:
                logger.info(f"✓ ✓ ✓ WHISPER API RESPONDED!")
                logger.info(f"  Text: '{whisper_result.get('text', 'NO TEXT')}'")
                logger.info(f"  Language: {whisper_result.get('language', 'UNKNOWN')}")
                logger.info(f"  Duration: {whisper_result.get('duration', 0):.2f}s")
            else:
                logger.error(f"❌ Whisper API returned None")

        except Exception as e:
            logger.error(f"❌ Whisper API test failed: {e}", exc_info=True)

        logger.info(f"\n" + "=" * 70)
        logger.info(f"DIAGNOSTIC TEST COMPLETE")
        logger.info(f"=" * 70)

    except Exception as e:
        logger.error(f"❌ Diagnostic test failed: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(test_transcription_service())
