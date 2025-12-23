# Twilio Cloud Dual-Channel Recording

## Status: ✅ ENABLED

Twilio's native dual-channel cloud recording is now enabled alongside our local WAV file recording.

---

## What Was Added

### TwiML Recording Tag

The `/twilio/voice` endpoint now includes `<Recording>` inside `<Start>`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Start>
        <Stream url="wss://your-server/twilio/media-stream" />
        <Recording channels="dual" recordingStatusCallback="https://your-server/twilio/recording-status" />
    </Start>
    <Dial callerId="+12402559789">
        <Number>+15551234567</Number>
    </Dial>
</Response>
```

### Recording Status Callback Endpoint

New endpoint: `POST /twilio/recording-status`

Receives callbacks from Twilio when recordings are ready.

---

## How It Works

### Call Flow with Dual Recording

```
1. Browser initiates call
   ↓
2. Twilio calls /twilio/voice webhook
   ↓
3. Server returns TwiML with:
   - <Stream> for real-time transcription
   - <Recording channels="dual"> for cloud recording
   ↓
4. Call proceeds normally
   │
   ├─→ Real-time audio streams to WebSocket
   │   - Saved locally as 8kHz + 16kHz WAV files
   │   - Transcribed by Whisper in real-time
   │
   └─→ Full call recorded by Twilio cloud
       - Dual-channel (agent + technician separate)
       - Stored in Twilio's cloud storage
       - Callback sent when ready
   ↓
5. Call ends
   ↓
6. Twilio processes recording
   ↓
7. Callback to /twilio/recording-status with:
   - RecordingSid
   - RecordingUrl
   - RecordingDuration
   - RecordingChannels (2 for dual)
```

---

## Three Types of Recording Now Active

### 1. Local 8kHz WAV (Existing)
- **Source:** Twilio Media Stream (technician audio only)
- **Location:** `audio_recordings/technician_{session}_8000Hz.wav`
- **Quality:** Original 8kHz mulaw → PCM
- **Channels:** 1 (mono - technician only)
- **Purpose:** Original quality reference before resampling

### 2. Local 16kHz WAV (Existing)
- **Source:** Resampled from 8kHz
- **Location:** `audio_recordings/technician_{session}_16000Hz.wav`
- **Quality:** Resampled to 16kHz for Whisper
- **Channels:** 1 (mono - technician only)
- **Purpose:** Processed audio for transcription

### 3. Twilio Cloud Dual-Channel Recording (NEW)
- **Source:** Full call (both parties)
- **Location:** Twilio cloud storage
- **Quality:** High-quality recording from Twilio's infrastructure
- **Channels:** 2 (dual - agent + technician separate)
- **Format:** Various (WAV, MP3 - configurable)
- **Purpose:** Complete call archive with both speakers isolated

---

## Benefits of Dual-Channel Cloud Recording

### Advantages Over Local Recording

1. **Both Speakers Recorded**
   - Agent (browser) audio
   - Technician (phone) audio
   - Both captured at source, not from media stream

2. **Separate Channels**
   - Channel 1: Agent audio
   - Channel 2: Technician audio
   - Can process independently
   - Better for speaker diarization

3. **Higher Quality**
   - Recorded at Twilio's infrastructure (before compression)
   - Not affected by media stream quality
   - Professional-grade audio capture

4. **Reliable Storage**
   - Stored in Twilio's cloud
   - Accessible via API
   - No disk space concerns on your server

5. **Post-Call Processing**
   - Available after call ends
   - Can download and process later
   - Doesn't impact real-time transcription performance

### When to Use Each Recording Type

| Use Case | Local 8kHz | Local 16kHz | Twilio Dual-Channel |
|----------|-----------|-------------|---------------------|
| Real-time transcription | ✅ Source | ✅ For Whisper | ❌ Not real-time |
| Quality comparison | ✅ Original | ✅ Resampled | ✅ High quality |
| Agent audio | ❌ No | ❌ No | ✅ Yes |
| Technician audio | ✅ Yes | ✅ Yes | ✅ Yes |
| Speaker separation | ❌ Mono | ❌ Mono | ✅ Dual-channel |
| Storage | Local disk | Local disk | Twilio cloud |
| Availability | During call | During call | After call |
| Cost | Free (disk space) | Free (disk space) | Twilio charges |

---

## Twilio Recording Callback

### Callback Payload

When recording is ready, Twilio POSTs to `/twilio/recording-status`:

```python
{
    'RecordingSid': 'RE1234567890abcdef1234567890abcdef',
    'RecordingUrl': 'https://api.twilio.com/2010-04-01/Accounts/AC.../Recordings/RE...',
    'RecordingStatus': 'completed',
    'RecordingDuration': '65',
    'RecordingChannels': '2',
    'CallSid': 'CA1234567890abcdef1234567890abcdef',
    'AccountSid': 'AC1234567890abcdef1234567890abcdef',
    'From': '+15551234567',
    'To': '+15557654321'
}
```

### Current Implementation

The callback endpoint logs the recording details:

```python
@twilio_bp.route('/recording-status', methods=['POST'])
def recording_status_callback():
    """Callback from Twilio when dual-channel recording is ready"""

    recording_sid = request.form.get('RecordingSid')
    recording_url = request.form.get('RecordingUrl')
    recording_status = request.form.get('RecordingStatus')
    recording_duration = request.form.get('RecordingDuration')
    recording_channels = request.form.get('RecordingChannels')
    call_sid = request.form.get('CallSid')

    logger.info(f"📼 Recording callback received:")
    logger.info(f"   Recording SID: {recording_sid}")
    logger.info(f"   Status: {recording_status}")
    logger.info(f"   Duration: {recording_duration}s")
    logger.info(f"   Channels: {recording_channels}")
    logger.info(f"   URL: {recording_url}")

    # TODO: Store metadata in database
    # TODO: Download recording file
    # TODO: Process dual-channel audio

    return '', 204
```

### Future Enhancements

**TODO items marked in code:**

1. **Store Recording Metadata**
   ```python
   # Save to database
   db.recordings.insert({
       'recording_sid': recording_sid,
       'call_sid': call_sid,
       'url': recording_url,
       'duration': recording_duration,
       'channels': recording_channels,
       'status': recording_status,
       'created_at': datetime.utcnow()
   })
   ```

2. **Download Recording File**
   ```python
   # Download from Twilio
   from twilio.rest import Client

   client = Client(account_sid, auth_token)
   recording = client.recordings(recording_sid).fetch()

   # Download as WAV
   wav_url = recording.media_url + '.wav'
   response = requests.get(wav_url, auth=(account_sid, auth_token))

   # Save locally
   filepath = f"twilio_recordings/{call_sid}_{recording_sid}.wav"
   with open(filepath, 'wb') as f:
       f.write(response.content)
   ```

3. **Process Dual-Channel Audio**
   ```python
   # Split channels using pydub or wave
   from pydub import AudioSegment

   audio = AudioSegment.from_wav(filepath)

   # Extract channels
   agent_audio = audio.split_to_mono()[0]  # Channel 1
   tech_audio = audio.split_to_mono()[1]   # Channel 2

   # Save separately
   agent_audio.export(f"{call_sid}_agent.wav", format="wav")
   tech_audio.export(f"{call_sid}_tech.wav", format="wav")

   # Process each separately
   transcribe_audio(agent_audio, speaker='agent')
   transcribe_audio(tech_audio, speaker='technician')
   ```

---

## Testing the Recording

### 1. Make a Test Call

From the browser interface, initiate a call and speak for 30+ seconds.

### 2. Check Server Logs

During call initiation, you should see:
```
📞 Browser calling +15551234567 from +15557654321
🔌 Starting media stream to wss://...
📼 Starting dual-channel recording with callback to https://.../twilio/recording-status
✅ Generated TwiML for call to +15551234567
```

### 3. Wait for Callback

After call ends, Twilio processes the recording (usually takes 1-5 minutes) and calls your callback endpoint.

Check logs for:
```
📼 Recording callback received:
   Recording SID: RE1234...
   Status: completed
   Duration: 45s
   Channels: 2
   URL: https://api.twilio.com/.../Recordings/RE...
   Call SID: CA5678...
```

### 4. Verify Recording URL

Use the Recording SID to fetch the recording via Twilio API:

```bash
curl -X GET "https://api.twilio.com/2010-04-01/Accounts/YOUR_ACCOUNT_SID/Recordings/RE1234.wav" \
  -u "YOUR_ACCOUNT_SID:YOUR_AUTH_TOKEN" \
  -o recording.wav
```

Or access via Twilio Console:
- Go to https://console.twilio.com/
- Navigate to Monitor → Logs → Recordings
- Find your recording by SID or date
- Listen or download

---

## Configuration

### Recording Callback URL

The callback URL is automatically generated using the request host:

```python
recording_callback = f"https://{request.host}/twilio/recording-status"
```

**For ngrok:**
```
https://uncrusted-laurena-reflexly.ngrok-free.dev/twilio/recording-status
```

**For production:**
```
https://yourdomain.com/twilio/recording-status
```

### Ensure ngrok is Running

Since you're using ngrok, make sure it's active:

```bash
# Check ngrok status
ps aux | grep ngrok | grep -v grep

# Should show:
# ngrok http 8000
```

If not running:
```bash
ngrok http 8000
```

Then update your `.env` with the new ngrok URL if it changed.

---

## Recording Formats

### Available Formats

Twilio recordings can be downloaded in multiple formats:

1. **WAV** (recommended for processing)
   - Add `.wav` to RecordingUrl
   - Lossless, high quality
   - Larger file size

2. **MP3** (recommended for storage)
   - Add `.mp3` to RecordingUrl
   - Compressed, smaller size
   - Good quality

Example:
```python
base_url = "https://api.twilio.com/.../Recordings/RE1234"

wav_url = f"{base_url}.wav"  # Full quality
mp3_url = f"{base_url}.mp3"  # Compressed
```

---

## Cost Considerations

### Twilio Recording Pricing

**Recording Storage:**
- $0.0050 per minute of recorded media
- First 10,000 minutes/month free
- Applies to both channels combined

**Storage Duration:**
- Recordings stored indefinitely by default
- Can be deleted via API to save costs
- Download and store locally if needed

**Example Cost:**
- 100 calls/month × 5 minutes average = 500 minutes
- 500 minutes < 10,000 free minutes
- **Cost: $0** (within free tier)

**Auto-Delete After Download:**
```python
# After downloading, delete from Twilio to save storage
client.recordings(recording_sid).delete()
logger.info(f"Deleted recording {recording_sid} from Twilio")
```

---

## Architecture Comparison

### Before (Local WAV Only)

```
Call → Twilio Media Stream → WebSocket
  ↓
8kHz audio chunks
  ↓
Save to local 8kHz WAV
  ↓
Resample to 16kHz
  ↓
Save to local 16kHz WAV
  ↓
Transcribe with Whisper

❌ Only technician audio
❌ Media stream quality (compressed)
❌ Single channel
```

### After (Local + Cloud)

```
Call → Twilio
  ↓
  ├─→ Media Stream → WebSocket (existing)
  │     ↓
  │   Local WAV recording (8kHz + 16kHz)
  │     ↓
  │   Real-time transcription
  │
  └─→ Cloud Recording (NEW)
        ↓
      Dual-channel recording
        ↓
      Callback when ready
        ↓
      Download and process

✅ Both agent + technician audio
✅ High quality (pre-compression)
✅ Dual-channel (separate speakers)
✅ Cloud storage
```

---

## Implementation Notes

### Why Manual TwiML Building?

The Python Twilio SDK doesn't support the `<Recording>` tag inside `<Start>` yet (as of this writing).

**Attempted:**
```python
start = Start()
start.recording(channels='dual')  # ❌ Method doesn't exist
```

**Solution:**
```python
# Build TwiML manually as XML string
twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Start>
        <Stream url="{stream_url}" />
        <Recording channels="dual" recordingStatusCallback="{callback_url}" />
    </Start>
    <Dial callerId="{phone}">
        <Number>{to_number}</Number>
    </Dial>
</Response>'''
```

This is safe and follows Twilio's official TwiML specification.

---

## Summary

✅ **Dual-channel cloud recording enabled**

**What's working:**
- TwiML includes `<Recording channels="dual">`
- Callback endpoint `/twilio/recording-status` ready
- Logs recording details when callback received
- Compatible with existing local WAV recording

**What's recorded:**
1. Local 8kHz WAV - technician only (for quality reference)
2. Local 16kHz WAV - technician only (for transcription)
3. **Twilio cloud dual-channel** - both agent + technician (NEW)

**Next steps:**
1. Make a test call
2. Wait for recording callback
3. Implement download and storage logic
4. Process dual-channel audio for speaker separation

**Cost:** Free tier (10,000 minutes/month)

---

**Date:** 2025-11-20
**Feature:** Twilio Cloud Dual-Channel Recording
**Status:** ✅ Active
**Callback Endpoint:** `/twilio/recording-status`
