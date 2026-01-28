# Deepgram Bidirectional Integration - Implementation Steps

## ✅ What's Already Done

1. **Created Official Deepgram SDK v5 Implementation**
   - File: `app/services/deepgram_streaming_v5.py`
   - Uses event-based pattern with `EventType.MESSAGE` callbacks
   - Full Pydantic object support

2. **Created Bridge Service**
   - File: `app/services/deepgram_twilio_bridge.py`
   - Manages bidirectional Deepgram connections
   - Handles speaker labeling automatically

3. **Created Integration Documentation**
   - File: `DEEPGRAM_BIDIRECTIONAL_INTEGRATION.md`
   - Architecture diagrams and message flow

## 🔧 Implementation Steps

### Step 1: Modify Twilio Media Stream Handler

**File**: `app/api/twilio_routes.py`

**Location**: In the `@sock.route('/twilio/media-stream/<session_id>')` function

**Add at the beginning** (after getting twilio_service):

```python
# Import Deepgram bridge
from app.services.deepgram_twilio_bridge import get_deepgram_twilio_bridge

# Get bridge service
deepgram_bridge = get_deepgram_twilio_bridge()

# Initialize Deepgram connection for customer audio
customer_deepgram = None
```

**Add after Twilio stream connects** (when you receive 'start' event):

```python
if data.get('event') == 'start':
    logger.info(f"[{session_id}] Twilio media stream started")

    # Create Deepgram streaming connection for customer
    def on_customer_transcript(result):
        """Callback for customer transcriptions from Deepgram"""
        try:
            # Get technician transcription WebSocket
            if session_id in twilio_service.active_streams:
                tech_ws = twilio_service.active_streams[session_id].get('technician', {}).get('transcription_ws')

                if tech_ws:
                    # Send transcription to frontend
                    message = {
                        'type': 'transcription',
                        'text': result['text'],
                        'speaker_role': result['speaker_role'],
                        'speaker_label': result['speaker_label'],
                        'is_final': result['is_final'],
                        'speech_final': result.get('speech_final', False),
                        'confidence': result['confidence'],
                        'timestamp': datetime.utcnow().isoformat(),
                        'language': result['language'],
                        'model': result['model']
                    }
                    tech_ws.send(json.dumps(message))
                    logger.info(f"[{session_id}] Sent customer transcription to frontend")
        except Exception as e:
            logger.error(f"[{session_id}] Error sending customer transcription: {e}")

    customer_deepgram = deepgram_bridge.create_customer_stream(
        session_id=session_id,
        language='fr',
        on_transcript=on_customer_transcript
    )

    if customer_deepgram:
        logger.info(f"[{session_id}] ✅ Customer Deepgram stream ready")
    else:
        logger.error(f"[{session_id}] ❌ Failed to create customer Deepgram stream")
```

**Add in the 'media' event handler** (where you process audio):

```python
if data.get('event') == 'media':
    # Existing code to decode mulaw...

    # After decoding mulaw to PCM:
    # Send audio to Deepgram
    if customer_deepgram and customer_deepgram.is_connected:
        deepgram_bridge.send_customer_audio(session_id, pcm_data)
```

**Add in the cleanup/finally block**:

```python
finally:
    # Close Deepgram connections
    deepgram_bridge.close_session(session_id)

    # Existing cleanup code...
```

### Step 2: Modify Agent Audio Stream Handler

**File**: `app/api/twilio_routes.py`

**Location**: In the `@sock.route('/twilio/agent-audio-stream/<session_id>')` function

**Add at the beginning**:

```python
# Import Deepgram bridge
from app.services.deepgram_twilio_bridge import get_deepgram_twilio_bridge

# Get bridge service
deepgram_bridge = get_deepgram_twilio_bridge()

# Initialize Deepgram connection for technician audio
technician_deepgram = None
```

**Add after WebSocket connects** (after sending 'connected' message):

```python
# Send confirmation to frontend
ws.send(json.dumps({
    'event': 'connected',
    'session_id': session_id,
    'type': 'agent_audio'
}))

# Create Deepgram streaming connection for technician
def on_technician_transcript(result):
    """Callback for technician transcriptions from Deepgram"""
    try:
        # Get technician transcription WebSocket
        if session_id in twilio_service.active_streams:
            tech_ws = twilio_service.active_streams[session_id].get('technician', {}).get('transcription_ws')

            if tech_ws:
                # Send transcription to frontend
                message = {
                    'type': 'transcription',
                    'text': result['text'],
                    'speaker_role': result['speaker_role'],
                    'speaker_label': result['speaker_label'],
                    'is_final': result['is_final'],
                    'speech_final': result.get('speech_final', False),
                    'confidence': result['confidence'],
                    'timestamp': datetime.utcnow().isoformat(),
                    'language': result['language'],
                    'model': result['model']
                }
                tech_ws.send(json.dumps(message))
                logger.info(f"[{session_id}] Sent technician transcription to frontend")
    except Exception as e:
        logger.error(f"[{session_id}] Error sending technician transcription: {e}")

technician_deepgram = deepgram_bridge.create_technician_stream(
    session_id=session_id,
    language='fr',
    on_transcript=on_technician_transcript
)

if technician_deepgram:
    logger.info(f"[{session_id}] ✅ Technician Deepgram stream ready")
else:
    logger.error(f"[{session_id}] ❌ Failed to create technician Deepgram stream")
```

**Add in the audio processing loop** (where you receive binary audio):

```python
if isinstance(message, bytes):
    # Browser now sends Int16Array directly (already in PCM format)
    pcm_data = message

    # Send audio to Deepgram
    if technician_deepgram and technician_deepgram.is_connected:
        deepgram_bridge.send_technician_audio(session_id, pcm_data)

    # Keep existing code that processes agent audio...
```

**Add in the cleanup/finally block**:

```python
finally:
    # Close Deepgram connection (will be closed by session cleanup, but safe to call twice)
    # Note: Customer stream is closed in media-stream handler
    # deepgram_bridge.close_session() is called there

    # Existing cleanup code...
```

### Step 3: Update Frontend JavaScript

**File**: `app/frontend/templates/demo/technician_support.html`

**Update the `addTranscriptionBubble` function** to handle interim results:

```javascript
function addTranscriptionBubble(text, label, role, is_final = true, confidence = 1.0) {
    const c = document.getElementById('transcriptionContent');
    const empty = c.querySelector('.transcription-empty');
    if (empty) empty.remove();

    // Check if this is an update to an existing interim result
    const existingInterim = c.querySelector(`[data-interim-id="${role}"]`);

    if (!is_final) {
        // This is an interim result
        if (existingInterim) {
            // Update existing interim bubble
            existingInterim.querySelector('.transcript-text').textContent = text;
            existingInterim.querySelector('.transcript-confidence').textContent = `${(confidence * 100).toFixed(0)}%`;
        } else {
            // Create new interim bubble
            const line = document.createElement('div');
            line.className = `transcript-line ${role}`;
            line.setAttribute('data-interim-id', role);
            line.style.fontStyle = 'italic';
            line.style.opacity = '0.7';

            line.innerHTML = `
                <div class="transcript-speaker">${label}</div>
                <div class="transcript-text">${text}</div>
                <div class="transcript-meta">
                    <span class="transcript-time">${new Date().toLocaleTimeString('fr-FR')}</span>
                    <span class="transcript-confidence">${(confidence * 100).toFixed(0)}%</span>
                    <span class="transcript-status" style="color: #999;">En cours...</span>
                </div>
            `;
            c.appendChild(line);
        }
    } else {
        // This is a final result
        if (existingInterim) {
            // Replace interim with final
            existingInterim.querySelector('.transcript-text').textContent = text;
            existingInterim.querySelector('.transcript-confidence').textContent = `${(confidence * 100).toFixed(0)}%`;
            existingInterim.querySelector('.transcript-status').remove();
            existingInterim.style.fontStyle = 'normal';
            existingInterim.style.opacity = '1';
            existingInterim.removeAttribute('data-interim-id');
        } else {
            // Create new final bubble
            const line = document.createElement('div');
            line.className = `transcript-line ${role}`;

            line.innerHTML = `
                <div class="transcript-speaker">${label}</div>
                <div class="transcript-text">${text}</div>
                <div class="transcript-meta">
                    <span class="transcript-time">${new Date().toLocaleTimeString('fr-FR')}</span>
                    <span class="transcript-confidence">${(confidence * 100).toFixed(0)}%</span>
                </div>
            `;
            c.appendChild(line);
        }
    }

    c.scrollTop = c.scrollHeight;
}
```

**Update the WebSocket message handler** in `technicianTranscriptionWebSocket.onmessage`:

```javascript
technicianTranscriptionWebSocket.onmessage = (e) => {
    try {
        const d = JSON.parse(e.data);

        if (d.event === 'connected' && d.type === 'technician_transcription') {
            t = true;
            check();
        } else if (d.type === 'transcription') {
            addTranscriptionBubble(
                d.text,
                d.speaker_label || 'Unknown',
                d.speaker_role || 'unknown',
                d.is_final !== false,  // Default to true if not specified
                d.confidence || 1.0
            );
        }
    } catch (err) {
        console.error('Transcription WebSocket error:', err);
    }
};
```

### Step 4: Test the Integration

1. **Start the Flask server**:
   ```bash
   python main.py
   ```

2. **Open the technician interface**:
   ```
   http://localhost:5000/demo/technician-support
   ```

3. **Make a test call** (or use browser mic)

4. **Watch the console** for logs:
   - `✅ Customer Deepgram stream ready`
   - `✅ Technician Deepgram stream ready`
   - `📞 Customer: 'hello...'`
   - `👨‍💼 Technician: 'bonjour...'`

5. **Check the frontend** for real-time transcriptions:
   - Interim results in gray/italic
   - Final results in black/normal
   - Both customer and technician speech

### Step 5: Monitor and Debug

**Check Deepgram connection status**:
```python
# In your code or debug console
from app.services.deepgram_twilio_bridge import get_deepgram_twilio_bridge
bridge = get_deepgram_twilio_bridge()
stats = bridge.get_session_stats('your-session-id')
print(stats)
```

**Expected output**:
```json
{
  "active": true,
  "session_id": "abc123",
  "streams": {
    "customer": {
      "connected": true,
      "language": "fr",
      "created_at": "2025-07-25T10:30:00"
    },
    "technician": {
      "connected": true,
      "language": "fr",
      "created_at": "2025-07-25T10:30:05"
    }
  }
}
```

## 🎯 Summary

You've now integrated:
- ✅ Deepgram Nova-2 streaming for customer audio (Twilio)
- ✅ Deepgram Nova-2 streaming for technician audio (browser)
- ✅ Event-based architecture (official SDK v5 pattern)
- ✅ Real-time interim + final results
- ✅ Bidirectional transcription
- ✅ Speaker labeling
- ✅ Confidence scores

## 📋 Final Checklist

- [ ] Import deepgram_twilio_bridge in twilio_routes.py
- [ ] Add customer Deepgram stream in media-stream handler
- [ ] Add technician Deepgram stream in agent-audio-stream handler
- [ ] Update frontend JavaScript for interim results
- [ ] Test with real Twilio call
- [ ] Test with browser microphone
- [ ] Verify both streams show transcriptions
- [ ] Check logs for connection status
- [ ] Verify cleanup on call end

## 🚀 Next Enhancements

1. **Language Detection**: Auto-detect language instead of hardcoding 'fr'
2. **Sentiment Analysis**: Add emotion detection from transcriptions
3. **Keyword Highlighting**: Highlight important technical terms
4. **Export Transcripts**: Save call transcriptions to database
5. **Real-time Translation**: Translate between French and English
