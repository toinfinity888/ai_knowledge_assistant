# Transcription Debugging Guide

## 🔍 Problem Diagnosis

The transcription system **IS WORKING** - the issue is with **audio quality**. Here's what happens:

### The Complete Flow ✅
1. ✅ Twilio WebSocket receives audio
2. ✅ Audio is decoded from mulaw to PCM
3. ✅ Audio chunks are buffered (3 seconds)
4. ✅ Whisper API is called
5. ✅ Whisper returns a transcription
6. ❌ **Transcription is filtered out as hallucination**

### Why Hallucinations Occur

When Whisper receives unclear audio (too quiet, noisy, or silence), it "hallucinates" common phrases:
- "Sous-titres réalisés para la communauté d'Amara.org" (subtitle credits)
- "Merci d'avoir regardé" (thanks for watching)
- Repeated bullets (•••)
- Music descriptions

**Your code correctly filters these out**, but this means no transcription appears when audio is poor.

## 🛠️ Changes Made

### 1. Debug Mode Enabled
File: app/services/enhanced_transcription_service.py line 56
```python
self.debug_show_hallucinations = True  # Shows all Whisper responses
```
**Result**: Hallucinations now appear with `[HALLUCINATION - AUDIO QUALITY ISSUE]` prefix

### 2. Audio Level Monitoring
File: app/services/twilio_audio_service.py lines 142-147
- Logs RMS (volume level) for every audio chunk
- Warns if audio is too quiet (RMS < 5) or clipping (RMS > 2500)

### 3. Better Error Messages
Hallucination warnings now include possible causes:
- Audio too quiet (check RMS levels)
- Mostly noise/silence
- Wrong audio track
- Microphone issues

## 📊 How to Debug

### Step 1: Check Server Logs
Start your server and look for these indicators:
```
# Good audio (normal RMS):
[session-123] 📊 Audio chunk: RMS=300.5, Max=2500

# Bad audio (too quiet):
[session-123] 📊 Audio chunk: RMS=2.1, Max=50
[session-123] ⚠️ WARNING: Very low audio level (RMS=2.1)

# Hallucination detected:
⚠️ WHISPER DIAGNOSTIC - Detected hallucination
🐛 DEBUG MODE: Returning hallucination for debugging
```

### Step 2: Check What's Being Transcribed
With debug mode enabled, you'll see:
```
[HALLUCINATION - AUDIO QUALITY ISSUE] Sous-titres réalisés para...
```
This tells you Whisper is working but audio quality is poor.

### Step 3: Run Diagnostic Test
```bash
python test_transcription_diagnostic.py
```

## 🎯 Common Issues & Solutions

### Issue 1: Audio Too Quiet
**Symptoms**: RMS < 100, hallucinations about subtitles
**Solutions**:
- Check microphone permissions
- Increase microphone volume
- Verify correct audio track is captured

### Issue 2: Wrong Audio Track
**Check**: app/api/twilio_routes.py line 378
```python
if track != 'inbound':  # Only process inbound (technician)
    continue
```

### Issue 3: Silence/Noise Only
**Symptoms**: RMS < 10, consistent hallucinations
**Solutions**:
- Verify technician is speaking
- Check browser audio input
- Test: navigator.mediaDevices.getUserMedia({audio: true})

## 🔧 Configuration

### Disable Debug Mode (Production)
```python
# enhanced_transcription_service.py line 56
self.debug_show_hallucinations = False
```

### Adjust Buffer Time (faster response)
```python
# enhanced_transcription_service.py lines 48-49
self.min_bytes_8k = 8000 * 2 * 2   # 2 seconds instead of 3
```

### Enable Audio Recording
```python
# twilio_audio_service.py line 42
self.enable_recording = True  # Save WAV files
```

## 📝 Quick Testing

1. Start server: `python main.py`
2. Make a test call
3. Look for RMS levels in logs
4. Check for hallucination warnings
5. Verify audio quality

## Expected RMS Levels
- **Good**: 100 - 1500
- **Too quiet**: < 50 
- **Clipping**: > 2500

---

**Summary**: Transcription works. Issue is audio quality. Debug mode now shows this clearly.
