# Audio Recording Guide

This guide explains how to use the audio recording feature to capture and analyze audio from Twilio phone calls (technician audio).

## Overview

The system can automatically record all audio received from technician phone calls to WAV files for debugging and quality analysis. This is helpful for:

- Analyzing audio quality issues
- Debugging transcription problems
- Reviewing RMS levels and audio characteristics
- Testing different microphones and phone setups
- Creating test datasets

## Feature Status

**Recording is ENABLED by default** for all technician audio from Twilio phone calls.

## Recording Location

All recordings are saved to:
```
/Users/saraevsviatoslav/Documents/ai_knowledge_assistant/audio_recordings/
```

## File Naming Convention

Files are named using this pattern:
```
{speaker}_{session_id}_{timestamp}.wav
```

**Example:**
```
technician_MZabcdef123456_20251110_143052.wav
```

Where:
- `speaker`: "technician" or "agent"
- `session_id`: Twilio session identifier
- `timestamp`: UTC timestamp in format YYYYMMDD_HHMMSS

## Audio Format Specifications

All recordings are saved in the following format:

- **Format:** WAV (uncompressed PCM)
- **Sample Rate:** 16,000 Hz (16kHz)
- **Channels:** 1 (Mono)
- **Bit Depth:** 16-bit
- **Byte Order:** Little-endian

This format is compatible with:
- Most audio analysis tools (Audacity, Adobe Audition, etc.)
- Python audio libraries (librosa, soundfile, wave, pydub)
- Whisper API (same format used for transcription)

## How It Works

### 1. Stream Initialization (Stage 5)

When a Twilio phone call starts:
```
📼 Created recording file: audio_recordings/technician_MZ123_20251110_143052.wav
✅ STAGE 5: Technician stream initialized
📼 STAGE 5: Recording enabled for session MZ123
```

### 2. Audio Writing (Stage 11)

Every audio chunk is written to the WAV file immediately after processing:
```
🔧 STAGE 7: _process_audio_chunk_sync called
✅ STAGE 8: Base64 decoded → 180 bytes mulaw
✅ STAGE 9: Mulaw decoded → 360 bytes PCM (8kHz, 16-bit)
✅ STAGE 10: Resampled to 16kHz → 720 bytes
📊 STAGE 11: Audio characteristics - RMS=850.3
📼 Wrote 720 bytes to recording file
```

### 3. Stream Cleanup

When the call ends, the WAV file is closed and statistics are logged:
```
📼 Closed recording for session MZ123
   Duration: 45.32 seconds
   Frames: 725120
   File: audio_recordings/technician_MZ123_20251110_143052.wav
```

## Analyzing Recorded Audio

### Using Python (wave module)

```python
import wave

# Open the recorded file
with wave.open('audio_recordings/technician_MZ123_20251110_143052.wav', 'rb') as wav:
    print(f"Channels: {wav.getnchannels()}")
    print(f"Sample Rate: {wav.getframerate()} Hz")
    print(f"Bit Depth: {wav.getsampwidth() * 8} bits")
    print(f"Duration: {wav.getnframes() / wav.getframerate():.2f} seconds")

    # Read audio data
    audio_data = wav.readframes(wav.getnframes())
```

### Using Python (librosa)

```python
import librosa
import numpy as np

# Load audio file
audio, sr = librosa.load('audio_recordings/technician_MZ123_20251110_143052.wav', sr=16000)

print(f"Sample rate: {sr} Hz")
print(f"Duration: {len(audio) / sr:.2f} seconds")
print(f"RMS level: {np.sqrt(np.mean(audio**2)):.2f}")

# Visualize waveform
import matplotlib.pyplot as plt
plt.figure(figsize=(14, 4))
plt.plot(audio)
plt.title('Waveform')
plt.xlabel('Sample')
plt.ylabel('Amplitude')
plt.show()
```

### Using Audacity

1. Open Audacity
2. File → Open → Select WAV file
3. Analyze audio quality, noise, RMS levels
4. Use effects to test audio processing

### Calculate RMS Levels

```python
import wave
import struct
import numpy as np

with wave.open('audio_recordings/technician_MZ123_20251110_143052.wav', 'rb') as wav:
    frames = wav.readframes(wav.getnframes())
    samples = struct.unpack(f'{len(frames)//2}h', frames)

    # Calculate RMS (same formula as in the code)
    rms = np.sqrt(np.mean(np.square(samples)))
    print(f"Average RMS: {rms:.1f}")

    # RMS thresholds for reference:
    # < 100 = Too quiet for technician
    # 500-2000 = Normal speech
    # > 5000 = Clipping/too loud
```

### Send to Whisper API for Testing

```python
from openai import OpenAI

client = OpenAI()

with open('audio_recordings/technician_MZ123_20251110_143052.wav', 'rb') as audio_file:
    transcription = client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
        language="fr"  # or "en" depending on your use case
    )
    print(transcription.text)
```

## Disabling Recording

To disable audio recording, modify the service initialization in your configuration:

```python
# In app/services/twilio_audio_service.py or wherever service is initialized
twilio_service = TwilioAudioService(
    account_sid=settings.account_sid,
    auth_token=settings.auth_token,
    phone_number=settings.phone_number,
    enable_recording=False  # Disable recording
)
```

Or update the singleton getter:

```python
# In get_twilio_service() function
_twilio_service = TwilioAudioService(
    account_sid=settings.account_sid,
    auth_token=settings.auth_token,
    phone_number=settings.phone_number,
    enable_recording=False  # Add this parameter
)
```

## Storage Considerations

### File Sizes

Approximate file sizes for recordings:
- 1 minute of audio: ~1.9 MB (16kHz, 16-bit, mono)
- 5 minutes: ~9.5 MB
- 10 minutes: ~19 MB
- 1 hour: ~115 MB

### Disk Space Management

The `audio_recordings/` directory will grow over time. To manage disk space:

#### 1. Delete old recordings manually:
```bash
cd /Users/saraevsviatoslav/Documents/ai_knowledge_assistant/audio_recordings
rm technician_*.wav  # Delete all recordings
rm technician_*_20251110_*.wav  # Delete recordings from specific date
```

#### 2. Automatic cleanup script (optional):
```python
# cleanup_old_recordings.py
import os
from pathlib import Path
from datetime import datetime, timedelta

recordings_dir = Path("audio_recordings")
retention_days = 7  # Keep recordings for 7 days

cutoff_date = datetime.now() - timedelta(days=retention_days)

for file in recordings_dir.glob("*.wav"):
    file_time = datetime.fromtimestamp(file.stat().st_mtime)
    if file_time < cutoff_date:
        print(f"Deleting old recording: {file.name}")
        file.unlink()
```

#### 3. Compress old recordings:
```bash
# Install sox if not installed: brew install sox
cd audio_recordings
for file in *.wav; do
    sox "$file" "${file%.wav}.flac"  # Convert to FLAC (50% smaller)
    rm "$file"  # Delete original WAV
done
```

## Logs Related to Recording

Look for these log messages:

### Success Messages:
- ✅ `Audio recording ENABLED - files will be saved to: ...` (startup)
- 📼 `Created recording file: ...` (stream start)
- 📼 `Wrote XXX bytes to recording file` (debug, every chunk)
- 📼 `Closed recording for session XXX` (stream end)

### Error Messages:
- ❌ `Failed to create WAV file for XXX: ...` (file creation failed)
- ❌ `Error writing to WAV file: ...` (write error during stream)
- ❌ `Error closing WAV file for XXX: ...` (cleanup error)

## Troubleshooting

### Problem: No recordings created

**Check:**
1. Verify recording is enabled in logs: `Audio recording ENABLED`
2. Check directory exists: `ls -la audio_recordings/`
3. Check directory permissions: `ls -ld audio_recordings/`
4. Verify call actually started (check Stage 4-5 logs)

**Solution:**
```bash
# Create directory manually if needed
mkdir -p audio_recordings
chmod 755 audio_recordings
```

### Problem: Empty or very short recordings

**Check:**
1. Call duration (was call answered and held?)
2. Audio stages 6-11 in logs (is audio actually being received?)
3. Twilio call status (is audio streaming?)

**Solution:**
- Make a longer test call
- Verify Twilio is sending audio (check Stage 6 frequency)
- Check if call was disconnected early

### Problem: Recording file corrupted

**Check:**
1. Was WAV file closed properly? (look for "Closed recording" message)
2. Were there write errors during streaming?
3. Was process killed before cleanup?

**Solution:**
- Always end calls cleanly (don't kill process during active call)
- Check error logs for write failures
- Try opening with: `ffmpeg -i corrupted.wav -c copy fixed.wav`

### Problem: High disk usage

**Solution:**
1. Delete old test recordings
2. Implement automatic cleanup (see Storage Considerations)
3. Disable recording if not actively debugging:
   ```python
   enable_recording=False
   ```

## Best Practices

1. **During Development/Testing:**
   - Keep recording enabled to capture issues
   - Review recordings when transcriptions fail
   - Analyze RMS levels to tune thresholds

2. **In Production:**
   - Consider disabling if not needed (saves disk space)
   - Enable only for specific debugging sessions
   - Implement automatic cleanup of old recordings
   - Monitor disk space usage

3. **For Debugging:**
   - Make test calls with known speech content
   - Record in quiet vs noisy environments
   - Test different phones/microphones
   - Compare RMS levels across recordings

4. **Privacy Considerations:**
   - Recordings contain actual customer audio
   - Store securely and delete when no longer needed
   - Consider data protection regulations (GDPR, etc.)
   - Document retention policy

## Example Debugging Workflow

### Scenario: Technician transcriptions are empty

**Step 1:** Make a test call and speak clearly

**Step 2:** Check the logs for the recording filename:
```
📼 Created recording file: audio_recordings/technician_MZ123_20251110_143052.wav
```

**Step 3:** After call ends, verify file was created:
```bash
ls -lh audio_recordings/technician_MZ123_20251110_143052.wav
```

**Step 4:** Analyze the audio:
```python
import wave
import struct
import numpy as np

with wave.open('audio_recordings/technician_MZ123_20251110_143052.wav', 'rb') as wav:
    frames = wav.readframes(wav.getnframes())
    samples = struct.unpack(f'{len(frames)//2}h', frames)
    rms = np.sqrt(np.mean(np.square(samples)))

    print(f"Duration: {wav.getnframes() / 16000:.2f}s")
    print(f"RMS: {rms:.1f}")
    print(f"Status: {'QUIET' if rms < 100 else 'NORMAL' if rms < 5000 else 'LOUD'}")
```

**Step 5:** Test transcription manually:
```python
from openai import OpenAI

client = OpenAI()
with open('audio_recordings/technician_MZ123_20251110_143052.wav', 'rb') as f:
    result = client.audio.transcriptions.create(
        model="whisper-1",
        file=f,
        language="fr"
    )
    print(f"Transcription: {result.text}")
```

**Step 6:** Based on results:
- If RMS < 100: Audio too quiet, ask technician to speak louder
- If transcription empty: Possible language mismatch or too much noise
- If transcription works manually: Check pipeline stages 16-19
- If file is too short: Call ended early, check connection

## Additional Tools

### FFmpeg Commands

```bash
# Get audio info
ffmpeg -i technician_MZ123.wav

# Convert to different format
ffmpeg -i technician_MZ123.wav -ar 8000 output_8khz.wav

# Extract 10 seconds starting at 5 seconds
ffmpeg -i technician_MZ123.wav -ss 5 -t 10 segment.wav

# Increase volume (if too quiet)
ffmpeg -i technician_MZ123.wav -af "volume=2.0" louder.wav

# Reduce noise (requires afftdn filter)
ffmpeg -i technician_MZ123.wav -af "afftdn" denoised.wav
```

### SoX Commands

```bash
# Get detailed stats
sox technician_MZ123.wav -n stat

# Show spectrogram
sox technician_MZ123.wav -n spectrogram

# Normalize audio
sox technician_MZ123.wav normalized.wav norm

# Trim silence from beginning/end
sox technician_MZ123.wav trimmed.wav silence 1 0.1 1% reverse silence 1 0.1 1% reverse
```

## Future Enhancements

Possible improvements to the recording system:

1. **Metadata files:** Save JSON metadata alongside WAV files with session info, RMS stats, timestamps
2. **Selective recording:** Only record when RMS is above threshold (save space)
3. **Cloud storage:** Upload recordings to S3/Cloud Storage automatically
4. **Recording index:** Database to track all recordings with searchable metadata
5. **Web UI:** Interface to browse, play, and analyze recordings
6. **Auto-transcription comparison:** Automatically compare live transcription vs recording analysis
7. **Agent recording:** Also record agent audio from browser (currently only technician)

## Summary

- ✅ Recording is enabled by default
- 📂 Files saved to `audio_recordings/`
- 🎵 Format: 16kHz, 16-bit, mono WAV
- 📊 Use for debugging RMS levels, transcription issues, audio quality
- 🗑️ Remember to clean up old recordings periodically
- 🔒 Consider privacy implications in production
