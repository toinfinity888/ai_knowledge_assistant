# Fix JWT Token Issue - Create Twilio API Keys

## Problem
The JWT token generation is failing because we're using Account SID + Auth Token instead of proper API Keys. Twilio requires API Keys for generating valid access tokens.

## Solution: Create Twilio API Keys

### Step 1: Create API Key in Twilio Console

1. Go to: https://console.twilio.com/us1/account/keys-credentials/api-keys
2. Click **"Create API Key"** button
3. Fill in:
   - **Friendly Name**: `ai-assistant-browser-calling`
   - **Region**: (leave default)
4. Click **"Create API Key"**
5. **IMPORTANT**: Copy both values immediately (they won't be shown again):
   - **SID**: Starts with `SK...` (e.g., `SKxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`)
   - **Secret**: Long random string

### Step 2: Add to .env File

Add these two lines to your `.env` file:

```bash
TWILIO_API_KEY_SID=SKxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_API_KEY_SECRET=your_secret_here
```

### Step 3: Update twilio_config.py

The config file already supports these fields, just make sure they're optional:

```python
class TwilioSettings(BaseSettings):
    account_sid: str
    auth_token: str
    phone_number: str
    websocket_url: Optional[str] = None

    # Add these for proper JWT token generation
    api_key_sid: Optional[str] = None
    api_key_secret: Optional[str] = None
    twiml_app_sid: Optional[str] = None
```

### Step 4: Restart Server

After adding the API keys to `.env`:

```bash
# Kill old server (Ctrl+C)
# Start fresh
PORT=8000 python main.py
```

### Step 5: Test

1. Open http://localhost:8000/demo/technician
2. Check browser console - should see:
   ```
   ✓ Twilio Device is ready for calls
   Device status: ready
   Device identity: support-agent
   ✓ En ligne - Prêt à recevoir des appels
   ```
3. Call your Twilio number - browser should ring!

---

## Why This Is Needed

- **Account SID + Auth Token**: Used for REST API calls (making/ending calls)
- **API Key SID + Secret**: Required for generating JWT tokens for Twilio Client SDK
- Without proper API Keys, the browser can't authenticate with Twilio's client infrastructure

---

## Quick Test

After setup, test the token endpoint:

```bash
curl -X POST http://localhost:8000/twilio/token \
  -H "Content-Type: application/json" \
  -d '{"identity": "support-agent"}'
```

Should return:
```json
{
  "token": "eyJhbGc...(long JWT token)",
  "identity": "support-agent"
}
```

If the token is very short or you get an error, the API keys are incorrect.
