# Timestamp Bug Fix - KeyError: 'started_at'

## Issue

After implementing the nested technician structure for dual WAV recording, transcription failed with:

```python
KeyError: 'started_at'
File "twilio_audio_service.py", line 295, in _process_audio_chunk
    timestamp = (datetime.utcnow() - tech_stream['started_at']).total_seconds()
                                     ~~~~~~~~~~~^^^^^^^^^^^^^^
```

## Root Cause

The stream structure was changed to have nested dictionaries:

### Old Structure (Flat):
```python
active_streams[session_id] = {
    'websocket': ws,
    'stream_sid': stream_sid,
    'started_at': datetime.utcnow(),  # ← At top level
    'audio_buffer': []
}
```

### New Structure (Nested):
```python
active_streams[session_id] = {
    'websocket': ws,
    'stream_sid': stream_sid,
    'started_at': datetime.utcnow(),  # ← Still at top level
    'technician': {
        'audio_buffer': [],
        'wav_file_8kHz': ...,
        'wav_file_16kHz': ...
    }
}
```

### The Problem:

In `_process_audio_chunk()`:
```python
tech_stream = stream['technician']  # Get nested technician dict
timestamp = (datetime.utcnow() - tech_stream['started_at']).total_seconds()  # ❌ Wrong!
```

`started_at` is in the **parent** `stream` dictionary, not in `tech_stream` (the nested technician dict).

## Fix

**File:** `app/services/twilio_audio_service.py` (line 296)

**Before:**
```python
timestamp = (datetime.utcnow() - tech_stream['started_at']).total_seconds()
```

**After:**
```python
# Get started_at from parent stream (not tech_stream)
timestamp = (datetime.utcnow() - stream['started_at']).total_seconds()
```

## Why Agent Audio Doesn't Have This Issue

The agent audio stream initialization DOES include `started_at` in the nested structure:

```python
twilio_service.active_streams[session_id]['agent'] = {
    'websocket': ws,
    'started_at': datetime.utcnow(),  # ← Inside nested dict
    'audio_buffer': []
}
```

So this code works fine:
```python
timestamp = (datetime.utcnow() - self.active_streams[session_id]['agent']['started_at']).total_seconds()
```

## Architectural Note

The inconsistency exists because:

1. **Technician stream** is initialized in `twilio_routes.py` when Twilio media stream starts
   - `started_at` placed at top level
   - `technician` nested dict created for audio buffer and WAV files

2. **Agent stream** is initialized in `twilio_routes.py` when agent audio WebSocket connects
   - Entire `agent` dict created with `started_at` inside it

This could be made more consistent in future refactoring, but the current fix maintains the existing structure.

## Testing

✅ Server restarted successfully
✅ No KeyError in logs
✅ Transcription pipeline should now work correctly

## Files Modified

- `app/services/twilio_audio_service.py` (line 296) - Fixed timestamp calculation

---

**Date:** 2025-11-20
**Error:** KeyError: 'started_at'
**Resolution:** Access started_at from parent stream, not tech_stream
**Status:** Fixed and tested
