# Voice Recording Status

## Current Status: ✅ ENABLED

Voice recording is **already enabled** and configured to save dual WAV files.

---

## Configuration

### Recording Enabled
- **Default:** `enable_recording=True` (hardcoded in TwilioAudioService)
- **Status:** ✅ Active
- **No .env variable needed** - enabled by default

### Recordings Directory
- **Path:** `/Users/saraevsviatoslav/Documents/ai_knowledge_assistant/audio_recordings/`
- **Status:** ✅ Created and ready
- **Created:** 2025-11-20 15:38

### Dual WAV Recording
As implemented in the recent update, each call creates **two WAV files**:

1. **8kHz WAV** - Original audio before resampling
   - Format: `technician_{session_id}_{timestamp}_8000Hz.wav`
   - Purpose: Original phone audio quality

2. **16kHz WAV** - Resampled audio for Whisper
   - Format: `technician_{session_id}_{timestamp}_16000Hz.wav`
   - Purpose: Processed audio after resampling

---

## How Recording Works

### Automatic Recording Flow

```
1. Call Initiated
   ↓
2. Media Stream Starts (Twilio WebSocket connects)
   ↓
3. Stream Initialization (twilio_routes.py:490-499)
   - Creates TWO WAV files automatically:
     - wav_file_8kHz (8000 Hz)
     - wav_file_16kHz (16000 Hz)
   ↓
4. Audio Processing (_process_audio_chunk)
   - Buffers audio until 1 second
   - Writes to 8kHz WAV file (before resampling)
   - Resamples 8kHz → 16kHz
   - Writes to 16kHz WAV file (after resampling)
   ↓
5. Call Ends
   - Both WAV files closed automatically
   - Statistics logged
```

### File Locations

After making a call, files will appear in:
```bash
audio_recordings/
├── technician_abc123_20251120_153045_8000Hz.wav
└── technician_abc123_20251120_153045_16000Hz.wav
```

---

## Verify Recording is Working

### Method 1: Check Directory Exists
```bash
ls -la audio_recordings/
# Should show directory created at 15:38
```

### Method 2: Make a Test Call
1. Open: http://localhost:8000/
2. Click "Call Technician"
3. Speak for 10-15 seconds
4. Hang up
5. Check files:
```bash
ls -lh audio_recordings/technician_*
```

### Method 3: Check Server Logs
During call, look for these log messages:
```
📼 Created recording file: .../technician_{session}_8000Hz.wav
📼 Created recording file: .../technician_{session}_16000Hz.wav
📼 STAGE 15.5: Wrote {bytes} bytes (8kHz original) to recording file
📼 STAGE 17: Wrote {bytes} bytes (16kHz resampled) to recording file
📼 Closed recording for session {session}
```

---

## Recording Configuration Options

### Current Configuration (Default)
```python
# app/services/twilio_audio_service.py (line 32)
def __init__(self, account_sid: str, auth_token: str, phone_number: str, enable_recording: bool = True):
    ...
    self.enable_recording = enable_recording  # ← True by default
    self.recordings_dir = Path("audio_recordings")
```

### To Disable Recording (if needed)

**Option 1: Modify initialization** (app/services/twilio_audio_service.py:605-609)
```python
_twilio_service = TwilioAudioService(
    account_sid=settings.account_sid,
    auth_token=settings.auth_token,
    phone_number=settings.phone_number,
    enable_recording=False  # ← Add this line
)
```

**Option 2: Add environment variable support**

Add to `app/config/twilio_config.py`:
```python
class TwilioSettings:
    # ... existing fields ...
    enable_recording: bool = True  # Add this

    @classmethod
    def from_env(cls) -> "TwilioSettings":
        return cls(
            # ... existing fields ...
            enable_recording=os.getenv("ENABLE_RECORDING", "true").lower() == "true"
        )
```

Then use in initialization:
```python
_twilio_service = TwilioAudioService(
    account_sid=settings.account_sid,
    auth_token=settings.auth_token,
    phone_number=settings.phone_number,
    enable_recording=settings.enable_recording  # From config
)
```

---

## Recording Features

### ✅ Currently Active

1. **Dual WAV Recording**
   - Saves both 8kHz (original) and 16kHz (resampled)
   - Allows quality comparison

2. **Automatic File Creation**
   - Created when call starts
   - No manual intervention needed

3. **Proper Cleanup**
   - Files closed when call ends
   - Statistics logged

4. **Sample Rate in Filename**
   - Easy identification: `_8000Hz.wav` vs `_16000Hz.wav`
   - No confusion about which file is which

5. **Technician Audio Only**
   - Currently records phone call audio (technician)
   - Agent audio can be added if needed

### 📋 Available But Not Yet Implemented

1. **Agent Audio Recording**
   - Can record browser microphone audio
   - Would need WAV file creation in agent stream handler

2. **Recording Statistics**
   - Duration, file size, RMS levels
   - Currently logged but not stored in database

3. **Recording Playback Interface**
   - Web UI to listen to recordings
   - Would be a nice addition

---

## Expected File Sizes

For a **60-second call**:

### 8kHz File
- Sample rate: 8000 Hz
- Bit depth: 16-bit (2 bytes)
- Channels: 1 (mono)
- **Size:** 8000 × 2 × 60 = **960 KB**

### 16kHz File
- Sample rate: 16000 Hz
- Bit depth: 16-bit (2 bytes)
- Channels: 1 (mono)
- **Size:** 16000 × 2 × 60 = **1.92 MB**

**Note:** 16kHz file should be exactly 2× larger than 8kHz file.

---

## Troubleshooting

### No WAV Files Created

**Check:**
1. ✅ Server running: `lsof -ti:8000`
2. ✅ Directory exists: `ls audio_recordings/`
3. ✅ Recording enabled: Check logs for "Audio recording ENABLED"
4. ✅ Made a call: Need to actually call to create files
5. ✅ Call duration: Speak for at least 1 second (buffering threshold)

### Directory Permission Error

```bash
chmod 755 audio_recordings/
```

### Files Not Closing

**Cause:** Server crashed before cleanup
**Solution:** Restart server - cleanup happens in `finally` block

---

## Testing Checklist

- [x] Server running on port 8000
- [x] `audio_recordings/` directory created
- [x] Dual WAV recording implemented
- [x] Voice endpoint restored (no more 404)
- [x] Timestamp bug fixed
- [ ] Make test call and verify files created
- [ ] Compare 8kHz vs 16kHz audio quality
- [ ] Verify file sizes match expectations

---

## Summary

✅ **Recording is ENABLED and ready to use**

**What's working:**
- Automatic dual WAV file creation (8kHz + 16kHz)
- Proper file naming with sample rate
- Automatic cleanup when call ends
- Recordings saved to `audio_recordings/` directory

**What's needed:**
- Make a test call to generate first recordings
- Verify audio quality by comparing 8kHz vs 16kHz files

**Next step:** Make a phone call and check the `audio_recordings/` directory for the generated WAV files!

---

**Date:** 2025-11-20
**Recording Status:** ✅ Enabled by default
**Directory:** `audio_recordings/`
**Format:** Dual WAV (8kHz original + 16kHz resampled)
