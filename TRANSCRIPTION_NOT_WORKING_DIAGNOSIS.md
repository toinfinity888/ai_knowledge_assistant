# Transcription Not Working - Real Diagnosis

## Problem

Even with fixes applied, technician transcriptions are NOT appearing. The logs show:
```
STAGE 19: CALLING WHISPER API
STAGE 19: Whisper API returned
❌ STAGE 19 FAILED: Transcription returned None
```

## Root Cause Analysis

### The Misleading Log Message

The log "CALLING WHISPER API" is **misleading**. Looking at the code:

```python
# In twilio_audio_service.py:388
logger.info(f"[{session_id}] 🚀 STAGE 19: CALLING WHISPER API")

result = await transcription_service.process_audio_stream(
    session_id=session_id,
    audio_chunk=combined_16k,
    timestamp=timestamp
)

logger.info(f"[{session_id}] 📥 STAGE 19: Whisper API returned")
```

This says "CALLING WHISPER API" but it's actually calling `process_audio_stream()` which:
1. **Buffers the audio** (doesn't immediately transcribe)
2. Waits for **VAD to detect speech end**
3. Only calls Whisper when **speech segment is complete**
4. Returns None while buffering

### Why Whisper Is Never Called

The `process_audio_stream` method has multiple exit points that return None WITHOUT calling Whisper:

#### Exit 1: Initial 0.5s Skip (Line 85-87)
```python
if time_since_start < 0.5:
    logger.debug(f"[{buffer_key}] ⏭️ Skipping initial 0.5s period")
    return None  # ← Whisper NOT called
```

#### Exit 2: Waiting for Speech RMS Check (Line 101-103)
```python
if chunk_rms < min_rms_threshold:
    logger.debug(f"[{buffer_key}] 💤 Still waiting for speech (RMS={chunk_rms:.1f} < {min_rms_threshold})")
    return None  # ← Whisper NOT called
```

**This is likely the issue!** The RMS threshold is 30 (we lowered it), but if audio is still below that, it never starts buffering.

#### Exit 3: Still Buffering (Line 187-189)
```python
else:
    logger.debug(f"[{buffer_key}] ⏳ Buffering: {buffer['total_duration']:.2f}s, VAD status: {reason}")
    return None  # ← Whisper NOT called, still buffering
```

#### Exit 4: Segment Too Short (Line 176-185)
```python
if buffer['total_duration'] < self.diarization_service.min_speech_duration:
    logger.debug(f"[{buffer_key}] ⏭️ Segment too short")
    return None  # ← Whisper NOT called, segment discarded
```

#### Exit 5: RMS Too Low (Line 146-158)
```python
if reason.startswith("rms_too_low"):
    logger.warning(f"[{buffer_key}] ⏭️ Segment rejected due to low RMS")
    return None  # ← Whisper NOT called
```

### The Missing Diagnostic Logs

You should see logs like:
- `💤 Still waiting for speech (RMS=XXX < 30)`
- `⏳ Buffering: X.XXs, VAD status: ...`
- `⏭️ Segment too short`
- `🔍 WHISPER DIAGNOSTIC - ...` (when Whisper is actually called)

**But you don't see these!** This means:
1. Either logging level is too high (DEBUG messages hidden)
2. Or the code is taking a different path

## Solutions

### Solution 1: Enable DEBUG Logging (IMMEDIATE)

The critical logs are at DEBUG level but we need INFO level. Change logging statements:

**File:** `app/services/enhanced_transcription_service.py`

Change all `logger.debug()` to `logger.info()` for visibility:

```python
# Line 86 - Change from debug to info
logger.info(f"[{buffer_key}] ⏭️ Skipping initial 0.5s period ({time_since_start:.3f}s elapsed)")

# Line 102 - Change from debug to info
logger.info(f"[{buffer_key}] 💤 Still waiting for speech (RMS={chunk_rms:.1f} < {min_rms_threshold})")

# Line 115 - Change from debug to info
logger.info(f"[{buffer_key}] 📦 Added chunk {len(audio_chunk)} bytes to buffer (total chunks: {len(buffer['chunks'])})")

# Line 122 - Change from debug to info
logger.info(f"[{buffer_key}] ⏱️ Buffer duration: {buffer['total_duration']:.2f}s")

# Line 176 - Change from debug to info
logger.info(f"[{buffer_key}] ⏭️ Segment too short ({buffer['total_duration']:.2f}s < {self.diarization_service.min_speech_duration}s) - discarding")

# Line 187 - Change from debug to info
logger.info(f"[{buffer_key}] ⏳ Buffering: {buffer['total_duration']:.2f}s, VAD status: {reason}")
```

### Solution 2: Lower RMS Threshold Even More

Current threshold is 30. For mulaw-decoded audio with max ~8316, this might still be too high.

**File:** `app/services/speaker_diarization_service.py`

```python
# Line 44 - Lower from 30 to 10
self.min_segment_rms_technician = 10.0  # Was 30.0
```

### Solution 3: Reduce Minimum Speech Duration

Current minimum is probably 1.0s. If user says quick words, they might be discarded.

**File:** Check `app/services/speaker_diarization_service.py`

```python
# Find min_speech_duration and reduce it
self.min_speech_duration = 0.5  # Was probably 1.0
```

### Solution 4: Force Immediate Transcription (TESTING ONLY)

To test if Whisper actually works, bypass all buffering/VAD:

**File:** `app/services/twilio_audio_service.py`

Add after line 399:

```python
# TEMPORARY TEST: Call Whisper directly
import io
import wave

wav_buffer = io.BytesIO()
with wave.open(wav_buffer, 'wb') as wav_file:
    wav_file.setnchannels(1)
    wav_file.setsampwidth(2)
    wav_file.setframerate(16000)
    wav_file.writeframes(combined_16k)

wav_buffer.seek(0)
wav_buffer.name = "test.wav"

from openai import OpenAI
client = OpenAI()

try:
    logger.info(f"[{session_id}] 🧪 TEST: Calling Whisper directly with {len(combined_16k)} bytes")
    test_response = client.audio.transcriptions.create(
        model="whisper-1",
        file=wav_buffer,
        language="fr",
        response_format="verbose_json",
        temperature=0.0
    )
    logger.info(f"[{session_id}] 🧪 TEST: Whisper returned: '{test_response.text}'")
except Exception as e:
    logger.error(f"[{session_id}] 🧪 TEST: Whisper error: {e}")
```

## Immediate Actions

1. **Change DEBUG to INFO** for all buffering logs
2. **Lower RMS threshold** to 10
3. **Restart server**
4. **Make test call** and check logs for:
   - `💤 Still waiting for speech` → RMS too low
   - `⏳ Buffering: X.XXs` → Still collecting audio
   - `⏭️ Segment too short` → Speech too brief
   - `🔍 WHISPER DIAGNOSTIC` → Actually calling Whisper!

## Expected Log Sequence (Should See)

```
[session_id] ⏭️ Skipping initial 0.5s period (0.10s elapsed)
[session_id] ⏭️ Skipping initial 0.5s period (0.20s elapsed)
...
[session_id] 💤 Still waiting for speech (RMS=15.3 < 30)  ← RMS check
[session_id] 🎙️ Speech detected (RMS=145.7) — starting real buffering  ← Speech starts
[session_id] 📦 Added chunk 31998 bytes to buffer (total chunks: 1)
[session_id] ⏱️ Buffer duration: 1.00s
[session_id] ⏳ Buffering: 1.00s, VAD status: speech_continuing
[session_id] 📦 Added chunk 31998 bytes to buffer (total chunks: 2)
[session_id] ⏱️ Buffer duration: 2.00s
[session_id] ⏳ Buffering: 2.00s, VAD status: speech_continuing
...
[session_id] ✂️ VAD-based segmentation triggered: reason=silence_detected, duration=3.50s
[session_id] Combined 3 chunks = 95994 bytes, duration=3.50s
🔍 WHISPER DIAGNOSTIC - Audio buffer size: 95994 bytes  ← Whisper called!
...
✅ WHISPER DIAGNOSTIC - Valid transcription received (45 chars)
```

## Why This Wasn't Obvious

1. **Misleading log message** "CALLING WHISPER API" when not actually calling Whisper
2. **DEBUG-level logs** hidden, so we can't see buffering state
3. **Silent failures** - returns None without explanation
4. **Multiple exit points** - hard to trace which one is triggered

## Fix Priority

1. ✅ **CRITICAL**: Change debug to info for visibility
2. ✅ **HIGH**: Lower RMS threshold to 10
3. ⚠️ **MEDIUM**: Reduce min speech duration to 0.5s
4. 🧪 **TESTING**: Add direct Whisper test bypass

Apply fixes 1 and 2 immediately, restart, test call, analyze logs.
