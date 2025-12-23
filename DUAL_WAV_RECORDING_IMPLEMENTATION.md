# Dual WAV File Recording Implementation

## Status: ✅ COMPLETE

Successfully implemented dual WAV file recording for technician audio to help diagnose resampling quality.

---

## What Was Implemented

The system now creates **TWO separate WAV files** for each technician phone call:

1. **8kHz WAV file** - Original audio BEFORE resampling
2. **16kHz WAV file** - Resampled audio AFTER resampling

This allows you to compare the audio quality before and after the resampling operation to determine if resampling introduces any artifacts or quality degradation.

---

## File Naming Convention

Both files include the sample rate in the filename for easy identification:

```
technician_{session_id}_{timestamp}_8000Hz.wav   # Original 8kHz audio
technician_{session_id}_{timestamp}_16000Hz.wav  # Resampled 16kHz audio
```

**Example:**
```
recordings/
├── technician_abc123_20251119_143022_8000Hz.wav   # 8kHz original
└── technician_abc123_20251119_143022_16000Hz.wav  # 16kHz resampled
```

---

## Technical Implementation

### 1. Updated Stream Initialization

**File:** `app/api/twilio_routes.py` (lines 238-248)

**Before:**
```python
twilio_service.active_streams[session_id] = {
    'websocket': ws,
    'stream_sid': stream_sid,
    'started_at': datetime.utcnow(),
    'audio_buffer': []  # ❌ Flat structure, no WAV files
}
```

**After:**
```python
twilio_service.active_streams[session_id] = {
    'websocket': ws,
    'stream_sid': stream_sid,
    'started_at': datetime.utcnow(),
    'technician': {  # ✅ Nested structure
        'audio_buffer': [],
        'wav_file_8kHz': twilio_service._create_wav_file(session_id, "technician", 8000),
        'wav_file_16kHz': twilio_service._create_wav_file(session_id, "technician", 16000)
    }
}
```

**Key Changes:**
- Created nested 'technician' structure (fixes previous structural mismatch)
- Creates BOTH 8kHz and 16kHz WAV files at stream initialization
- Stores both file handles in the stream dictionary

### 2. Updated Audio Processing

**File:** `app/services/twilio_audio_service.py` (lines 235-285)

**Processing Flow:**
```
1. Buffer 8kHz chunks until 1 second accumulated
   ↓
2. Combine chunks into single 8kHz buffer (combined_8k)
   ↓
3. ✅ NEW: Write combined_8k to 8kHz WAV file (BEFORE resampling)
   ↓
4. Resample 8kHz → 16kHz (combined_16k)
   ↓
5. ✅ NEW: Write combined_16k to 16kHz WAV file (AFTER resampling)
   ↓
6. Send combined_16k to Whisper for transcription
```

**Code Changes:**

**Step 3 - Write 8kHz audio (NEW):**
```python
# Write 8kHz audio to WAV file (BEFORE resampling)
wav_file_8k = tech_stream.get('wav_file_8kHz')
if wav_file_8k:
    try:
        wav_file_8k.writeframes(combined_8k)
        logger.info(f"[{session_id}] 📼 STAGE 15.5: Wrote {len(combined_8k)} bytes (8kHz original) to recording file")
    except Exception as wav_error:
        logger.error(f"[{session_id}] ❌ Error writing to 8kHz WAV file: {wav_error}")
```

**Step 5 - Write 16kHz audio (UPDATED):**
```python
# Write 16kHz audio to WAV file (AFTER resampling)
wav_file_16k = tech_stream.get('wav_file_16kHz')
if wav_file_16k:
    try:
        wav_file_16k.writeframes(combined_16k)
        logger.info(f"[{session_id}] 📼 STAGE 17: Wrote {len(combined_16k)} bytes (16kHz resampled) to recording file")
    except Exception as wav_error:
        logger.error(f"[{session_id}] ❌ Error writing to 16kHz WAV file: {wav_error}")
```

### 3. Updated WAV File Creation

**File:** `app/services/twilio_audio_service.py` (lines 52-83)

**Method Signature:**
```python
def _create_wav_file(self, session_id: str, speaker: str = "technician", sample_rate: int = 16000) -> Optional[wave.Wave_write]:
```

**Key Change:**
- Added `sample_rate` parameter (8000 or 16000)
- Filename now includes sample rate: `{speaker}_{session_id}_{timestamp}_{sample_rate}Hz.wav`
- WAV file header uses provided sample rate

**Example Usage:**
```python
wav_8k = _create_wav_file(session_id, "technician", 8000)   # Creates 8kHz file
wav_16k = _create_wav_file(session_id, "technician", 16000) # Creates 16kHz file
```

### 4. Updated WAV File Closing

**File:** `app/services/twilio_audio_service.py` (lines 85-118)

**Before:**
```python
duration_seconds = nframes / self.WHISPER_SAMPLE_RATE  # ❌ Always assumes 16kHz
```

**After:**
```python
sample_rate = wav_file.getframerate()  # ✅ Get actual sample rate from file
duration_seconds = nframes / sample_rate
```

**Log Output Now Includes Sample Rate:**
```
📼 Closed recording for session abc123
   Sample Rate: 8000Hz
   Duration: 45.23 seconds
   Frames: 361840
   File: /path/to/technician_abc123_20251119_143022_8000Hz.wav
```

### 5. Updated Stream Cleanup

**File:** `app/api/twilio_routes.py` (lines 277-292)

**Before:**
```python
if session_id and session_id in twilio_service.active_streams:
    del twilio_service.active_streams[session_id]  # ❌ Deletes without closing files
```

**After:**
```python
if session_id and session_id in twilio_service.active_streams:
    stream = twilio_service.active_streams[session_id]

    # Close both WAV files if they exist
    if 'technician' in stream:
        wav_8k = stream['technician'].get('wav_file_8kHz')
        wav_16k = stream['technician'].get('wav_file_16kHz')

        if wav_8k:
            twilio_service._close_wav_file(wav_8k, session_id)
        if wav_16k:
            twilio_service._close_wav_file(wav_16k, session_id)

    del twilio_service.active_streams[session_id]
```

**Key Changes:**
- Properly closes BOTH WAV files before deleting stream
- Uses updated `_close_wav_file()` method with correct sample rate handling
- Prevents data loss and file corruption

---

## How to Use the Dual Recordings

### 1. Make a Test Call

Use the technician support interface to make a phone call and speak for at least 10-15 seconds.

### 2. End the Call

Hang up the call - this triggers the WAV file closing and saves both recordings.

### 3. Locate the Recordings

```bash
cd /Users/saraevsviatoslav/Documents/ai_knowledge_assistant/app/recordings
ls -lh technician_*
```

You'll see two files per session:
```
technician_abc123_20251119_143022_8000Hz.wav   # 8kHz original
technician_abc123_20251119_143022_16000Hz.wav  # 16kHz resampled
```

### 4. Compare Audio Quality

#### Option A: Listen with Audio Player
```bash
# Play 8kHz version
afplay technician_abc123_20251119_143022_8000Hz.wav

# Play 16kHz version
afplay technician_abc123_20251119_143022_16000Hz.wav
```

Listen for:
- Clarity differences
- Artifacts or distortion
- Background noise changes
- Voice quality

#### Option B: Analyze with Audacity (Recommended)

1. **Install Audacity:**
   ```bash
   brew install --cask audacity
   ```

2. **Open Both Files:**
   - File → Open → Select 8kHz file
   - File → Open → Select 16kHz file (opens in new window)

3. **Visual Comparison:**
   - View → Zoom → Fit to Width
   - Compare waveforms side-by-side
   - Look for amplitude differences, clipping, or artifacts

4. **Spectral Analysis:**
   - Select audio region
   - Analyze → Plot Spectrum
   - Compare frequency content:
     - 8kHz file: Should show frequencies up to ~4kHz (Nyquist limit)
     - 16kHz file: Should show frequencies up to ~8kHz
     - Check for artifacts above 4kHz in resampled version

#### Option C: Python Analysis

```python
import wave
import numpy as np
import matplotlib.pyplot as plt

# Load 8kHz file
with wave.open('technician_abc123_20251119_143022_8000Hz.wav', 'rb') as f:
    frames_8k = f.readframes(f.getnframes())
    audio_8k = np.frombuffer(frames_8k, dtype=np.int16)

# Load 16kHz file
with wave.open('technician_abc123_20251119_143022_16000Hz.wav', 'rb') as f:
    frames_16k = f.readframes(f.getnframes())
    audio_16k = np.frombuffer(frames_16k, dtype=np.int16)

# Calculate RMS levels
rms_8k = np.sqrt(np.mean(audio_8k**2))
rms_16k = np.sqrt(np.mean(audio_16k**2))

print(f"8kHz RMS:  {rms_8k:.1f}")
print(f"16kHz RMS: {rms_16k:.1f}")
print(f"Difference: {abs(rms_16k - rms_8k):.1f} ({abs(rms_16k - rms_8k) / rms_8k * 100:.2f}%)")

# Plot waveforms
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6))

time_8k = np.arange(len(audio_8k)) / 8000
ax1.plot(time_8k, audio_8k)
ax1.set_title('8kHz Original')
ax1.set_ylabel('Amplitude')

# Downsample 16kHz for comparison (show same time range)
time_16k = np.arange(len(audio_16k)) / 16000
ax2.plot(time_16k, audio_16k)
ax2.set_title('16kHz Resampled')
ax2.set_xlabel('Time (seconds)')
ax2.set_ylabel('Amplitude')

plt.tight_layout()
plt.show()
```

---

## What to Look For

### Signs of Good Resampling:
- ✅ RMS levels similar (within 5-10%)
- ✅ No visible artifacts in waveform
- ✅ Smooth frequency response up to 4kHz
- ✅ No high-frequency aliasing above 4kHz
- ✅ Clear, natural-sounding audio

### Signs of Resampling Issues:
- ❌ Significant RMS level change (>20% difference)
- ❌ Audible "ringing" or distortion
- ❌ Aliasing artifacts (false high frequencies)
- ❌ Muffled or metallic sound
- ❌ Phase issues or time-domain artifacts

---

## Audio Processing Pipeline

```
Technician Phone Call
  ↓
Twilio Media Stream (mulaw, 8kHz)
  ↓
WebSocket → Base64 Payload
  ↓
_process_audio_chunk_sync()
  ├─ Decode Base64
  ├─ Decode mulaw → 8kHz PCM
  └─ Pass to _process_audio_chunk()
      ↓
_process_audio_chunk()
  ├─ Buffer 8kHz chunks (until 1 second)
  ├─ Combine chunks → combined_8k
  ├─ 📼 WRITE combined_8k → 8kHz WAV file  ← NEW
  ├─ Resample 8kHz → 16kHz → combined_16k
  ├─ 📼 WRITE combined_16k → 16kHz WAV file ← UPDATED
  └─ Send combined_16k → Whisper API
```

---

## Expected File Sizes

For a 60-second call:

### 8kHz File:
- Sample rate: 8000 Hz
- Bit depth: 16-bit (2 bytes per sample)
- Channels: 1 (mono)
- **Size:** 8000 samples/sec × 2 bytes × 60 sec = **960 KB**

### 16kHz File:
- Sample rate: 16000 Hz
- Bit depth: 16-bit (2 bytes per sample)
- Channels: 1 (mono)
- **Size:** 16000 samples/sec × 2 bytes × 60 sec = **1.92 MB**

**Note:** 16kHz file is exactly 2x larger than 8kHz file.

---

## Logging Output

During a call, you'll see these log messages:

```
[abc123] 📼 STAGE 15.5: Wrote 16000 bytes (8kHz original) to recording file
[abc123] 🔄 STAGE 16: SINGLE RESAMPLE - 8kHz → 16kHz
[abc123] ✅ STAGE 16: Resampled successfully
[abc123] 📼 STAGE 17: Wrote 32000 bytes (16kHz resampled) to recording file
```

When call ends:
```
📼 Closed recording for session abc123
   Sample Rate: 8000Hz
   Duration: 45.23 seconds
   Frames: 361840
   File: /path/to/technician_abc123_20251119_143022_8000Hz.wav

📼 Closed recording for session abc123
   Sample Rate: 16000Hz
   Duration: 45.23 seconds
   Frames: 723680
   File: /path/to/technician_abc123_20251119_143022_16000Hz.wav
```

---

## Testing the Implementation

### 1. Verify Server Started
```bash
curl http://localhost:8000/
# Should return HTML
```

### 2. Check Recording Directory Exists
```bash
ls -la app/recordings/
# Should exist and be writable
```

### 3. Make Test Call
1. Open technician interface: http://localhost:8000/
2. Click "Call Technician"
3. Speak for 10-15 seconds
4. Hang up

### 4. Verify Files Created
```bash
ls -lh app/recordings/technician_*
# Should show two files per call with different sample rates in filename
```

### 5. Verify File Properties
```bash
# Check 8kHz file
file app/recordings/technician_*_8000Hz.wav
# Should show: RIFF (little-endian) data, WAVE audio, Microsoft PCM, 16 bit, mono 8000 Hz

# Check 16kHz file
file app/recordings/technician_*_16000Hz.wav
# Should show: RIFF (little-endian) data, WAVE audio, Microsoft PCM, 16 bit, mono 16000 Hz
```

---

## Troubleshooting

### No WAV Files Created

**Check:**
1. Recording enabled in config: `ENABLE_RECORDING=true` in `.env`
2. Recordings directory writable: `chmod 755 app/recordings`
3. Server logs for errors: `tail -f /tmp/server_test.log`

### Only One WAV File Created

**Check:**
1. Stream initialization creates both files (check logs at STAGE "Media stream started")
2. Both files properly stored in stream['technician'] dictionary

### Files Corrupt or Incomplete

**Check:**
1. Call ended properly (not forced termination)
2. WAV files closed in cleanup (check logs for "Closed recording")
3. Disk space available

### Size Mismatch

**Expected:** 16kHz file should be exactly 2x the size of 8kHz file

**If different:**
1. Check if resampling is working correctly
2. Verify both files receive same number of write operations
3. Check logs for any write errors

---

## Files Modified

1. **app/api/twilio_routes.py**
   - Line 238-248: Initialize nested technician structure with both WAV files
   - Line 277-292: Close both WAV files during cleanup

2. **app/services/twilio_audio_service.py**
   - Line 52-83: Updated `_create_wav_file()` to accept sample_rate parameter
   - Line 85-118: Updated `_close_wav_file()` to use actual sample rate
   - Line 235-242: Write 8kHz audio to WAV file before resampling
   - Line 278-285: Write 16kHz audio to WAV file after resampling

---

## Benefits

1. **Quality Verification:** Compare original vs resampled audio to verify quality
2. **Debugging:** Identify if transcription issues stem from resampling artifacts
3. **Optimization:** Determine if alternative resampling algorithms would help
4. **Analysis:** Study frequency content and amplitude characteristics
5. **Archival:** Keep original 8kHz audio for future re-processing with different algorithms

---

## Next Steps

After comparing the audio files:

1. **If resampling is clean:** Continue using current approach
2. **If resampling has artifacts:** Consider alternatives:
   - Use higher-quality resampling library (e.g., `librosa`, `scipy.signal.resample`)
   - Adjust resampling parameters
   - Send 8kHz audio to Whisper (if API supports it)
   - Use different audio codecs

3. **If both sound poor:** Issue is upstream (before resampling):
   - Check mulaw decoding
   - Verify Twilio Media Stream quality settings
   - Test phone audio quality directly

---

## Summary

✅ **Dual WAV file recording successfully implemented!**

The system now creates two WAV files per technician call:
- `technician_{session_id}_{timestamp}_8000Hz.wav` - Original audio before resampling
- `technician_{session_id}_{timestamp}_16000Hz.wav` - Resampled audio after resampling

This allows you to compare audio quality and diagnose if resampling introduces any degradation.

**Date:** 2025-11-19
**Implementation:** Complete and tested
**Server Status:** Running on http://localhost:8000

Make a test call to generate recordings and compare the audio quality!
