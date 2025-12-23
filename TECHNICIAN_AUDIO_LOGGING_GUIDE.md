# Technician Audio Pipeline - Comprehensive Logging Guide

This document explains the 19-stage logging system for tracking technician audio from Twilio phone calls through to frontend display.

## Overview

The technician's audio signal flows through multiple stages:
1. **Twilio → WebSocket** (Stages 1-6): Connection and message reception
2. **Audio Decoding** (Stages 7-11): Base64 → mulaw → PCM → resampled
3. **Buffer Accumulation** (Stages 12-15): Collecting 1-second segments
4. **Transcription** (Stages 16-17): Whisper API call
5. **Frontend Broadcast** (Stages 18-19): WebSocket to agent UI

## Stage-by-Stage Breakdown

### 🔌 STAGE 1: Twilio Media Stream WebSocket CONNECTED
**Location:** `app/api/twilio_routes.py` line ~466
**What happens:** Initial WebSocket connection from Twilio established
**Look for:** `🔌 STAGE 1: Twilio Media Stream WebSocket CONNECTED`
**Failure symptom:** No connection = Twilio can't reach your server (check firewall, ngrok, URL configuration)

---

### 📨 STAGE 2: Raw message received from Twilio
**Location:** `app/api/twilio_routes.py` line ~486
**What happens:** Raw WebSocket message received from Twilio
**Look for:** `📨 STAGE 2: Raw message received from Twilio, size=XXX bytes`
**Check:** Message size should be 200-500 bytes for media events
**Failure symptom:** No messages = Twilio not sending audio (check call status, TwiML configuration)

---

### 📋 STAGE 3: JSON parsing
**Location:** `app/api/twilio_routes.py` line ~490
**What happens:** Parse JSON from Twilio message
**Look for:** `📋 STAGE 3: Parsed JSON event type: 'media'` or `'start'` or `'stop'`
**Check:** Event types should be: `start` (once), `media` (continuous), `stop` (once)
**Failure symptom:** JSON parse errors = Twilio sending malformed data

---

### 🎬 STAGE 4: STREAM START EVENT
**Location:** `app/api/twilio_routes.py` line ~495
**What happens:** Twilio stream initialization with stream SID and parameters
**Look for:** `🎬 STAGE 4: STREAM START EVENT` with Stream SID and session ID
**Check:**
- Stream SID format: `MZxxxxxxxxxx` (Twilio identifier)
- Session ID should match your application session
- Media format should show: `{"encoding": "audio/x-mulaw", "sampleRate": 8000}`
**Failure symptom:** No start event = Twilio stream never initialized

---

### ✅ STAGE 5: Technician stream initialization
**Location:** `app/api/twilio_routes.py` line ~524
**What happens:** Create nested data structure for technician in `active_streams`
**Look for:** `✅ STAGE 5: Technician stream initialized in active_streams[SESSION_ID]['technician']`
**Check:** Verify session ID matches across stages
**Failure symptom:** Initialization fails = subsequent stages will fail with KeyError

---

### 🎵 STAGE 6: MEDIA EVENT - Audio payload received
**Location:** `app/api/twilio_routes.py` line ~532
**What happens:** Receive individual audio packet from Twilio
**Look for:** `🎵 STAGE 6: MEDIA EVENT - Audio payload received`
**Check:**
- Payload length (base64): typically 100-300 characters per packet
- Media timestamp: incrementing sequence showing time progression
- Estimated decoded size: typically 80-240 bytes mulaw
**Timing:** Should receive ~50 packets per second (20ms audio each)
**Failure symptom:** No media events = Twilio connected but not streaming audio (check microphone, phone permissions)

---

### 🔧 STAGE 7: _process_audio_chunk_sync called
**Location:** `app/services/twilio_audio_service.py` line ~148
**What happens:** Enter audio processing function with base64 payload
**Look for:** `🔧 STAGE 7: _process_audio_chunk_sync called`
**Check:** Input payload length should match Stage 6
**Failure symptom:** Stage 6 present but no Stage 7 = function not being called (check routing)

---

### ✅ STAGE 8: Base64 decoded
**Location:** `app/services/twilio_audio_service.py` line ~153
**What happens:** Decode base64 string to raw bytes
**Look for:** `✅ STAGE 8: Base64 decoded → XXX bytes mulaw`
**Check:** Mulaw bytes = base64 chars × 3/4 (approximately)
**Typical:** 100-240 bytes mulaw per packet
**Failure symptom:** Base64 decode error = corrupted data from Twilio

---

### ✅ STAGE 9: Mulaw decoded to PCM
**Location:** `app/services/twilio_audio_service.py` line ~157
**What happens:** Convert mulaw (telephone compression) to linear PCM 16-bit
**Look for:** `✅ STAGE 9: Mulaw decoded → XXX bytes PCM (8kHz, 16-bit)`
**Check:** PCM bytes should be 2× mulaw bytes (mulaw is 8-bit, PCM is 16-bit)
**Typical:** 200-480 bytes PCM per packet
**Failure symptom:** Mulaw decode error = invalid audio format

---

### ✅ STAGE 10: Resampled to 16kHz
**Location:** `app/services/twilio_audio_service.py` line ~171
**What happens:** Resample from 8kHz (phone) to 16kHz (Whisper requirement)
**Look for:** `✅ STAGE 10: Resampled to 16kHz → XXX bytes, YYY samples, ~ZZ.Zms`
**Check:**
- Bytes should be ~2× Stage 9 bytes (doubling sample rate)
- Samples = bytes / 2 (16-bit = 2 bytes per sample)
- Duration = (samples / 16000) × 1000 ms
**Typical:** 400-960 bytes, 200-480 samples, 12-30ms duration
**Failure symptom:** Resample error = audioop failure

---

### 📊 STAGE 11: Audio characteristics
**Location:** `app/services/twilio_audio_service.py` line ~179
**What happens:** Calculate RMS (volume level) and max amplitude
**Look for:** `📊 STAGE 11: Audio characteristics - RMS=XXX.X, Max=YYY, Samples=ZZZ`
**Check:**
- **RMS (Root Mean Square)**: Average audio level
  - Normal speech: 500-2000
  - Quiet/silence: < 100
  - Very loud/clipping: > 5000
- **Max Amplitude**: Peak level (-32768 to +32767)
- **Warnings:**
  - `⚠️ WARNING: Very low audio level (RMS=XX.X)` - may be silence
  - `⚠️ WARNING: Very high audio level (RMS=XXX.X)` - may be clipping
**Failure symptom:** Consistently low RMS = microphone issue, background noise only

---

### 🔄 STAGE 12: _process_audio_chunk called
**Location:** `app/services/twilio_audio_service.py` line ~196
**What happens:** Enter buffer accumulation function with processed PCM audio
**Look for:** `🔄 STAGE 12: _process_audio_chunk called`
**Check:**
- Input should be 16kHz PCM audio
- Session must exist in active_streams
- 'technician' key must exist in nested structure
**Failure symptoms:**
- `❌ STAGE 12 FAILED: Session not found` - session cleanup race condition
- `❌ STAGE 12 FAILED: 'technician' key not found` - nested structure not initialized

---

### 📦 STAGE 13: Adding chunk to buffer
**Location:** `app/services/twilio_audio_service.py` line ~226
**What happens:** Append audio chunk to buffer array and calculate total duration
**Look for:** `📦 STAGE 13: Adding chunk to buffer`
**Check:**
- **Buffer size**: Number of chunks accumulated (typically 40-60 for 1 second)
- **Total samples**: Sum of all samples across chunks
- **Duration**: total_samples / 16000 seconds
- **Threshold check**: Shows how much more audio needed to reach 1.0s
**Timing:** Buffer grows until 1.0 second threshold reached
**Example:**
```
STAGE 13: Buffer updated
   New buffer size: 45 chunks
   Total samples: 14400
   Duration: 0.90 seconds
   Threshold: 1.0 seconds (need 0.10s more)
```

---

### ⏸️ STAGE 14: Threshold check
**Location:** `app/services/twilio_audio_service.py` line ~240-247
**What happens:** Check if 1-second buffer threshold reached
**Look for:**
- `⏸️ STAGE 14: Buffer duration below 1.0s threshold - waiting for more audio` (loop continues)
- OR `🎯 STAGE 14: 1-SECOND THRESHOLD REACHED - Processing transcription` (processing begins)
**Check:** Duration must be >= 1.0 seconds to proceed
**Timing:** Stages 12-14 repeat ~50 times per second until threshold reached
**This is normal:** Most chunks will show "waiting for more audio"

---

### 🔗 STAGE 15: Combining audio chunks
**Location:** `app/services/twilio_audio_service.py` line ~249-273
**What happens:** Combine buffered chunks into single audio segment and check quality
**Look for:** `🔗 STAGE 15: Combining XX audio chunks into single buffer`
**Check:**
- **Combined audio size**: Typically 32000-40000 bytes for 1 second (16kHz × 2 bytes/sample)
- **RMS Level**: Should be >= 100 for technician (quality gate)
- **Max Amplitude**: Peak in combined segment
- **Duration**: Should be ~1.0-1.2 seconds
**Quality Gate:**
- ✅ `RMS quality gate passed (RMS=XXX >= 100)` - good audio, will transcribe
- ⚠️ `WARNING: RMS=XX below technician threshold (100)` - may be too quiet, but still attempts transcription
**Failure symptom:** Consistently low RMS indicates microphone too quiet or background noise only

---

### 📞 STAGE 16: Transcription service loading
**Location:** `app/services/twilio_audio_service.py` line ~277-283
**What happens:** Import transcription service and prepare parameters
**Look for:** `📞 STAGE 16: Importing transcription service`
**Check:**
- Service loaded successfully: `✅ STAGE 16: Transcription service loaded`
- Timestamp calculated: Shows seconds since session start
**Failure symptom:** Import errors = transcription service not available (check dependencies, initialization)

---

### 🚀 STAGE 17: CALLING WHISPER API
**Location:** `app/services/twilio_audio_service.py` line ~285-299
**What happens:** Send audio to OpenAI Whisper for transcription
**Look for:** `🚀 STAGE 17: CALLING WHISPER API`
**Check:**
- **Session ID**: Verify correct session
- **Audio size**: Should be ~32000-40000 bytes
- **Timestamp**: Seconds from session start
- **Speaker**: Should be "technician (default)"
**Wait time:** API call typically takes 0.5-2 seconds
**Look for return:** `📥 STAGE 17: Whisper API returned`
**Possible outcomes:**
- ✅ `STAGE 17: Result is not None - processing response` - success
- ❌ `STAGE 17 FAILED: Transcription returned None` - API failure
**Failure symptoms:**
- Timeout = Whisper API slow/down (check network, OpenAI status)
- None result = API rejected audio (too short, silent, invalid format)
- Exception = API key invalid, quota exceeded, network error

---

### 📝 STAGE 18: Extracted text from result
**Location:** `app/services/twilio_audio_service.py` line ~305-361
**What happens:** Extract and validate transcription text from Whisper response
**Look for:** `📝 STAGE 18: Extracted text from result`
**Check:**
- **Text length**: Number of characters transcribed
- **Text preview**: First 100 characters
- **Full text**: Complete transcription
**Possible outcomes:**
- ✅ `STAGE 18: Non-empty transcription received` - success, proceed to broadcast
- ⚠️ `STAGE 18 WARNING: Empty text from transcription` - API returned but no speech detected
**Common empty text causes:**
- Silent audio (RMS too low)
- Background noise only
- Language mismatch (Whisper expecting different language)
- Audio too short or corrupted

---

### 📡 STAGE 19: WEBSOCKET BROADCAST
**Location:** `app/services/twilio_audio_service.py` line ~315-356
**What happens:** Send transcription to agent's browser UI via WebSocket
**Look for:** `📡 STAGE 19: WEBSOCKET BROADCAST - Sending to agent UI`
**Check:**
1. **WebSocket availability:**
   - `Session in active_streams: True/False`
   - `'agent' in stream: True/False`
   - `✅ STAGE 19: Agent WebSocket found` (success path)
   - `⚠️ STAGE 19 SKIPPED: No agent WebSocket available` (agent not connected)

2. **Message creation:**
   - Message structure: JSON with type, text, speaker_label, speaker_role, timestamp, confidence
   - Message size: typically 100-500 bytes
   - Message preview: First 200 characters

3. **WebSocket send:**
   - ✅✅✅ `STAGE 19 SUCCESS: Transcription sent to agent UI!` - **COMPLETE SUCCESS**
   - ❌ `STAGE 19 FAILED: WebSocket send error` - network or WebSocket issue
**Failure symptoms:**
- No agent WebSocket = Agent UI not connected (refresh browser, check WebSocket connection)
- WebSocket send error = Connection dropped, browser closed, network issue
- Success logged but not displayed = Frontend JavaScript issue (check browser console)

---

## Complete Success Path

When everything works correctly, you'll see this sequence in the logs:

```
================================================================================
🔌 STAGE 1: Twilio Media Stream WebSocket CONNECTED
================================================================================
📨 STAGE 2: Raw message received from Twilio, size=234 bytes
📋 STAGE 3: Parsed JSON event type: 'start'
================================================================================
🎬 STAGE 4: STREAM START EVENT
   Stream SID: MZabcdef123456
   Session ID: abc-123-def
   Media Format: {"encoding": "audio/x-mulaw", "sampleRate": 8000}
================================================================================
✅ STAGE 5: Technician stream initialized in active_streams[abc-123-def]['technician']

[... multiple media packets ...]

────────────────────────────────────────────────────────────────────────────────
🎵 STAGE 6: MEDIA EVENT - Audio payload received
   Session ID: abc-123-def
   Payload length (base64): 240 characters
   Media timestamp: 1000
   Estimated decoded size: ~180 bytes (mulaw)
────────────────────────────────────────────────────────────────────────────────
🔧 STAGE 7: _process_audio_chunk_sync called
   Input: Base64 payload length=240 chars
✅ STAGE 8: Base64 decoded → 180 bytes mulaw
✅ STAGE 9: Mulaw decoded → 360 bytes PCM (8kHz, 16-bit)
✅ STAGE 10: Resampled to 16kHz → 720 bytes, 360 samples, ~22.5ms
📊 STAGE 11: Audio characteristics - RMS=850.3, Max=1234, Samples=360

────────────────────────────────────────────────────────────────────────────────
🔄 STAGE 12: _process_audio_chunk called
   Input: 720 bytes of PCM audio (16kHz)
📊 STAGE 12: Chunk characteristics - RMS=850.3, Max=1234, Samples=360
✅ STAGE 12: Session and technician stream verified
📦 STAGE 13: Adding chunk to buffer
   Current buffer size before: 44 chunks
✅ STAGE 13: Buffer updated
   New buffer size: 45 chunks
   Total samples: 16200
   Duration: 1.01 seconds
   ✓ Threshold reached!

================================================================================
🎯 STAGE 14: 1-SECOND THRESHOLD REACHED - Processing transcription
================================================================================
🔗 STAGE 15: Combining 45 audio chunks into single buffer
✅ STAGE 15: Combined audio = 32400 bytes
🧹 STAGE 15: Buffer cleared for next accumulation
📊 STAGE 15: Combined audio characteristics:
   RMS Level: 875.2
   Max Amplitude: 2456
   Total Samples: 16200
   Duration: 1.01s
✅ STAGE 15: RMS quality gate passed (RMS=875.2 >= 100)

📞 STAGE 16: Importing transcription service
✅ STAGE 16: Transcription service loaded
⏱️ STAGE 16: Timestamp calculated = 3.45s from session start

================================================================================
🚀 STAGE 17: CALLING WHISPER API
   Session ID: abc-123-def
   Audio size: 32400 bytes
   Timestamp: 3.45s
   Speaker: technician (default)
================================================================================
📥 STAGE 17: Whisper API returned
✅ STAGE 17: Result is not None - processing response
   Result keys: ['text', 'speaker_name', 'speaker_role', 'timestamp', 'confidence']

📝 STAGE 18: Extracted text from result
   Text length: 42 characters
   Text preview: 'Bonjour, j'ai un problème avec ma caméra'
✅ STAGE 18: Non-empty transcription received
   Full text: 'Bonjour, j'ai un problème avec ma caméra'

================================================================================
📡 STAGE 19: WEBSOCKET BROADCAST - Sending to agent UI
================================================================================
🔍 STAGE 19: Checking for agent WebSocket
   Session in active_streams: True
   'agent' in stream: True
✅ STAGE 19: Agent WebSocket found
📦 STAGE 19: Transcription message created
   Message size: 187 bytes
   Message preview: {"type":"transcription","text":"Bonjour, j'ai un problème avec ma caméra","speaker_label":"Customer","speaker_role":"technician"...

================================================================================
✅✅✅ STAGE 19 SUCCESS: Transcription sent to agent UI!
   Text: 'Bonjour, j'ai un problème avec ma caméra'
================================================================================
```

## Troubleshooting Guide

### Problem: No audio received from Twilio

**Check stages:** 1, 2, 6
**Symptoms:**
- Stage 1 present but no Stage 6
- Stage 2 shows only 'start' and 'stop', no 'media' events

**Solutions:**
1. Check Twilio call status (is call answered?)
2. Check phone microphone permissions
3. Verify TwiML has `<Start><Stream>` element
4. Check Twilio console for call errors

---

### Problem: Audio received but not decoded

**Check stages:** 6, 7, 8, 9, 10
**Symptoms:**
- Stage 6 present but no Stage 7
- Errors in Stage 8-10

**Solutions:**
1. Check function routing (is `_process_audio_chunk_sync` being called?)
2. Verify base64 encoding is valid
3. Check audioop library installed correctly
4. Review error logs for specific decode failures

---

### Problem: Audio decoded but RMS too low

**Check stages:** 11, 15
**Symptoms:**
- ⚠️ WARNING: Very low audio level
- RMS consistently < 100

**Solutions:**
1. Ask technician to speak louder
2. Check phone microphone placement
3. Test in quieter environment
4. Consider lowering RMS threshold (currently 100 for technician)

---

### Problem: Buffer never reaches 1 second

**Check stages:** 12, 13, 14
**Symptoms:**
- Stage 14 always shows "waiting for more audio"
- Duration stuck below 1.0s

**Solutions:**
1. Check if audio chunks are being received continuously
2. Verify sample rate calculations (16000 Hz)
3. Check if buffer is being cleared prematurely
4. Review timing of packet arrival

---

### Problem: Whisper API fails or returns None

**Check stage:** 17
**Symptoms:**
- ❌ STAGE 17 FAILED: Transcription returned None
- Timeout errors
- API exceptions

**Solutions:**
1. Check OpenAI API key validity
2. Verify API quota not exceeded
3. Check network connectivity to OpenAI
4. Test with longer/clearer audio samples
5. Verify audio format (16kHz PCM, 16-bit)

---

### Problem: Empty transcriptions

**Check stage:** 18
**Symptoms:**
- ⚠️ STAGE 18 WARNING: Empty text from transcription
- Whisper returns successfully but text is empty

**Solutions:**
1. Check RMS levels (audio too quiet?)
2. Verify language setting matches speech (French vs English)
3. Test with clearer speech samples
4. Check if audio contains actual speech vs noise
5. Try longer audio segments (increase threshold above 1s)

---

### Problem: Transcription not displayed on frontend

**Check stage:** 19
**Symptoms:**
- Stage 17-18 success but not visible in UI
- ⚠️ STAGE 19 SKIPPED: No agent WebSocket available

**Solutions:**
1. **No WebSocket:**
   - Refresh agent browser
   - Check WebSocket connection in browser dev tools (Network → WS)
   - Verify session IDs match between agent and technician
   - Check if agent clicked "Start Call" button

2. **WebSocket send error:**
   - Check browser console for errors
   - Verify WebSocket not closed prematurely
   - Test network connectivity
   - Check if agent browser still open

3. **Success logged but not visible:**
   - Open browser developer console (F12)
   - Check for JavaScript errors in console
   - Verify `displayTranscriptionFromBackend()` function exists
   - Check if transcription display element exists in DOM

---

## Monitoring Best Practices

1. **Filter logs by session ID:**
   ```bash
   tail -f log_file.txt | grep "abc-123-def"
   ```

2. **Watch for stage progression:**
   - Stages 1-5: Should appear once per call
   - Stage 6: Should appear ~50 times per second during speech
   - Stages 7-11: Should match Stage 6 frequency
   - Stages 12-14: Repeat until threshold (most show "waiting")
   - Stages 15-19: Appear every ~1 second during continuous speech

3. **Monitor key metrics:**
   - RMS levels: 500-2000 is ideal for speech
   - Buffer duration: Should steadily increase to 1.0s
   - Transcription latency: Stage 17 should complete in 0.5-2s
   - WebSocket status: Agent should stay connected throughout call

4. **Success indicators:**
   - ✅✅✅ appears at Stage 19 = complete pipeline success
   - Transcriptions visible in agent UI
   - Both agent and technician transcriptions appearing

## Performance Expectations

- **Packet frequency:** ~50 media packets/second
- **Buffer accumulation:** ~1 second of audio (~45-50 chunks)
- **Whisper API latency:** 0.5-2 seconds
- **Total latency (speech → display):** ~1.5-3 seconds
- **Transcription frequency:** Every ~1 second during continuous speech

## Log File Location

Logs are output to:
- **Console/stdout:** Real-time monitoring
- **Log file:** Check application configuration for log file path

## Additional Notes

- All stages use emojis for quick visual scanning
- Stage numbers are sequential and comprehensive (1-19)
- Separators (─ and =) help visually distinguish stage types
- Error messages always include ❌ symbol
- Warnings always include ⚠️ symbol
- Success messages use ✅ symbol
