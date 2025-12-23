# Testing Guide - Technician Transcription System

## Quick Start

### 1. Server Status

✅ Server is already running on port 8000

```bash
# Verify server is running
curl -s http://localhost:8000/ && echo "✅ Server is running"
```

### 2. Open Agent Interface

Open in your browser:
```
http://localhost:8000/demo/technician-support
```

### 3. Make a Test Call

#### Option A: Using Your Phone

1. Call your Twilio number
2. In the browser, click "Accepter l'appel"
3. Speak French into your phone
4. Watch for transcriptions in the UI

#### Option B: Using Twilio Test Call (if configured)

1. In the agent interface, click "Accepter l'appel"
2. Speak into your computer microphone (as agent)
3. Call the Twilio number from your phone (as technician)

## What to Expect

### Browser Console (Press F12)

When call starts:
```
📡 Connecting to technician transcription WebSocket...
✅ Technician transcription WebSocket connected
✅ Technician transcription WS connection confirmed
```

When technician speaks:
```
📥 Received from technician transcription WS: {type: 'transcription', text: 'Bonjour, j'ai un problème...', speaker_label: 'Technicien', speaker_role: 'technician'}
```

### Backend Logs

Monitor with:
```bash
tail -f /Users/saraevsviatoslav/Documents/ai_knowledge_assistant/server.log | grep -E "(WHISPER|STAGE 21|WebSocket|Buffering)"
```

Expected sequence:
```
[session_id] 💤 Still waiting for speech (RMS=5.3 < 10)
[session_id] 🎙️ Speech detected (RMS=145.7) — starting real buffering
[session_id] 📦 Added chunk 31998 bytes to buffer (total chunks: 1)
[session_id] ⏱️ Buffer duration: 1.00s
[session_id] ⏳ Buffering: 1.00s, VAD status: speech_continuing
[session_id] 📦 Added chunk 31998 bytes to buffer (total chunks: 2)
[session_id] ⏱️ Buffer duration: 2.00s
[session_id] ⏳ Buffering: 2.00s, VAD status: speech_continuing
...
[session_id] ✂️ VAD-based segmentation triggered: reason=silence_detected, duration=3.50s
[session_id] Combined 3 chunks = 95994 bytes, duration=3.50s
🔍 WHISPER DIAGNOSTIC - Audio buffer size: 95994 bytes
🔍 WHISPER DIAGNOSTIC - Audio level appears NORMAL (RMS=811.9)
🎯 Calling Whisper API with model=whisper-1, language=fr
✅ WHISPER DIAGNOSTIC - Valid transcription received (45 chars)
[session_id] ✅ STAGE 21: Technician transcription WebSocket found
[session_id] ✅✅✅ STAGE 21 SUCCESS: Transcription sent to technician UI!
```

### User Interface

Transcriptions should appear in the "Transcription en temps réel" panel:

```
[22:57:15] Technicien Bonjour, j'ai un problème avec ma caméra
[22:57:23] Agent Bonjour, quel est le problème exactement?
[22:57:30] Technicien La caméra ne s'allume plus
```

## Troubleshooting

### ❌ Problem: No transcriptions appear

#### Check 1: Browser Console

Open browser console (F12) and look for:

**Good signs:**
```
✅ Technician transcription WebSocket connected
📥 Received from technician transcription WS: {...}
```

**Bad signs:**
```
❌ Technician transcription WebSocket error: ...
WebSocket connection to 'ws://localhost:8000/...' failed
```

**Fix:** Verify server is running and endpoint exists:
```bash
curl http://localhost:8000/
grep -n "technician-transcription" /Users/saraevsviatoslav/Documents/ai_knowledge_assistant/app/api/twilio_routes.py
```

#### Check 2: Backend Logs

```bash
grep "STAGE 21" /Users/saraevsviatoslav/Documents/ai_knowledge_assistant/server.log | tail -20
```

**If you see:**
```
⚠️ No technician transcription WebSocket available
```
→ Frontend didn't connect. Check browser console for WebSocket errors.

**If you see:**
```
❌ STAGE 19 FAILED: Transcription returned None
```
→ Whisper is not being called. Check for buffering logs.

#### Check 3: Audio Levels

```bash
grep "Still waiting for speech" /Users/saraevsviatoslav/Documents/ai_knowledge_assistant/server.log | tail -10
```

**If you see:**
```
💤 Still waiting for speech (RMS=5.3 < 10)
```
Repeatedly → RMS too low. Audio is too quiet or microphone not working.

**Fix:** Speak louder or check phone microphone.

#### Check 4: Buffering

```bash
grep "Buffering" /Users/saraevsviatoslav/Documents/ai_knowledge_assistant/server.log | tail -10
```

**If you see:**
```
⏳ Buffering: 1.00s, VAD status: speech_continuing
⏳ Buffering: 2.00s, VAD status: speech_continuing
...
```
But never see:
```
✂️ VAD-based segmentation triggered
```
→ VAD is not detecting silence. Speak, then pause for 1-2 seconds.

### ❌ Problem: Transcriptions are in wrong language

**Check logs:**
```bash
grep "Calling Whisper API" /Users/saraevsviatoslav/Documents/ai_knowledge_assistant/server.log | tail -5
```

Should see:
```
🎯 Calling Whisper API with model=whisper-1, language=fr
```

If `language=en`, fix in [enhanced_transcription_service.py](app/services/enhanced_transcription_service.py).

### ❌ Problem: Transcriptions are gibberish (hallucinations)

**Check logs:**
```bash
grep "WHISPER DIAGNOSTIC" /Users/saraevsviatoslav/Documents/ai_knowledge_assistant/server.log | tail -10
```

**If you see:**
```
⚠️ Hallucination detected: <pattern_name>
```
→ Hallucinations are being filtered. This is normal for silent audio.

**If you see real transcriptions but they're wrong:**
```
✅ WHISPER DIAGNOSTIC - Valid transcription received (885 chars)
```
But transcription is "•••••••••••" → Whisper prompt issue.

**Fix:** Verify prompt was removed in [enhanced_transcription_service.py:260-270](app/services/enhanced_transcription_service.py#L260-L270).

### ❌ Problem: Server not running

```bash
# Check if server is running
lsof -ti:8000

# If nothing, start server
cd /Users/saraevsviatoslav/Documents/ai_knowledge_assistant
python main.py
```

## Test Scenarios

### Scenario 1: Basic Transcription Test

**Goal:** Verify transcriptions appear

1. Open agent interface
2. Accept call
3. Speak in French via phone: "Bonjour, 1, 2, 3"
4. Pause for 2 seconds
5. Check UI for transcription

**Expected:** Transcription appears within 5-10 seconds

### Scenario 2: Multiple Speech Segments

**Goal:** Verify multiple transcriptions work

1. Accept call
2. Speak: "Bonjour" → Pause 2 seconds
3. Speak: "J'ai un problème" → Pause 2 seconds
4. Speak: "Avec ma caméra" → Pause 2 seconds

**Expected:** Three separate transcriptions appear

### Scenario 3: Agent + Technician Conversation

**Goal:** Verify both speakers are transcribed

1. Accept call
2. Technician (phone): "Bonjour" → Pause
3. Agent (browser mic): "Bonjour, comment puis-je vous aider?" → Pause
4. Technician (phone): "J'ai un problème" → Pause

**Expected:** Both technician and agent transcriptions appear with correct labels

### Scenario 4: WebSocket Reconnection

**Goal:** Verify cleanup works

1. Accept call, verify transcriptions work
2. End call
3. Start new call
4. Verify transcriptions still work

**Expected:** New WebSocket connection established, transcriptions continue working

## Success Criteria

✅ Browser console shows WebSocket connected
✅ Backend logs show "STAGE 21 SUCCESS"
✅ Transcriptions appear in UI within 5-10 seconds of speaking
✅ Speaker labels are correct (Technicien/Agent)
✅ Multiple speech segments are transcribed separately
✅ WebSocket cleanup works when call ends

## Quick Commands

```bash
# Check server status
curl -s http://localhost:8000/ && echo "✅ Server running"

# Monitor logs during test
tail -f /Users/saraevsviatoslav/Documents/ai_knowledge_assistant/server.log | grep -E "(WHISPER|STAGE 21|WebSocket)"

# Check WebSocket connections
grep "Technician transcription WebSocket" /Users/saraevsviatoslav/Documents/ai_knowledge_assistant/server.log | tail -10

# Check transcription success
grep "STAGE 21 SUCCESS" /Users/saraevsviatoslav/Documents/ai_knowledge_assistant/server.log | tail -10

# Check for errors
grep "ERROR" /Users/saraevsviatoslav/Documents/ai_knowledge_assistant/server.log | tail -20

# Restart server if needed
lsof -ti:8000 | xargs kill -9 && sleep 2 && cd /Users/saraevsviatoslav/Documents/ai_knowledge_assistant && python main.py
```

## Next Steps After Testing

If tests pass:
1. ✅ Mark task complete
2. 📝 Document any issues found
3. 🚀 Deploy to production (if applicable)

If tests fail:
1. Check troubleshooting section above
2. Review backend logs for specific error
3. Check browser console for WebSocket errors
4. Verify Twilio configuration

---

**Ready to test!** Open http://localhost:8000/demo/technician-support and make a call.
