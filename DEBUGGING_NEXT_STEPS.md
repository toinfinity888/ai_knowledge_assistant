# Debugging Next Steps - Whisper Returns None Issue

## Current Status

### What Works ✅
1. **Audio Recording** - Technician audio is being recorded to WAV files successfully
2. **Audio Quality** - Latest recording analysis shows:
   - RMS Level: 811.9 (GOOD - Normal speech range)
   - Format: 16kHz, 16-bit, mono ✅
   - No clipping detected ✅
   - Max amplitude: 8316 (normal for mulaw-decoded audio)
3. **Audio Pipeline** - Refactored to buffer-then-resample architecture
4. **RMS Thresholds** - Lowered to 30 for both quality gate and transcription service

### What Doesn't Work ❌
1. **Whisper API Returns None** - Despite good audio quality
2. **No Transcriptions in UI** - Nothing appears in agent interface
3. **User Reports Distortion** - Audio sounds "raspy and stretched"

### Diagnostic Logging Added ✅
Comprehensive logging added to `enhanced_transcription_service.py` that will show:
- Audio buffer size
- Audio format verification (channels, sample rate, bit depth)
- First few audio samples
- RMS levels before sending to Whisper
- API call timing
- Complete API response analysis
- Empty/None detection with suggested causes

## Investigation Steps

### Step 1: Make Test Call and Analyze Logs

**Action:**
1. Make a test phone call to the system
2. Speak clearly in French for 10-15 seconds
3. End the call
4. Check the application logs for Whisper diagnostic messages

**What to Look For:**

#### A. Audio Format Issues
```
🔍 WHISPER DIAGNOSTIC - Audio format:
   Channels: 1 (expected: 1)  ← Should be 1
   Sample rate: 16000 Hz (expected: 16000)  ← Should be 16000
   Sample width: 2 bytes (expected: 2 for 16-bit)  ← Should be 2
```

If any values don't match expectations → **FORMAT PROBLEM**

#### B. Audio Level Issues
```
✅ WHISPER DIAGNOSTIC - Audio level appears NORMAL (RMS=811.9)
```

Or:
```
⚠️ WHISPER DIAGNOSTIC - Audio is VERY QUIET (RMS=45.3)
❌ WHISPER DIAGNOSTIC - Audio appears SILENT (RMS=2.1)
```

If RMS < 100 → **VOLUME PROBLEM**

#### C. API Response Issues
```
🔍 WHISPER DIAGNOSTIC - response.text: 'Bonjour...'  ← Text present = SUCCESS
```

Or:
```
🔍 WHISPER DIAGNOSTIC - response.text: ''  ← Empty = PROBLEM
❌ WHISPER DIAGNOSTIC - response.text is None  ← None = BIG PROBLEM
```

#### D. Exception Issues
```
❌ WHISPER API EXCEPTION: HTTPError: ...
```

### Step 2: Test Direct Transcription

**Create test script:** `test_direct_whisper.py`

```python
#!/usr/bin/env python3
"""
Direct Whisper API test using recorded WAV file
Bypasses all buffering/processing to isolate Whisper API behavior
"""
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Use latest recording
recording_path = "audio_recordings/technician_MZ287d415db5b3a75485d9179aa22a07c4_20251114_195221.wav"

print(f"Testing Whisper API with: {recording_path}")
print("=" * 80)

with open(recording_path, 'rb') as audio_file:
    try:
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="fr",
            response_format="verbose_json",
            temperature=0.0
        )

        print(f"✅ SUCCESS!")
        print(f"Text: {response.text}")
        print(f"Language: {response.language}")
        print(f"Duration: {response.duration}s")

        if hasattr(response, 'segments'):
            print(f"Segments: {len(response.segments)}")
            for i, seg in enumerate(response.segments[:3]):
                print(f"  [{i}] {seg.get('start', 0):.2f}s - {seg.get('end', 0):.2f}s: {seg.get('text', '')}")

    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
```

**Run:**
```bash
python test_direct_whisper.py
```

**Expected Results:**

If **SUCCESS** → Whisper API works fine, problem is in pipeline
If **FAILURE** → Audio file itself has issues

### Step 3: Compare Recording with Live Stream

**Check if recorded file matches what Whisper receives:**

Add temporary file saving in `enhanced_transcription_service.py` around line 268:

```python
# Before calling Whisper
wav_buffer = self._create_wav_buffer(combined_audio)

# TEMP: Save what we're sending to Whisper
import tempfile
temp_path = f"/tmp/whisper_test_{session_id}_{int(current_timestamp)}.wav"
with open(temp_path, 'wb') as f:
    wav_buffer.seek(0)
    f.write(wav_buffer.read())
    wav_buffer.seek(0)
logger.info(f"🔍 TEMP: Saved audio to {temp_path} for debugging")

# Continue with Whisper call
transcription_result = await self._transcribe_with_whisper(...)
```

Then:
1. Make test call
2. Check `/tmp/whisper_test_*.wav` files
3. Analyze with `analyze_recording.py`
4. Compare with main recording in `audio_recordings/`

If files are **identical** → Recording accurately represents what Whisper sees
If files are **different** → Problem in buffering/concatenation

### Step 4: Test Audio Playback

**Listen to recorded audio directly:**

```bash
# macOS (using afplay)
afplay audio_recordings/technician_MZ287d415db5b3a75485d9179aa22a07c4_20251114_195221.wav

# Or use VLC, QuickTime, etc.
open audio_recordings/technician_MZ287d415db5b3a75485d9179aa22a07c4_20251114_195221.wav
```

**Listen for:**
- Does speech sound intelligible?
- Is it stretched/slowed down?
- Is it raspy/distorted?
- Are there artifacts at segment boundaries?
- Does it sound like telephone quality (mulaw) or worse?

**Expected:**
- Telephone quality (8-bit mulaw decoded to 16-bit)
- Slight "telephone" character is normal
- Speech should be intelligible
- No obvious stretching or artifacts

### Step 5: Check Transcription Service Flow

**Verify complete flow from audio → UI:**

1. **Audio reaches transcription service?**
   - Check logs for: `[session_id] Combined X chunks = Y bytes`

2. **Speaker detection working?**
   - Check logs for: `Using explicit speaker: technician`

3. **should_process_segment returns True?**
   - Check logs for: `✅ Speaker technician WILL be processed`

4. **Whisper called?**
   - Check logs for: `🎯 Calling Whisper API with model=whisper-1`

5. **Whisper returns text?**
   - Check logs for: `🔍 WHISPER DIAGNOSTIC - response.text: '...'`

6. **Transcription sent to agents?**
   - Check logs for: `Transcribed X.XXs from Technicien`

7. **WebSocket broadcast?**
   - Check logs for: `Broadcasting to WebSocket...`

### Step 6: Test with Known Good Audio

**Create synthetic test audio:**

```python
#!/usr/bin/env python3
"""
Create synthetic speech audio for testing
Uses pyttsx3 or gTTS to generate known speech
"""
import wave
import numpy as np

# Generate 1 second of 440Hz sine wave (A note)
sample_rate = 16000
duration = 1.0
frequency = 440.0

t = np.linspace(0, duration, int(sample_rate * duration))
audio = np.sin(2 * np.pi * frequency * t)

# Scale to 16-bit range
audio_16bit = (audio * 8000).astype(np.int16)

# Save as WAV
with wave.open("test_sine_wave.wav", 'wb') as wav:
    wav.setnchannels(1)
    wav.setsampwidth(2)
    wav.setframerate(sample_rate)
    wav.writeframes(audio_16bit.tobytes())

print("Created test_sine_wave.wav")
```

Or use text-to-speech:

```python
from gtts import gTTS
import os

text = "Bonjour, ceci est un test de transcription"
tts = gTTS(text=text, lang='fr')
tts.save("test_speech_fr.mp3")

# Convert to 16kHz WAV
os.system("ffmpeg -i test_speech_fr.mp3 -ar 16000 -ac 1 test_speech_fr.wav")
```

Then test:
```bash
python test_direct_whisper.py test_speech_fr.wav
```

If **SUCCESS** → Whisper API works, problem is in recorded audio quality
If **FAILURE** → API key or network issue

## Possible Root Causes

### Cause 1: Whisper Prompt Too Restrictive

**Current prompt:**
```python
prompt = """Vous êtes un transcripteur automatique précis.
...
•  Si vous n'entendez rien ou si c'est du silence, ne produisez aucun texte.
...
"""
```

**Issue:** Prompt tells Whisper "if you don't hear anything, produce no text"
This might cause Whisper to return empty string for noisy/unclear audio

**Test:** Try without prompt:
```python
response = client.audio.transcriptions.create(
    model="whisper-1",
    file=audio_buffer,
    language="fr",
    response_format="verbose_json",
    # prompt=prompt,  # COMMENT OUT
    temperature=0.0
)
```

### Cause 2: Audio Buffering Mismatch

**Current flow:**
1. Twilio sends ~20ms chunks (50 per second)
2. We buffer 8kHz audio for 1 second
3. Resample entire 1-second buffer to 16kHz once
4. Send to transcription service
5. Transcription service expects small chunks for VAD

**Issue:** Transcription service was designed for small chunks but now receives 1-second chunks

**Test:** Bypass transcription service VAD buffering:
```python
# In twilio_audio_service.py, send directly to Whisper
# Skip the transcription_service.process_audio_stream() intermediate step
```

### Cause 3: Mulaw Decoding Artifact

**Current flow:**
```
mulaw (8-bit) → PCM (16-bit) → resample (8kHz → 16kHz)
```

**Issue:** Mulaw decoding produces ~8159 max amplitude, not 32767
When Whisper expects full 16-bit range, quiet audio might be rejected

**Test:** Amplify audio before sending to Whisper:
```python
import numpy as np

# After creating wav_buffer
wav_buffer.seek(0)
audio_data = wav_buffer.read()

# Parse PCM samples
samples = np.frombuffer(audio_data[44:], dtype=np.int16)  # Skip WAV header

# Amplify by 2x (careful not to clip!)
amplified = np.clip(samples * 2, -32767, 32767).astype(np.int16)

# Create new WAV buffer with amplified audio
# ... (recreate WAV file with amplified data)
```

### Cause 4: Language Detection Failing

**Issue:** Whisper detects wrong language, transcribes incorrectly, returns empty

**Test:** Try language="auto" or different languages:
```python
response = client.audio.transcriptions.create(
    model="whisper-1",
    file=audio_buffer,
    language=None,  # Auto-detect
    response_format="verbose_json",
)
```

Check response.language to see what Whisper detected

### Cause 5: Audio Too Short

**Issue:** 1-second chunks might be too short for Whisper

**Test:** Buffer longer before transcribing:
```python
# In enhanced_transcription_service.py
self.buffer_duration = 5.0  # Increase from 3.0 to 5.0 seconds
```

## Expected Outcomes

### Best Case
- Whisper diagnostic logs show normal audio format and levels
- Direct file test transcribes successfully
- Problem is in live pipeline buffering/VAD
- **Fix:** Adjust buffering logic or bypass transcription service VAD

### Medium Case
- Audio format is correct but RMS too low
- Direct file test succeeds after amplification
- **Fix:** Add gain/amplification before Whisper

### Worst Case
- Audio is truly distorted (not just mulaw characteristics)
- Direct file test fails
- Playback sounds unintelligible
- **Fix:** Debug audio pipeline stages 7-17, check for buffer corruption

## Testing Checklist

- [ ] Make test call and check diagnostic logs
- [ ] Run `test_direct_whisper.py` on recorded file
- [ ] Listen to recorded audio playback
- [ ] Compare `/tmp/whisper_test_*.wav` with main recording
- [ ] Test without Whisper prompt
- [ ] Test with language="auto"
- [ ] Test with amplified audio
- [ ] Test with longer buffer duration (5s instead of 1s)
- [ ] Create synthetic test audio and verify Whisper works
- [ ] Trace complete flow from Twilio → UI

## Quick Commands

```bash
# Analyze latest recording
python analyze_recording.py audio_recordings/technician_*.wav

# Test direct Whisper API
python test_direct_whisper.py

# Check application logs for Whisper diagnostics
grep "WHISPER DIAGNOSTIC" logs.txt

# Listen to recording
afplay audio_recordings/technician_*.wav

# Monitor live logs during test call
tail -f logs.txt | grep -E "(WHISPER|STAGE)"
```

## Summary

The diagnostic logging is now in place. The next step is to:

1. **Make a test call** and examine the Whisper diagnostic logs
2. **Test direct transcription** of recorded file to isolate if issue is in pipeline or Whisper
3. **Listen to audio** to verify if distortion is real or perceived
4. Based on findings, apply appropriate fix from possible root causes

The comprehensive logging will reveal exactly where the problem is occurring and what fix is needed.
