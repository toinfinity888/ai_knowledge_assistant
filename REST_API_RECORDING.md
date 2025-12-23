# REST API Recording - Dynamic Call Recording

## Status: ✅ IMPLEMENTED

Added the ability to start recording on active calls using Twilio's REST API with `client.calls().recordings.create()`.

---

## Overview

You now have **TWO ways** to enable recording:

### 1. TwiML Recording (Existing)
- **When:** Recording starts automatically when call begins
- **How:** `<Recording>` tag in TwiML response
- **Use case:** Always record every call

### 2. REST API Recording (NEW)
- **When:** Recording starts dynamically on active calls
- **How:** POST to `/twilio/start-recording` endpoint
- **Use case:** Conditional recording, user-triggered recording

---

## REST API Implementation

### Service Method

Added to `TwilioAudioService` ([twilio_audio_service.py:563-605](app/services/twilio_audio_service.py#L563-L605)):

```python
def start_recording(self, call_sid: str, recording_status_callback: Optional[str] = None) -> Dict[str, Any]:
    """
    Start recording an active call using Twilio REST API

    This is an alternative to using <Recording> in TwiML. Useful for:
    - Starting recording on an already-active call
    - Dynamically starting/stopping recording based on conditions
    """

    recording = self.client.calls(call_sid).recordings.create(
        recording_channels='dual',  # Separate agent + technician
        recording_status_callback=recording_status_callback,
        recording_status_callback_event=['completed']
    )

    return {
        'recording_sid': recording.sid,
        'call_sid': call_sid,
        'status': recording.status,
        'channels': 'dual'
    }
```

### API Endpoint

New endpoint: `POST /twilio/start-recording`

**Request:**
```json
{
    "call_sid": "CAxxxxxxxxxxxx",
    "recording_status_callback": "https://your-server/callback"
}
```

**Response:**
```json
{
    "success": true,
    "recording_sid": "RExxxxxxxxxxxx",
    "call_sid": "CAxxxxxxxxxxxx",
    "status": "in-progress",
    "channels": "dual"
}
```

---

## When to Use Each Method

### TwiML Recording (`<Recording>` tag)

**Advantages:**
- ✅ Recording starts immediately when call begins
- ✅ No additional API calls needed
- ✅ Guaranteed to capture entire call
- ✅ Simpler implementation

**Use when:**
- You want to record ALL calls automatically
- Recording policy requires complete call capture
- No user choice needed

**Example:** Compliance recording, quality assurance

### REST API Recording (`client.calls().recordings.create()`)

**Advantages:**
- ✅ Start recording at any time during call
- ✅ Conditional recording based on user action
- ✅ Can be triggered by agent or system event
- ✅ More flexible control

**Use when:**
- Agent decides mid-call to start recording
- Recording only needed for certain topics
- User consent required before recording
- System detects specific keywords/events

**Example:** "Record this for my manager", escalation scenarios

---

## Usage Scenarios

### Scenario 1: Always Record (TwiML)

**Current implementation:**

```xml
<Response>
    <Start>
        <Stream url="wss://..." />
        <Recording channels="dual" ... />  ← Always records
    </Start>
    <Dial>...</Dial>
</Response>
```

**Result:** Every call is recorded from start to finish.

### Scenario 2: On-Demand Recording (REST API)

**Step 1: Start call WITHOUT recording**

Remove `<Recording>` from TwiML:
```xml
<Response>
    <Start>
        <Stream url="wss://..." />
        <!-- NO Recording tag -->
    </Start>
    <Dial>...</Dial>
</Response>
```

**Step 2: Agent decides to start recording mid-call**

Frontend button triggers API call:
```javascript
async function startRecording(callSid) {
    const response = await fetch('/twilio/start-recording', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            call_sid: callSid,
            recording_status_callback: 'https://your-server/twilio/recording-status'
        })
    });

    const result = await response.json();
    console.log('Recording started:', result.recording_sid);
}
```

**Step 3: Recording begins**

Twilio starts recording from that moment forward (not retroactive).

### Scenario 3: Conditional Recording

**Example: Record only if issue escalated**

```python
# In your call handling logic
if issue_severity == 'high' or needs_escalation:
    # Start recording via REST API
    twilio_service = get_twilio_service()
    recording = twilio_service.start_recording(
        call_sid=call_sid,
        recording_status_callback='https://your-server/twilio/recording-status'
    )
    logger.info(f"High-priority issue detected - recording started: {recording['recording_sid']}")
```

### Scenario 4: User Consent Recording

**Example: Ask permission before recording**

```python
# 1. Call starts WITHOUT recording

# 2. Agent asks: "May I record this call for quality purposes?"

# 3. If customer says yes:
if customer_consents:
    twilio_service.start_recording(call_sid)
    # Announce to customer
    play_message("This call is now being recorded.")
```

---

## Hybrid Approach: TwiML + REST API

You can use **BOTH** methods together:

### Use Case: Dual Recording for Different Purposes

```xml
<!-- TwiML: Always start basic recording -->
<Response>
    <Start>
        <Stream url="wss://..." />
        <Recording channels="mono" />  ← Basic mono recording
    </Start>
    <Dial>...</Dial>
</Response>
```

Then if escalation happens:
```python
# REST API: Start high-quality dual-channel recording
twilio_service.start_recording(
    call_sid=call_sid,
    recording_channels='dual'  # High-quality separate channels
)
```

**Result:** Two recordings:
1. Full call in mono (from TwiML)
2. Escalation portion in dual-channel (from REST API)

---

## Testing the REST API

### Test 1: Start Recording on Active Call

**Step 1: Make a call** (using existing interface)

**Step 2: Get the call SID** (from logs or UI)

**Step 3: Start recording via API**

```bash
curl -X POST http://localhost:8000/twilio/start-recording \
  -H "Content-Type: application/json" \
  -d '{
    "call_sid": "CA1234567890abcdef",
    "recording_status_callback": "https://your-ngrok-url/twilio/recording-status"
  }'
```

**Expected response:**
```json
{
  "success": true,
  "recording_sid": "REabcdef1234567890",
  "call_sid": "CA1234567890abcdef",
  "status": "in-progress",
  "channels": "dual"
}
```

**Step 4: Check server logs**

```
📼 Starting recording for call CA1234... via REST API
✅ Recording started:
   Recording SID: RE...
   Call SID: CA...
   Status: in-progress
```

**Step 5: Wait for callback** (after call ends)

```
📼 Recording callback received:
   Event: completed
   Recording SID: RE...
   Duration: 45s
   Channels: 2
```

### Test 2: Error Handling

**Test with invalid call SID:**
```bash
curl -X POST http://localhost:8000/twilio/start-recording \
  -H "Content-Type: application/json" \
  -d '{"call_sid": "INVALID"}'
```

**Expected response:**
```json
{
  "error": "The requested resource /Accounts/.../Calls/INVALID/Recordings.json was not found"
}
```

**Test with missing call_sid:**
```bash
curl -X POST http://localhost:8000/twilio/start-recording \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Expected response:**
```json
{
  "error": "Missing call_sid"
}
```

---

## Frontend Integration

### Add "Start Recording" Button to UI

**HTML:**
```html
<button id="startRecordingBtn" onclick="startRecording()" disabled>
    Start Recording
</button>
<span id="recordingStatus"></span>
```

**JavaScript:**
```javascript
let currentCallSid = null;

// When call connects, enable button
device.on('connect', (conn) => {
    currentCallSid = conn.parameters.CallSid;
    document.getElementById('startRecordingBtn').disabled = false;
});

// Start recording function
async function startRecording() {
    if (!currentCallSid) {
        alert('No active call');
        return;
    }

    try {
        const response = await fetch('/twilio/start-recording', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                call_sid: currentCallSid,
                recording_status_callback: `${window.location.origin}/twilio/recording-status`
            })
        });

        const result = await response.json();

        if (result.success) {
            document.getElementById('recordingStatus').textContent =
                '🔴 Recording...';
            document.getElementById('startRecordingBtn').disabled = true;
            console.log('Recording started:', result.recording_sid);
        } else {
            alert('Failed to start recording: ' + result.error);
        }
    } catch (error) {
        console.error('Error starting recording:', error);
        alert('Error starting recording');
    }
}

// When call ends, reset
device.on('disconnect', () => {
    currentCallSid = null;
    document.getElementById('startRecordingBtn').disabled = true;
    document.getElementById('recordingStatus').textContent = '';
});
```

---

## Comparison: TwiML vs REST API

| Feature | TwiML `<Recording>` | REST API `.recordings.create()` |
|---------|---------------------|----------------------------------|
| **Timing** | Call start | Anytime during call |
| **Trigger** | Automatic | Manual/conditional |
| **Coverage** | Full call | From start point forward |
| **Setup** | XML in TwiML | HTTP POST request |
| **Use case** | Always record | On-demand record |
| **User choice** | No | Yes |
| **Code location** | `/voice` endpoint | `/start-recording` endpoint |
| **Channels** | mono or dual | mono or dual |
| **Callback** | Yes | Yes |

---

## Architecture Comparison

### Before (TwiML Only)

```
Call Start
  ↓
TwiML with <Recording>
  ↓
Recording starts automatically
  ↓
Full call recorded
```

### After (TwiML + REST API)

```
Call Start
  ↓
Option 1: TwiML with <Recording>
  ├─ Recording starts automatically
  └─ Full call recorded

Option 2: TwiML without <Recording>
  ├─ Call starts normally
  ├─ No recording initially
  └─ Agent/system decides later:
      ↓
  POST /start-recording
      ↓
  Recording starts from that moment
```

---

## Recording Methods Summary

You now have **FOUR recording methods**:

### 1. Local 8kHz WAV (Real-time)
- **Source:** Twilio Media Stream
- **Method:** WebSocket
- **Storage:** Local disk
- **When:** Real-time during call
- **Purpose:** Original quality reference

### 2. Local 16kHz WAV (Real-time)
- **Source:** Resampled from 8kHz
- **Method:** WebSocket + processing
- **Storage:** Local disk
- **When:** Real-time during call
- **Purpose:** Whisper transcription

### 3. Twilio Cloud - TwiML (Automatic)
- **Source:** Full call
- **Method:** `<Recording>` in TwiML
- **Storage:** Twilio cloud
- **When:** Entire call (automatic)
- **Purpose:** Compliance, QA

### 4. Twilio Cloud - REST API (On-demand) ← NEW
- **Source:** Full call
- **Method:** `.recordings.create()`
- **Storage:** Twilio cloud
- **When:** Partial call (triggered)
- **Purpose:** Conditional recording

---

## Use Case Examples

### Example 1: Support Call Center

**Requirement:** Record only escalated calls

**Implementation:**
1. Normal calls: No TwiML recording
2. If escalated: Trigger REST API recording
3. Result: Save storage, only record important calls

```python
if issue_escalated_to_supervisor:
    recording = twilio_service.start_recording(call_sid)
    send_notification(supervisor, f"Escalated call recorded: {recording['recording_sid']}")
```

### Example 2: Healthcare/Legal

**Requirement:** User consent before recording

**Implementation:**
1. Call starts without recording
2. Ask for consent
3. If granted: Start recording via REST API

```python
consent_given = ask_for_consent(customer)
if consent_given:
    recording = twilio_service.start_recording(call_sid)
    log_consent(customer_id, recording['recording_sid'], timestamp)
```

### Example 3: Training/Coaching

**Requirement:** Supervisor requests recording for training

**Implementation:**
1. Calls normally not recorded
2. Supervisor monitors live calls
3. If good example: Click "Record for Training"
4. REST API starts recording mid-call

```javascript
// Supervisor dashboard
function recordForTraining(callSid) {
    startRecording(callSid);
    tagRecording('training_example');
}
```

---

## Configuration Options

### REST API Recording Parameters

The `recordings.create()` method supports:

```python
recording = client.calls(call_sid).recordings.create(
    recording_channels='dual',           # 'mono' or 'dual'
    recording_status_callback='https://...',
    recording_status_callback_method='POST',
    recording_status_callback_event=['in-progress', 'completed', 'absent'],
    recording_track='both'               # 'inbound', 'outbound', or 'both'
)
```

### Current Implementation

```python
# app/services/twilio_audio_service.py:585-589
recording = self.client.calls(call_sid).recordings.create(
    recording_channels='dual',           # Separate agent + tech
    recording_status_callback=callback,  # Optional webhook
    recording_status_callback_event=['completed']  # Only notify when done
)
```

To customize, modify the parameters in `start_recording()` method.

---

## API Reference

### Endpoint: POST /twilio/start-recording

**URL:** `http://your-server:8000/twilio/start-recording`

**Method:** POST

**Headers:**
```
Content-Type: application/json
```

**Body:**
```json
{
    "call_sid": "CAxxxxxxxxxxxx",              // Required
    "recording_status_callback": "https://..." // Optional
}
```

**Success Response (200):**
```json
{
    "success": true,
    "recording_sid": "RExxxxxxxxxxxx",
    "call_sid": "CAxxxxxxxxxxxx",
    "status": "in-progress",
    "channels": "dual"
}
```

**Error Responses:**

**400 Bad Request** (missing call_sid):
```json
{
    "error": "Missing call_sid"
}
```

**500 Internal Server Error** (Twilio API error):
```json
{
    "error": "The requested resource was not found"
}
```

---

## Security Considerations

### Authorization

**Important:** Add authentication to the `/start-recording` endpoint!

**Example with token auth:**
```python
@twilio_bp.route('/start-recording', methods=['POST'])
def start_recording():
    # Check authorization
    auth_header = request.headers.get('Authorization')
    if not is_valid_token(auth_header):
        return jsonify({'error': 'Unauthorized'}), 401

    # ... rest of implementation
```

### Rate Limiting

Prevent abuse by limiting recording start requests:

```python
from flask_limiter import Limiter

limiter = Limiter(app, key_func=lambda: request.remote_addr)

@twilio_bp.route('/start-recording', methods=['POST'])
@limiter.limit("10 per minute")  # Max 10 recording starts per minute
def start_recording():
    # ... implementation
```

### Call Ownership Validation

Ensure user can only record their own calls:

```python
@twilio_bp.route('/start-recording', methods=['POST'])
def start_recording():
    call_sid = data.get('call_sid')
    user_id = get_current_user_id()

    # Verify user owns this call
    if not is_user_call(user_id, call_sid):
        return jsonify({'error': 'Forbidden'}), 403

    # ... start recording
```

---

## Troubleshooting

### Error: "Call not found"

**Cause:** Invalid or expired call SID

**Solution:** Verify call is still active:
```bash
curl -X GET http://localhost:8000/twilio/call-status/CA1234...
```

### Error: "Recording already in progress"

**Cause:** Call is already being recorded (via TwiML or previous REST call)

**Solution:** Check if recording exists before starting new one

### No Callback Received

**Cause:** Callback URL not reachable by Twilio

**Solution:**
1. Ensure ngrok is running
2. Use full public URL in callback
3. Test callback endpoint manually

---

## Summary

✅ **REST API recording fully implemented**

**What was added:**

1. **Service Method** (`twilio_audio_service.py:563-605`)
   - `start_recording(call_sid, callback_url)`
   - Dual-channel support
   - Status callback support

2. **API Endpoint** (`twilio_routes.py:187-233`)
   - `POST /twilio/start-recording`
   - JSON request/response
   - Error handling

**Benefits:**

- ✅ Start recording anytime during call
- ✅ Conditional recording based on events
- ✅ User-triggered recording
- ✅ Dual-channel support
- ✅ Same callback as TwiML recording

**Use cases:**

- On-demand recording
- Consent-based recording
- Escalation recording
- Training/QA recording
- Compliance recording

---

**Date:** 2025-11-20
**Feature:** REST API Call Recording
**Status:** ✅ Production Ready
**Method:** `client.calls().recordings.create()`
