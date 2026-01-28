#!/usr/bin/env python3
"""
Quick test to verify Deepgram can transcribe audio
"""
import struct
import time
from deepgram import DeepgramClient
from deepgram.core.events import EventType

# Generate simple sine wave test audio (440 Hz tone)
def generate_test_audio(duration_sec=1, sample_rate=8000):
    """Generate a simple sine wave as PCM audio"""
    import math
    samples = []
    for i in range(int(duration_sec * sample_rate)):
        # 440 Hz sine wave
        value = int(32767 * 0.5 * math.sin(2 * math.pi * 440 * i / sample_rate))
        samples.append(value)

    # Pack as PCM Int16
    return struct.pack(f'{len(samples)}h', *samples)

def test_deepgram():
    api_key = "8a15ec5e512303797a079b6b28ac268c5f59d0fb"

    print("🔧 Creating Deepgram client...")
    client = DeepgramClient(api_key=api_key)

    print("🔧 Creating connection...")
    context_manager = client.listen.v1.connect(
        model='nova-2',
        language='en',
        encoding='linear16',
        sample_rate='8000',
        channels='1',
        interim_results='false'
    )

    connection = context_manager.__enter__()

    # Track if we got any response
    got_response = False
    transcripts = []

    def on_message(message):
        nonlocal got_response, transcripts
        got_response = True
        print(f"📨 Got message: type={getattr(message, 'type', 'Unknown')}")
        if hasattr(message, 'channel'):
            channel = message.channel
            if hasattr(channel, 'alternatives') and channel.alternatives:
                alt = channel.alternatives[0]
                transcript = getattr(alt, 'transcript', '')
                confidence = getattr(alt, 'confidence', 0.0)
                print(f"   Transcript: '{transcript}' (conf: {confidence})")
                transcripts.append(transcript)

    def on_open(_):
        print("✅ Connection opened")

    def on_close(_):
        print("🔌 Connection closed")

    def on_error(error):
        print(f"❌ Error: {error}")

    connection.on(EventType.OPEN, on_open)
    connection.on(EventType.MESSAGE, on_message)
    connection.on(EventType.CLOSE, on_close)
    connection.on(EventType.ERROR, on_error)

    print("🎧 Starting listening...")
    import threading
    listen_thread = threading.Thread(target=connection.start_listening, daemon=True)
    listen_thread.start()

    # Wait for connection
    time.sleep(1)

    # Send test audio (just silence/tone - we're testing if Deepgram RESPONDS)
    print("📤 Sending test audio...")
    test_audio = generate_test_audio(duration_sec=2)
    connection.send_media(test_audio)

    # Also send actual silence to trigger a response
    silence = b'\x00\x00' * 8000  # 1 second of silence
    connection.send_media(silence)

    # Wait for response
    print("⏳ Waiting for response...")
    time.sleep(3)

    # Close
    print(f"\n📊 Results:")
    print(f"   Got response: {got_response}")
    print(f"   Transcripts: {transcripts}")

    context_manager.__exit__(None, None, None)

    return got_response

if __name__ == '__main__':
    test_deepgram()
