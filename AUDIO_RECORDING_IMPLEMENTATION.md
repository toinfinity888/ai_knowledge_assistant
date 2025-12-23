# Audio Recording Implementation Summary

## Overview

Audio recording functionality has been successfully implemented to capture technician audio from Twilio phone calls for debugging and analysis purposes.

## What Was Implemented

### 1. Core Recording Functionality

**File:** [app/services/twilio_audio_service.py](app/services/twilio_audio_service.py)

#### Added Imports
- `wave` - For creating WAV files
- `os` and `pathlib.Path` - For file system operations

#### Modified `__init__` Method
- Added `enable_recording` parameter (default: `True`)
- Created `audio_recordings/` directory
- Added configuration logging

#### New Methods
1. **`_create_wav_file(session_id, speaker)`**
   - Creates WAV file with proper format (16kHz, 16-bit, mono)
   - Generates filename: `{speaker}_{session_id}_{timestamp}.wav`
   - Returns WAV file handle or None if disabled

2. **`_close_wav_file(wav_file, session_id)`**
   - Closes WAV file gracefully
   - Logs recording statistics (duration, frames, filename)
   - Handles errors during closing

#### Modified `_process_audio_chunk_sync` Method
- Added audio writing after Stage 11 (audio characteristics)
- Writes processed 16kHz PCM audio to WAV file
- Logs write operations (debug level)
- Handles write errors gracefully

### 2. Integration with Twilio Routes

**File:** [app/api/twilio_routes.py](app/api/twilio_routes.py)

#### Modified Stream Initialization (Stage 5)
- Creates WAV file when technician stream starts
- Stores `wav_file` handle in stream dictionary
- Logs recording status

#### Modified Cleanup (finally block)
- Closes WAV file when stream ends
- Ensures proper file cleanup even on errors

### 3. Documentation

Created comprehensive documentation:

1. **[AUDIO_RECORDING_GUIDE.md](AUDIO_RECORDING_GUIDE.md)**
   - Complete user guide for audio recording feature
   - File format specifications
   - Analysis techniques
   - Storage management
   - Troubleshooting guide
   - Privacy considerations

2. **[analyze_recording.py](analyze_recording.py)**
   - Python script for analyzing recorded WAV files
   - Features:
     - Audio metadata extraction
     - RMS level calculation
     - Silence detection
     - Amplitude statistics
     - Quality assessment
     - Waveform visualization (optional)
     - Whisper API transcription testing (optional)

## File Locations

```
ai_knowledge_assistant/
├── audio_recordings/                    # Recording output directory (auto-created)
│   └── technician_{session_id}_{timestamp}.wav
├── app/
│   ├── services/
│   │   └── twilio_audio_service.py     # Core recording logic
│   └── api/
│       └── twilio_routes.py            # Integration with Twilio streams
├── AUDIO_RECORDING_GUIDE.md            # User documentation
├── AUDIO_RECORDING_IMPLEMENTATION.md   # This file
└── analyze_recording.py                # Analysis tool
```

## How It Works

### Recording Flow

```
1. Twilio Call Starts
   ↓
2. Stream Initialization (Stage 5)
   - Create WAV file: technician_{session_id}_{timestamp}.wav
   - Store file handle in active_streams[session_id]['technician']['wav_file']
   ↓
3. Audio Processing Loop (Stage 7-11)
   - Receive audio from Twilio
   - Decode base64 → mulaw → PCM → resample to 16kHz
   - Write 16kHz PCM audio to WAV file
   - Continue processing for transcription
   ↓
4. Stream End (Cleanup)
   - Close WAV file
   - Log statistics (duration, frames)
   - Clean up resources
```

### Audio Format

**Input from Twilio:**
- Format: mulaw (8-bit compressed)
- Sample Rate: 8 kHz
- Channels: Mono
- Encoding: Base64-encoded

**Stored in WAV File:**
- Format: PCM (uncompressed)
- Sample Rate: 16 kHz
- Bit Depth: 16-bit
- Channels: Mono
- Same format used for Whisper transcription

## Usage Examples

### 1. Basic Usage (Recording Enabled by Default)

Just start the application and make calls - recordings will be created automatically:

```bash
python main.py
# Make a test call
# Check recordings: ls -la audio_recordings/
```

### 2. Disable Recording

Modify service initialization:

```python
# In get_twilio_service() function
_twilio_service = TwilioAudioService(
    account_sid=settings.account_sid,
    auth_token=settings.auth_token,
    phone_number=settings.phone_number,
    enable_recording=False  # Disable recording
)
```

### 3. Analyze Recordings

```bash
# Basic analysis
python analyze_recording.py audio_recordings/technician_MZ123_20251110.wav

# With waveform visualization
python analyze_recording.py audio_recordings/technician_MZ123_20251110.wav --plot

# Test transcription
python analyze_recording.py audio_recordings/technician_MZ123_20251110.wav --transcribe --language fr

# Analyze latest recording
python analyze_recording.py audio_recordings/technician_*.wav
```

## Log Messages

### Startup
```
Audio recording ENABLED - files will be saved to: /path/to/audio_recordings
TwilioAudioService initialized with phone +1234567890
```

### Stream Start (Stage 5)
```
📼 Created recording file: audio_recordings/technician_MZ123_20251110_143052.wav
✅ STAGE 5: Technician stream initialized in active_streams[MZ123]['technician']
📼 STAGE 5: Recording enabled for session MZ123
```

### During Recording (Debug Level)
```
📼 Wrote 720 bytes to recording file
```

### Stream End
```
📼 Closed recording for session MZ123
   Duration: 45.32 seconds
   Frames: 725120
   File: audio_recordings/technician_MZ123_20251110_143052.wav
Media stream closed for session MZ123
```

## Benefits

1. **Debugging Audio Issues**
   - Verify audio is being received from Twilio
   - Check audio quality and RMS levels
   - Identify silence vs speech segments
   - Detect clipping or distortion

2. **Transcription Troubleshooting**
   - Manually test audio with Whisper API
   - Compare live transcription vs manual transcription
   - Identify language detection issues
   - Analyze why transcriptions might be empty

3. **Quality Analysis**
   - Measure RMS levels across different calls
   - Compare different phones/microphones
   - Test in various acoustic environments
   - Optimize RMS thresholds based on real data

4. **Testing and Development**
   - Create test datasets with known content
   - Verify audio processing pipeline
   - Validate resampling and decoding
   - Benchmark transcription accuracy

## Storage Considerations

### File Sizes
- 1 minute: ~1.9 MB
- 5 minutes: ~9.5 MB
- 10 minutes: ~19 MB
- 1 hour: ~115 MB

### Management
```bash
# View recordings
ls -lh audio_recordings/

# Delete old recordings (example: older than 7 days)
find audio_recordings/ -name "*.wav" -mtime +7 -delete

# Check disk usage
du -sh audio_recordings/
```

## Technical Details

### WAV File Format
- **RIFF Header:** Standard WAV container
- **Format Chunk:** PCM, 16kHz, 16-bit, mono
- **Data Chunk:** Raw PCM samples
- **No compression:** Files are larger but highest quality

### Real-time Writing
- Audio is written incrementally as chunks arrive (~50 chunks/second)
- Each chunk is ~720 bytes (20-30ms of audio at 16kHz)
- File is flushed automatically by Python's wave module
- Partial recordings are usable even if process crashes

### Thread Safety
- WAV file handle stored per session
- Each session has independent recording
- No shared state between concurrent calls
- Safe for multiple simultaneous recordings

## Error Handling

### File Creation Errors
```python
try:
    wav_file = wave.open(filepath, 'wb')
except Exception as e:
    logger.error(f"Failed to create WAV file: {e}")
    return None  # Continue without recording
```

### Write Errors
```python
try:
    wav_file.writeframes(audio_data)
except Exception as e:
    logger.error(f"Error writing to WAV file: {e}")
    # Continue processing (don't crash)
```

### Close Errors
```python
try:
    wav_file.close()
except Exception as e:
    logger.error(f"Error closing WAV file: {e}")
    # Cleanup continues
```

## Privacy and Security

### Recommendations

1. **Data Protection**
   - Recordings contain customer voice data
   - Consider GDPR/privacy regulations
   - Implement retention policies
   - Secure storage location

2. **Access Control**
   - Restrict access to audio_recordings/ directory
   - Don't commit recordings to git (already in .gitignore)
   - Consider encryption for sensitive environments

3. **Production Use**
   - Disable recording in production unless debugging
   - Implement automatic cleanup (e.g., 7-day retention)
   - Log access to recordings
   - Document why recordings are needed

## Future Enhancements

Possible improvements:

1. **Configuration**
   - Environment variable to enable/disable: `ENABLE_AUDIO_RECORDING=true`
   - Configurable output directory
   - Configurable retention period

2. **Metadata**
   - Save JSON metadata alongside WAV files
   - Include session info, timestamps, RMS stats
   - Track transcription accuracy

3. **Cloud Storage**
   - Upload to S3/Cloud Storage
   - Automatic archival after X days
   - On-demand retrieval

4. **Agent Recording**
   - Also record agent audio from browser
   - Store in separate files or stereo WAV
   - Compare both sides of conversation

5. **Web Interface**
   - Browse recordings in UI
   - Play back in browser
   - Download or delete recordings
   - View analysis results

6. **Automatic Analysis**
   - Run analyze_recording.py automatically after each call
   - Store analysis results in database
   - Alert on quality issues (low RMS, high silence, etc.)

## Testing

### Manual Testing

1. Start the application:
```bash
python main.py
```

2. Make a test call from a phone

3. Speak clearly for 10-15 seconds

4. End the call

5. Check recordings:
```bash
ls -lh audio_recordings/
```

6. Analyze the recording:
```bash
python analyze_recording.py audio_recordings/technician_*.wav --plot --transcribe
```

7. Verify:
   - File exists and has reasonable size
   - Duration matches call duration
   - RMS levels are in normal range (500-2000)
   - Transcription works correctly

### Automated Testing

```python
# test_audio_recording.py
import wave
from pathlib import Path
from app.services.twilio_audio_service import TwilioAudioService

def test_create_wav_file():
    service = TwilioAudioService("sid", "token", "phone", enable_recording=True)
    wav_file = service._create_wav_file("test_session", "technician")

    assert wav_file is not None
    assert Path("audio_recordings/technician_test_session_*.wav").exists()

    service._close_wav_file(wav_file, "test_session")

def test_recording_disabled():
    service = TwilioAudioService("sid", "token", "phone", enable_recording=False)
    wav_file = service._create_wav_file("test_session", "technician")

    assert wav_file is None
```

## Troubleshooting

### Issue: Directory not created

**Solution:**
```bash
mkdir -p audio_recordings
chmod 755 audio_recordings
```

### Issue: Permission denied

**Solution:**
```bash
# Check permissions
ls -ld audio_recordings/

# Fix permissions
chmod 755 audio_recordings/
```

### Issue: File not found after call

**Check:**
1. Was recording enabled? Look for startup message
2. Did stream initialize? Check Stage 5 logs
3. Was there an error creating file? Check error logs
4. Did call actually connect? Verify Twilio status

### Issue: Empty or corrupted file

**Possible causes:**
1. Call ended before audio was received
2. Process crashed before cleanup
3. Disk full or write errors

**Solution:**
- Check logs for write errors
- Verify disk space: `df -h`
- Ensure proper cleanup (look for "Closed recording" message)

## Summary

✅ **Implemented:**
- Automatic recording of technician audio from Twilio calls
- WAV file creation (16kHz, 16-bit, mono)
- Real-time audio writing during calls
- Proper cleanup and statistics logging
- Analysis tool for recorded files
- Comprehensive documentation

✅ **Features:**
- Enabled by default for easy debugging
- Can be disabled via configuration
- Logs all operations for troubleshooting
- Error handling prevents crashes
- Compatible with Whisper API format

✅ **Documentation:**
- User guide (AUDIO_RECORDING_GUIDE.md)
- Implementation details (this file)
- Analysis tool (analyze_recording.py)
- Usage examples and troubleshooting

The recording system is ready to use for debugging audio quality issues and transcription problems!
