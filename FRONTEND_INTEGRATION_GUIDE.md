# Frontend Integration Guide - Technician Transcription WebSocket

## Problem Solved

**Root Cause:** Frontend was not connecting to receive technician transcriptions from the backend.

**Solution:** Created a dedicated WebSocket endpoint `/twilio/technician-transcription/<session_id>` for delivering technician transcriptions to the UI.

## Backend Changes (✅ COMPLETE)

1. **New WebSocket Endpoint** - [twilio_routes.py:659-716](app/api/twilio_routes.py#L659-L716)
   - Endpoint: `/twilio/technician-transcription/<session_id>`
   - Receives and stores the technician transcription WebSocket connection
   - Sends connection confirmation to frontend

2. **Updated Broadcasting Logic** - [twilio_audio_service.py:416-478](app/services/twilio_audio_service.py#L416-L478)
   - Sends technician transcriptions to the technician WebSocket (primary)
   - Also sends to agent WebSocket (secondary, so agent sees technician's speech)
   - Comprehensive logging for debugging

3. **All Other Fixes Applied:**
   - ✅ Whisper prompt removed (no hallucinations)
   - ✅ Hallucination detection added
   - ✅ DEBUG → INFO logging for visibility
   - ✅ RMS threshold lowered to 10
   - ✅ Comprehensive diagnostic logging

## Frontend Changes Required (🔴 TODO)

### Step 1: Find Your Frontend WebSocket Connection Code

Look for where you currently connect the agent audio WebSocket. It should look something like:

```javascript
// Example - your code may vary
const agentWsUrl = `${wsProtocol}//${window.location.host}/twilio/agent-audio-stream/${sessionId}`;
const agentWebSocket = new WebSocket(agentWsUrl);
```

### Step 2: Add Technician Transcription WebSocket Connection

**Add this code RIGHT AFTER the agent WebSocket connection:**

```javascript
// ================================================================================
// TECHNICIAN TRANSCRIPTION WEBSOCKET
// ================================================================================
// This WebSocket receives transcriptions of the technician's speech from backend
const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const technicianTranscriptionWsUrl = `${wsProtocol}//${window.location.host}/twilio/technician-transcription/${sessionId}`;

console.log('📡 Connecting to technician transcription WebSocket:', technicianTranscriptionWsUrl);

const technicianTranscriptionWs = new WebSocket(technicianTranscriptionWsUrl);

technicianTranscriptionWs.onopen = () => {
    console.log('✅ Technician transcription WebSocket connected');
};

technicianTranscriptionWs.onmessage = (event) => {
    try {
        const data = JSON.parse(event.data);
        console.log('📥 Received from technician transcription WS:', data);

        if (data.type === 'transcription') {
            // Display the transcription in your UI
            displayTranscription(data);
        } else if (data.event === 'connected') {
            console.log('✅ Technician transcription WS connection confirmed');
        }
    } catch (e) {
        console.error('❌ Error parsing technician transcription message:', e);
    }
};

technicianTranscriptionWs.onerror = (error) => {
    console.error('❌ Technician transcription WebSocket error:', error);
};

technicianTranscriptionWs.onclose = () => {
    console.log('Technician transcription WebSocket closed');
};
```

### Step 3: Update Your displayTranscription() Function

Make sure your `displayTranscription()` function handles the speaker role correctly:

```javascript
function displayTranscription(data) {
    const {
        text,
        speaker_label,  // "Technicien" or "Agent"
        speaker_role,   // "technician" or "agent"
        confidence,
        timestamp
    } = data;

    console.log(`💬 ${speaker_label}: ${text}`);

    // Create transcription element
    const transcriptionElement = document.createElement('div');
    transcriptionElement.className = `transcription transcription-${speaker_role}`;

    // Add speaker label
    const speakerLabel = document.createElement('span');
    speakerLabel.className = 'speaker-label';
    speakerLabel.textContent = speaker_label + ': ';

    // Add text
    const textSpan = document.createElement('span');
    textSpan.className = 'transcription-text';
    textSpan.textContent = text;

    transcriptionElement.appendChild(speakerLabel);
    transcriptionElement.appendChild(textSpan);

    // Add to transcription container
    const container = document.getElementById('transcriptions-container'); // Adjust to your container ID
    if (container) {
        container.appendChild(transcriptionElement);
        container.scrollTop = container.scrollHeight; // Auto-scroll
    }
}
```

### Step 4: Add CSS for Speaker Differentiation

Add styles to visually differentiate technician vs agent transcriptions:

```css
.transcription {
    margin: 8px 0;
    padding: 10px;
    border-radius: 8px;
    max-width: 80%;
}

.transcription-technician {
    background-color: #e3f2fd; /* Light blue for technician */
    margin-left: 0;
    margin-right: auto;
}

.transcription-agent {
    background-color: #f1f8e9; /* Light green for agent */
    margin-left: auto;
    margin-right: 0;
    text-align: right;
}

.speaker-label {
    font-weight: bold;
    color: #1976d2;
}

.transcription-technician .speaker-label {
    color: #1976d2; /* Blue for technician */
}

.transcription-agent .speaker-label {
    color: #558b2f; /* Green for agent */
}

.transcription-text {
    color: #333;
}
```

### Step 5: Close WebSocket on Cleanup

Make sure to close the WebSocket when the call ends:

```javascript
function endCall() {
    // Close technician transcription WebSocket
    if (technicianTranscriptionWs && technicianTranscriptionWs.readyState === WebSocket.OPEN) {
        technicianTranscriptionWs.send(JSON.dumps({event: 'close'}));
        technicianTranscriptionWs.close();
        console.log('Closed technician transcription WebSocket');
    }

    // ... other cleanup code ...
}
```

## Complete Frontend Example

Here's a complete example showing all pieces together:

```javascript
// ================================================================================
// CALL INITIALIZATION
// ================================================================================
let agentAudioWs = null;
let technicianTranscriptionWs = null;

function startCall(sessionId) {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';

    // 1. Connect Agent Audio WebSocket (for sending agent's microphone)
    const agentAudioWsUrl = `${wsProtocol}//${window.location.host}/twilio/agent-audio-stream/${sessionId}`;
    agentAudioWs = new WebSocket(agentAudioWsUrl);

    agentAudioWs.onopen = () => {
        console.log('✅ Agent audio WebSocket connected');
        // Start sending microphone audio...
    };

    // 2. Connect Technician Transcription WebSocket (for receiving transcriptions)
    const techTranscriptionWsUrl = `${wsProtocol}//${window.location.host}/twilio/technician-transcription/${sessionId}`;
    technicianTranscriptionWs = new WebSocket(techTranscriptionWsUrl);

    technicianTranscriptionWs.onopen = () => {
        console.log('✅ Technician transcription WebSocket connected');
    };

    technicianTranscriptionWs.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);

            if (data.type === 'transcription') {
                displayTranscription(data);
            } else if (data.event === 'connected') {
                console.log('✅ Technician transcription connection confirmed');
            }
        } catch (e) {
            console.error('❌ Error:', e);
        }
    };

    technicianTranscriptionWs.onerror = (error) => {
        console.error('❌ Technician transcription error:', error);
    };
}

function displayTranscription(data) {
    const { text, speaker_label, speaker_role } = data;

    console.log(`💬 ${speaker_label}: ${text}`);

    // Create and display transcription element
    const container = document.getElementById('transcriptions');
    if (container) {
        const div = document.createElement('div');
        div.className = `transcription transcription-${speaker_role}`;
        div.innerHTML = `<strong>${speaker_label}:</strong> ${text}`;
        container.appendChild(div);
        container.scrollTop = container.scrollHeight;
    }
}

function endCall() {
    // Close both WebSockets
    if (agentAudioWs) {
        agentAudioWs.close();
    }

    if (technicianTranscriptionWs) {
        technicianTranscriptionWs.send(JSON.stringify({event: 'close'}));
        technicianTranscriptionWs.close();
    }

    console.log('Call ended, WebSockets closed');
}
```

## Testing the Integration

### 1. Open Browser Console

Before making a call, open the browser developer console (F12) to see logs.

### 2. Start a Call

You should see:
```
📡 Connecting to technician transcription WebSocket: ws://localhost:8000/twilio/technician-transcription/MZ...
✅ Technician transcription WebSocket connected
✅ Technician transcription connection confirmed
```

### 3. Speak as Technician (via phone)

You should see in console:
```
📥 Received from technician transcription WS: {type: 'transcription', text: 'Bonjour...', speaker_label: 'Technicien', ...}
💬 Technicien: Bonjour, j'ai un problème avec...
```

And see the transcription appear in your UI!

### 4. Check Backend Logs

In the server terminal, you should see:
```
[2025-11-14 21:XX:XX] INFO - ✅ Technician transcription WebSocket connected for session MZ...
[2025-11-14 21:XX:XX] INFO - 📝 Registered technician transcription WebSocket for session MZ...
...
[MZ...] 💤 Still waiting for speech (RMS=5.3 < 10)
[MZ...] 🎙️ Speech detected (RMS=145.7) — starting real buffering
[MZ...] 📦 Added chunk 31998 bytes to buffer (total chunks: 1)
[MZ...] ⏱️ Buffer duration: 1.00s
[MZ...] ⏳ Buffering: 1.00s, VAD status: speech_continuing
...
[MZ...] ✂️ VAD-based segmentation triggered: reason=silence_detected, duration=3.50s
🔍 WHISPER DIAGNOSTIC - Audio level appears NORMAL (RMS=811.9)
✅ WHISPER DIAGNOSTIC - Valid transcription received (45 chars)
[MZ...] ✅ STAGE 21: Technician transcription WebSocket found
[MZ...] ✅✅✅ STAGE 21 SUCCESS: Transcription sent to technician UI!
```

## Troubleshooting

### Problem: WebSocket Connection Refused

**Check:**
- Is the backend server running on port 8000?
- Is `sessionId` correct in the URL?
- Browser console shows the exact URL being used

**Solution:**
```bash
# Verify server is running
curl http://localhost:8000/

# Check logs
tail -f ai_knowledge_assistant/server.log
```

### Problem: WebSocket Connects But No Transcriptions

**Check backend logs for:**
```
💤 Still waiting for speech (RMS=X.X < 10)
```
If you see this repeatedly, audio RMS is too low.

**Or:**
```
⏳ Buffering: X.XXs, VAD status: speech_continuing
```
If buffering never ends, VAD is not detecting silence.

**Or:**
```
⚠️ No technician transcription WebSocket available
```
Frontend didn't connect to the WebSocket endpoint.

### Problem: Transcriptions Appear But Wrong Speaker

**Check the `speaker_role` field:**
```javascript
console.log('Speaker role:', data.speaker_role); // Should be 'technician'
```

## Summary

✅ **Backend Complete:**
- WebSocket endpoint created
- Broadcasting logic updated
- All transcription fixes applied
- Server running with all changes

🔴 **Frontend TODO:**
1. Add technician transcription WebSocket connection
2. Update `displayTranscription()` to handle speaker roles
3. Add CSS for speaker differentiation
4. Test and verify transcriptions appear

**After frontend integration, technician transcriptions will finally appear in the UI!**
