# Deepgram Bidirectional Streaming Integration Plan

## Overview
Integrate Deepgram Nova-2 streaming transcription for BOTH directions in technician support:
1. **Twilio Phone Calls** → Customer audio (from Twilio Media Streams)
2. **Browser Audio** → Technician audio (from getUserMedia)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (Browser)                        │
│  ┌──────────────────┐        ┌─────────────────────────┐   │
│  │  Twilio Voice    │        │  getUserMedia (Mic)     │   │
│  │  (Customer)      │        │  (Technician)           │   │
│  └────────┬─────────┘        └────────┬────────────────┘   │
│           │ WebRTC                    │ AudioWorklet       │
└───────────┼───────────────────────────┼────────────────────┘
            │                           │
            │                           │ WS: /twilio/agent-audio-stream/
            │                           ▼
┌───────────┼───────────────────────────────────────────────┐
│           │         Backend (Flask)                        │
│           │                                                 │
│  ┌────────▼────────────┐      ┌────────────────────────┐  │
│  │ Twilio Media Stream │      │  Agent Audio WebSocket  │  │
│  │   WS Endpoint       │      │      WS Endpoint        │  │
│  └────────┬────────────┘      └────────┬───────────────┘  │
│           │                             │                  │
│           │ mulaw → PCM                 │ PCM Int16        │
│           │                             │                  │
│  ┌────────▼─────────────────────────────▼───────────────┐  │
│  │                                                        │  │
│  │     Deepgram Streaming Connections                    │  │
│  │                                                        │  │
│  │   ┌──────────────────┐  ┌────────────────────────┐   │  │
│  │   │  Customer Stream │  │  Technician Stream     │   │  │
│  │   │  (Nova-2, fr)    │  │  (Nova-2, fr)          │   │  │
│  │   └────────┬─────────┘  └────────┬───────────────┘   │  │
│  │            │                      │                    │  │
│  └────────────┼──────────────────────┼────────────────────┘  │
│               │ Transcriptions       │ Transcriptions        │
│               │                      │                        │
│  ┌────────────▼──────────────────────▼────────────────────┐  │
│  │      Technician Transcription WebSocket                 │  │
│  │      WS: /twilio/technician-transcription/              │  │
│  └────────────┬──────────────────────────────────────────┘  │
└───────────────┼───────────────────────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────────────────────┐
│              Frontend Transcription Display                │
│  ┌──────────────────────────────────────────────────────┐ │
│  │  👤 Customer: "Le bouton ne fonctionne pas..."       │ │
│  │  👨‍💼 Technician: "Avez-vous essayé de redémarrer?"   │ │
│  └──────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────┘
```

## Implementation Steps

### 1. Backend Updates

#### A. Modify `/twilio/media-stream/<session_id>`
**File**: `app/api/twilio_routes.py`

- Create Deepgram streaming connection when Twilio connects
- Forward incoming mulaw audio → decode → send to Deepgram
- Receive Deepgram transcriptions → broadcast to frontend

#### B. Modify `/twilio/agent-audio-stream/<session_id>`
**File**: `app/api/twilio_routes.py`

- Create separate Deepgram streaming connection for technician
- Receive PCM Int16 from browser → send to Deepgram
- Forward transcriptions to frontend WebSocket

#### C. Update Transcription WebSocket
**File**: `app/api/twilio_routes.py`

- Broadcast transcriptions from BOTH streams
- Add speaker labels: `customer` vs `technician`
- Include interim results for real-time feedback

### 2. Frontend Updates

#### A. Enable Interim Results Display
**File**: `app/frontend/templates/demo/technician_support.html`

- Show interim transcriptions in gray/italic
- Update to final transcriptions in black/bold
- Add visual indicators for speaker (customer/technician)

#### B. Update WebSocket Message Handling
- Handle `is_final` flag
- Handle `speech_final` flag for utterance boundaries
- Display confidence scores (optional)

### 3. Configuration

#### Add Deepgram Settings
**File**: `app/config/transcription_config.json`

```json
{
  "transcription_backend": "deepgram",
  "deepgram_use_streaming": true,
  "deepgram_show_interim": true,
  "transcription_language": "fr"
}
```

## Message Flow

### Customer Audio (Twilio → Deepgram)
```
1. Twilio sends mulaw audio → Backend
2. Backend decodes mulaw → PCM Int16
3. PCM → Deepgram connection.send_audio()
4. Deepgram fires EventType.MESSAGE callback
5. Callback sends to /twilio/technician-transcription/ WebSocket
6. Frontend displays in transcription panel
```

### Technician Audio (Browser → Deepgram)
```
1. Browser AudioWorklet captures mic → PCM Int16
2. WebSocket sends to /twilio/agent-audio-stream/
3. Backend receives → Deepgram connection.send_audio()
4. Deepgram fires EventType.MESSAGE callback
5. Callback sends to /twilio/technician-transcription/ WebSocket
6. Frontend displays in transcription panel
```

## Expected Frontend Message Format

```json
{
  "type": "transcription",
  "text": "Le bouton ne fonctionne pas",
  "speaker_role": "customer",
  "speaker_label": "Client",
  "is_final": false,
  "speech_final": false,
  "confidence": 0.92,
  "timestamp": "2025-07-25T10:30:45.123Z",
  "language": "fr",
  "model": "deepgram-nova-2-streaming"
}
```

## Benefits

1. **Real-Time Streaming**: Token-by-token transcriptions as users speak
2. **Bidirectional**: Both customer and technician speech transcribed
3. **Language Support**: French (fr) configured, easily extensible
4. **High Accuracy**: Deepgram Nova-2 optimized for telephony
5. **Visual Feedback**: Interim results show transcription in progress

## Testing Checklist

- [ ] Twilio call connects and Deepgram initializes
- [ ] Customer speech transcribed (from phone)
- [ ] Technician speech transcribed (from browser)
- [ ] Interim results display in gray/italic
- [ ] Final results replace interim in black/bold
- [ ] Speaker labels show correctly (customer/technician)
- [ ] Connection cleanup on call end
- [ ] Error handling for connection failures
- [ ] Multiple concurrent calls work independently

## Files to Modify

1. `/app/api/twilio_routes.py` - Add Deepgram connections
2. `/app/frontend/templates/demo/technician_support.html` - Update UI
3. `/app/config/transcription_config.json` - Configuration

## Next Steps

1. Implement Deepgram integration in twilio_routes.py
2. Update frontend message handlers
3. Test with real Twilio calls
4. Deploy and monitor
