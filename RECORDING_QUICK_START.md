# Audio Recording Quick Start Guide

## TL;DR

Recording is **enabled by default**. Files are saved to `audio_recordings/` automatically.

## How to Use

### 1. Make a Call (Recording Happens Automatically)

```bash
# Start the application
python main.py

# Make a test call from your phone
# Speak clearly for 10-30 seconds
# End the call
```

### 2. Check Recordings

```bash
# List all recordings
ls -lh audio_recordings/

# Example output:
# -rw-r--r-- 1 user staff 1.1M Nov 10 23:30 technician_MZ123_20251110_223015.wav
```

### 3. Analyze Recording

```bash
# Basic analysis (shows RMS, duration, silence detection)
python analyze_recording.py audio_recordings/technician_*.wav

# With waveform visualization
python analyze_recording.py audio_recordings/technician_*.wav --plot

# Test transcription with Whisper
python analyze_recording.py audio_recordings/technician_*.wav --transcribe
```

## What to Look For

### ✅ Good Recording
```
RMS Level: 1021.9
Status: GOOD - Normal speech range
Speech windows: 13 / 34 (38.2%)
```
- RMS between 500-2000
- Speech percentage > 30%
- No clipping

### ⚠️ Problem: Too Quiet
```
RMS Level: 45.3
Status: QUIET - Below technician threshold (100)
```
**Solution:** Ask technician to speak louder or use better microphone

### ⚠️ Problem: Mostly Silence
```
Silent windows: 32 / 34 (94.1%)
Status: HIGH silence percentage
```
**Solution:** Verify microphone is working, check if call is connected

### ⚠️ Problem: Clipping
```
RMS Level: 5234.7
Status: VERY LOUD - Possible clipping
Max Amplitude: 32767
```
**Solution:** Reduce input volume

## Log Messages

### Recording Started
```
📼 Created recording file: audio_recordings/technician_MZ123_20251110_223015.wav
📼 STAGE 5: Recording enabled for session MZ123
```

### Recording Ended
```
📼 Closed recording for session MZ123
   Duration: 34.85 seconds
   Frames: 557612
   File: audio_recordings/technician_MZ123_20251110_223015.wav
```

## Common Issues

### No recording file created?

**Check:**
```bash
# 1. Directory exists?
ls -la audio_recordings/

# 2. Recording enabled in logs?
grep "Audio recording ENABLED" logs.txt

# 3. Did call actually connect?
grep "STAGE 4: STREAM START" logs.txt
```

### File is very small (< 100 KB)?

**Cause:** Call ended too quickly or no audio received

**Check:**
```bash
# Verify call duration in logs
grep "Duration:" logs.txt
```

### Can't analyze recording?

**Check dependencies:**
```bash
pip install numpy  # Required for analysis
pip install matplotlib  # Optional, for --plot
pip install openai  # Optional, for --transcribe
```

## Disable Recording

If you don't want to record audio:

```python
# In app/services/twilio_audio_service.py, line ~485
_twilio_service = TwilioAudioService(
    account_sid=settings.account_sid,
    auth_token=settings.auth_token,
    phone_number=settings.phone_number,
    enable_recording=False  # Add this line
)
```

## Clean Up Old Recordings

```bash
# Delete all recordings
rm audio_recordings/*.wav

# Delete recordings older than 7 days
find audio_recordings/ -name "*.wav" -mtime +7 -delete

# Check disk usage
du -sh audio_recordings/
```

## File Format Details

- **Format:** WAV (PCM uncompressed)
- **Sample Rate:** 16,000 Hz
- **Bit Depth:** 16-bit signed integer
- **Channels:** Mono
- **Size:** ~1.9 MB per minute

## Real Test Example

From the test call that just ran:

```
File: technician_MZbbae7a3997c63f0ee252d2bd738901cd_20251110_223015.wav
Duration: 34.85 seconds
Size: 1.06 MB
RMS: 1021.9 (GOOD)
Speech: 38.2%
Status: ✓ Audio should transcribe well
```

This indicates:
- ✅ Recording working correctly
- ✅ Audio quality is good
- ✅ RMS level is in normal speech range
- ✅ Reasonable speech-to-silence ratio
- ✅ Should transcribe successfully

## Next Steps

1. **Debug transcription issues:** If transcriptions are empty, analyze the recording to check RMS levels
2. **Compare phones:** Record from different devices and compare RMS levels
3. **Test environments:** Record in quiet vs noisy locations
4. **Quality assurance:** Build a library of test recordings with known content

## Documentation

- **Full Guide:** [AUDIO_RECORDING_GUIDE.md](AUDIO_RECORDING_GUIDE.md)
- **Implementation:** [AUDIO_RECORDING_IMPLEMENTATION.md](AUDIO_RECORDING_IMPLEMENTATION.md)
- **Pipeline Logging:** [TECHNICIAN_AUDIO_LOGGING_GUIDE.md](TECHNICIAN_AUDIO_LOGGING_GUIDE.md)
