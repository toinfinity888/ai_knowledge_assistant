# Whisper Diagnostic Logging Guide

## Overview

Comprehensive diagnostic logging has been added to the Whisper API transcription flow to help debug issues where:
- Whisper returns None or empty transcriptions
- Audio sounds distorted but has good RMS levels
- Transcriptions don't appear in the UI

## Location

**File:** [app/services/enhanced_transcription_service.py](app/services/enhanced_transcription_service.py)
**Method:** `_transcribe_with_whisper()` (lines 339-511)

## What Gets Logged

### 1. Audio Buffer Verification (Before API Call)

#### Buffer Size
```
🔍 WHISPER DIAGNOSTIC - Audio buffer size: 57644 bytes (56.29 KB)
```
- Shows total size of audio being sent to Whisper
- Typical: ~30-60 KB for 1-2 seconds of 16kHz, 16-bit mono audio

#### Audio Format Details
```
🔍 WHISPER DIAGNOSTIC - Audio format:
   Channels: 1 (expected: 1)
   Sample rate: 16000 Hz (expected: 16000)
   Sample width: 2 bytes (expected: 2 for 16-bit)
   Duration: 1.80 seconds
   Frames: 28,800
```
- Verifies WAV file has correct format for Whisper API
- Whisper requires: 16kHz, 16-bit, mono
- Any mismatch will be flagged

#### Audio Data Integrity
```
🔍 WHISPER DIAGNOSTIC - Audio data integrity:
   First 5 samples: [234, -156, 892, 1203, -445]
   RMS level: 811.9
   Max amplitude: 8316
   Samples analyzed: 100
```
- Shows first few audio samples to verify data is not all zeros
- Calculates RMS of first 100 samples
- Shows max amplitude to detect clipping

#### Audio Level Assessment
```
✅ WHISPER DIAGNOSTIC - Audio level appears NORMAL (RMS=811.9)
```

Or warnings:
```
⚠️ WHISPER DIAGNOSTIC - Audio is VERY QUIET (RMS=45.3)
❌ WHISPER DIAGNOSTIC - Audio appears SILENT (RMS=2.1)
```

**Thresholds:**
- RMS < 10: SILENT (likely no audio)
- RMS < 100: VERY QUIET (may not transcribe well)
- RMS >= 100: NORMAL (should transcribe fine)

### 2. Whisper API Call

```
🎯 Calling Whisper API with model=whisper-1, language=fr
```

Shows:
- Model being used (whisper-1)
- Language parameter (fr, en, etc.)

### 3. API Response Analysis

#### Response Timing
```
🔍 WHISPER DIAGNOSTIC - API call completed in 2.34s
```
- Shows how long Whisper API took to respond
- Typical: 2-5 seconds depending on audio length

#### Response Object Type
```
🔍 WHISPER DIAGNOSTIC - Full response object type: <class 'openai.types.audio.Transcription'>
🔍 WHISPER DIAGNOSTIC - Response attributes: ['text', 'language', 'duration', 'segments', ...]
```
- Shows Python type of response object
- Lists all available attributes

#### Response Fields
```
🔍 WHISPER DIAGNOSTIC - response.text: 'Bonjour, j'ai un problème avec...'
🔍 WHISPER DIAGNOSTIC - response.language: 'fr'
🔍 WHISPER DIAGNOSTIC - response.duration: 1.80s
🔍 WHISPER DIAGNOSTIC - response.segments count: 3
```
- Logs each field of the response
- Shows actual transcription text
- Confirms language detected by Whisper
- Shows audio duration as calculated by Whisper

#### None Response Detection
```
❌ WHISPER DIAGNOSTIC - response.text is None (not empty string, but None type)
❌ WHISPER DIAGNOSTIC - This suggests Whisper could not process the audio
```
- Differentiates between empty string `''` and `None` type
- `None` means API had an issue processing audio

#### Empty Text Detection
```
⚠️ WHISPER DIAGNOSTIC - Whisper returned EMPTY text!
⚠️ WHISPER DIAGNOSTIC - This could mean:
   1. Audio is silent or too quiet
   2. Audio is too noisy/distorted
   3. Wrong language specified
   4. Audio format issue
⚠️ WHISPER DIAGNOSTIC - Full response: {'text': '', 'language': 'fr', 'duration': 1.8}
```
- Explains possible causes of empty transcription
- Shows full response for debugging

### 4. Error Handling
```
❌ WHISPER API EXCEPTION: HTTPError: 400 Bad Request
❌ WHISPER DIAGNOSTIC - Exception occurred during API call or response processing
```
- Logs exception type and message
- Includes full stack trace
- Helps identify API errors vs code bugs

## How to Use the Logs

### Scenario 1: Whisper Returns None

**Look for:**
1. **Audio Format Issues**
   ```
   Channels: 2 (expected: 1)  ❌ PROBLEM: Stereo instead of mono
   Sample rate: 8000 Hz (expected: 16000)  ❌ PROBLEM: Wrong sample rate
   ```

2. **Silent Audio**
   ```
   ❌ WHISPER DIAGNOSTIC - Audio appears SILENT (RMS=2.1)
   ```

3. **Missing Response Fields**
   ```
   ❌ WHISPER DIAGNOSTIC - Response has NO 'text' attribute!
   ```

4. **API Exception**
   ```
   ❌ WHISPER API EXCEPTION: ...
   ```

### Scenario 2: Empty Transcription

**Look for:**
1. **Quiet Audio**
   ```
   ⚠️ WHISPER DIAGNOSTIC - Audio is VERY QUIET (RMS=45.3)
   ```
   **Solution:** Increase gain or ask technician to speak louder

2. **Wrong Language**
   ```
   🔍 WHISPER DIAGNOSTIC - response.language: 'en'
   ```
   But you expected French
   **Solution:** Check language detection, verify audio is in expected language

3. **Distorted Audio**
   ```
   Max amplitude: 32767  ❌ Clipping detected
   ```
   **Solution:** Reduce input volume

### Scenario 3: Distorted Audio Despite Good RMS

**Look for:**
```
RMS level: 811.9  ✅ Good
Max amplitude: 8316
First 5 samples: [2341, -1567, 2892, -2103, 1445]
```

**Analysis:**
- Max amplitude of ~8316 is NORMAL for mulaw-decoded audio
- Mulaw uses 8-bit encoding (256 values when encoded)
- Decoded max is typically ±8159, NOT ±32767
- Low number of unique values is EXPECTED

**If still sounds distorted:**
1. Check recorded WAV file directly with audio player
2. Compare with original Twilio stream
3. Verify resampling pipeline (should be buffer-then-resample, not chunk-by-chunk)

## Log Example: Successful Transcription

```
🔍 WHISPER DIAGNOSTIC - Audio buffer size: 57644 bytes (56.29 KB)
🔍 WHISPER DIAGNOSTIC - Audio format:
   Channels: 1 (expected: 1)
   Sample rate: 16000 Hz (expected: 16000)
   Sample width: 2 bytes (expected: 2 for 16-bit)
   Duration: 1.80 seconds
   Frames: 28,800
🔍 WHISPER DIAGNOSTIC - Audio data integrity:
   First 5 samples: [234, -156, 892, 1203, -445]
   RMS level: 811.9
   Max amplitude: 8316
   Samples analyzed: 100
✅ WHISPER DIAGNOSTIC - Audio level appears NORMAL (RMS=811.9)
🎯 Calling Whisper API with model=whisper-1, language=fr
🔍 WHISPER DIAGNOSTIC - API call completed in 2.34s
🔍 WHISPER DIAGNOSTIC - Full response object type: <class 'openai.types.audio.Transcription'>
🔍 WHISPER DIAGNOSTIC - response.text: 'Bonjour, j'ai un problème avec la caméra'
🔍 WHISPER DIAGNOSTIC - response.language: 'fr'
🔍 WHISPER DIAGNOSTIC - response.duration: 1.80s
🔍 WHISPER DIAGNOSTIC - response.segments count: 1
🎯 Whisper API response: text='Bonjour, j'ai un problème avec la caméra', language=fr, duration=1.8
```

## Log Example: Failed Transcription (Silent Audio)

```
🔍 WHISPER DIAGNOSTIC - Audio buffer size: 32044 bytes (31.29 KB)
🔍 WHISPER DIAGNOSTIC - Audio format:
   Channels: 1 (expected: 1)
   Sample rate: 16000 Hz (expected: 16000)
   Sample width: 2 bytes (expected: 2 for 16-bit)
   Duration: 1.00 seconds
   Frames: 16,000
🔍 WHISPER DIAGNOSTIC - Audio data integrity:
   First 5 samples: [2, -1, 0, 1, -2]
   RMS level: 3.4
   Max amplitude: 5
   Samples analyzed: 100
❌ WHISPER DIAGNOSTIC - Audio appears SILENT (RMS=3.4)
🎯 Calling Whisper API with model=whisper-1, language=fr
🔍 WHISPER DIAGNOSTIC - API call completed in 1.89s
🔍 WHISPER DIAGNOSTIC - response.text: ''
🔍 WHISPER DIAGNOSTIC - response.language: 'fr'
🔍 WHISPER DIAGNOSTIC - response.duration: 1.00s
⚠️ WHISPER DIAGNOSTIC - Whisper returned EMPTY text!
⚠️ WHISPER DIAGNOSTIC - This could mean:
   1. Audio is silent or too quiet
   2. Audio is too noisy/distorted
   3. Wrong language specified
   4. Audio format issue
⚠️ WHISPER DIAGNOSTIC - Full response: {'text': '', 'language': 'fr', 'duration': 1.0}
[session_123] Whisper returned empty text: {'text': '', 'language': 'fr', 'duration': 1.0, 'confidence': 0.9}
```

## Log Example: API Exception

```
🔍 WHISPER DIAGNOSTIC - Audio buffer size: 45123 bytes (44.07 KB)
🔍 WHISPER DIAGNOSTIC - Audio format:
   Channels: 1 (expected: 1)
   Sample rate: 16000 Hz (expected: 16000)
   Sample width: 2 bytes (expected: 2 for 16-bit)
   Duration: 1.41 seconds
   Frames: 22,561
✅ WHISPER DIAGNOSTIC - Audio level appears NORMAL (RMS=921.3)
🎯 Calling Whisper API with model=whisper-1, language=fr
❌ WHISPER API EXCEPTION: APIConnectionError: Connection timeout
❌ WHISPER DIAGNOSTIC - Exception occurred during API call or response processing
Traceback (most recent call last):
  File "app/services/enhanced_transcription_service.py", line 436, in _transcribe_with_whisper
    response = self.openai_client.audio.transcriptions.create(...)
  ...
```

## Filtering Logs

Since diagnostic logging is verbose, you can filter for specific issues:

### Show only Whisper diagnostic messages
```bash
grep "WHISPER DIAGNOSTIC" logs.txt
```

### Show only errors
```bash
grep "❌ WHISPER" logs.txt
```

### Show only warnings
```bash
grep "⚠️ WHISPER" logs.txt
```

### Show successful transcriptions
```bash
grep "🎯 Whisper API response:" logs.txt
```

### Show empty transcriptions
```bash
grep "EMPTY text" logs.txt
```

## Performance Impact

**Development/Testing:**
- Keep diagnostic logging enabled
- Helps debug audio quality and transcription issues

**Production:**
- Consider reducing logging level
- Keep error/warning logs
- Optional: Disable detailed diagnostics for performance

To disable detailed diagnostics, comment out lines 355-414 in [enhanced_transcription_service.py](app/services/enhanced_transcription_service.py):

```python
# async def _transcribe_with_whisper(...):
#     try:
#         # ========================================
#         # DIAGNOSTIC LOGGING - AUDIO VERIFICATION
#         # ========================================
#         # ... comment out this entire section ...
```

## Related Documentation

- [Audio Recording Guide](AUDIO_RECORDING_GUIDE.md) - How to record and analyze audio
- [Audio Refactor Complete](AUDIO_REFACTOR_COMPLETE.md) - Buffer-then-resample architecture
- [Transcription Flow Diagnosis](TRANSCRIPTION_FLOW_DIAGNOSIS.md) - Complete transcription pipeline
- [Technician Audio Logging](TECHNICIAN_AUDIO_LOGGING_GUIDE.md) - Complete pipeline stage logging

## Troubleshooting Decision Tree

```
Whisper returns None or empty?
│
├─ Check Audio Level
│  ├─ RMS < 10 → Audio is silent, check microphone/connection
│  ├─ RMS < 100 → Audio too quiet, increase gain or ask to speak louder
│  └─ RMS >= 100 → Audio level is OK, continue...
│
├─ Check Audio Format
│  ├─ Channels != 1 → Convert to mono
│  ├─ Sample rate != 16000 → Resample to 16kHz
│  ├─ Sample width != 2 → Convert to 16-bit
│  └─ Format correct → Continue...
│
├─ Check API Response
│  ├─ response.text is None → API error, check exception logs
│  ├─ response.text is '' → Check possible causes:
│  │  ├─ Language mismatch → Verify language parameter
│  │  ├─ Noise/distortion → Check audio quality
│  │  └─ Silent audio → Verify speech is present
│  └─ response.text has content → Success!
│
└─ Check for Exceptions
   ├─ API timeout → Network issue
   ├─ 400 Bad Request → Invalid audio format
   ├─ 401 Unauthorized → Check API key
   └─ Other → Check stack trace
```

## Summary

- ✅ Comprehensive logging added to Whisper API flow
- ✅ Audio format verification before API call
- ✅ RMS level assessment with thresholds
- ✅ Detailed response analysis
- ✅ Clear error messages with suggested fixes
- ✅ Performance timing
- ✅ Exception handling with stack traces

The diagnostic logging will help identify exactly why Whisper is returning None or empty transcriptions, making it much easier to debug audio quality issues.
