# ngrok Guide - Complete Setup

## Current Status ✅

Your ngrok is **already running**!

```bash
Process ID: 72561
Command: ngrok http 8000
Current URL: wss://uncrusted-laurena-reflexly.ngrok-free.dev
```

---

## Quick Commands

### Check if ngrok is Running

```bash
ps aux | grep ngrok | grep -v grep
```

**Output if running:**
```
saraevsviatoslav 72561   0.0  0.1 411602864  10064 s031  S+    3Nov25  24:46.00 ngrok http 8000
```

**Output if NOT running:**
```
(empty - no output)
```

### View ngrok Dashboard

Open in browser:
```
http://localhost:4040
```

This shows:
- ✅ Current public URL
- ✅ All HTTP/WebSocket requests in real-time
- ✅ Request/response details for debugging

### Stop ngrok

```bash
# Option 1: Find process and kill
pkill ngrok

# Option 2: Kill by process ID
kill 72561

# Option 3: If in the terminal where ngrok is running
Ctrl+C
```

### Start ngrok

```bash
# Basic command (expose port 8000)
ngrok http 8000

# With custom domain (requires paid plan)
ngrok http 8000 --domain=your-custom-domain.ngrok-free.app

# With authentication
ngrok http 8000 --auth="username:password"

# With region
ngrok http 8000 --region=eu  # Europe
ngrok http 8000 --region=us  # United States
ngrok http 8000 --region=ap  # Asia Pacific
```

---

## Complete Setup Guide

### 1. First-Time Setup (Authentication)

If you haven't authenticated ngrok yet:

```bash
# Get your authtoken from: https://dashboard.ngrok.com/get-started/your-authtoken
ngrok config add-authtoken YOUR_AUTHTOKEN_HERE
```

**Free tier includes:**
- ✅ 1 online ngrok process
- ✅ 40 connections/minute
- ✅ HTTPS endpoints
- ✅ WebSocket support

### 2. Start ngrok for Your Server

**Option A: Simple (Random URL)**
```bash
cd /Users/saraevsviatoslav/Documents/ai_knowledge_assistant
ngrok http 8000
```

You'll see:
```
ngrok

Session Status                online
Account                       Your Name (Plan: Free)
Version                       3.32.0
Region                        United States (us)
Latency                       45ms
Web Interface                 http://127.0.0.1:4040
Forwarding                    https://abc123xyz.ngrok-free.app -> http://localhost:8000

Connections                   ttl     opn     rt1     rt5     p50     p90
                              0       0       0.00    0.00    0.00    0.00
```

Copy the HTTPS URL: `https://abc123xyz.ngrok-free.app`

**Option B: Background (Recommended for Development)**
```bash
# Start in background
ngrok http 8000 > /dev/null 2>&1 &

# Get the URL programmatically
curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"[^"]*' | grep -o 'https://[^"]*'
```

**Option C: Static Domain (Paid Plan)**
```bash
ngrok http 8000 --domain=your-static-domain.ngrok-free.app
```

### 3. Update Your .env File

After starting ngrok, copy the URL and update `.env`:

```bash
# Get the ngrok URL
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"https://[^"]*' | cut -d'"' -f4)

echo "Your ngrok URL: $NGROK_URL"

# Update .env manually or with sed
# Change from:
TWILIO_WEBSOCKET_URL=wss://uncrusted-laurena-reflexly.ngrok-free.dev/twilio/media-stream

# To:
TWILIO_WEBSOCKET_URL=wss://NEW_URL.ngrok-free.app/twilio/media-stream
```

**Important:** Change `https://` to `wss://` for WebSocket URLs!

### 4. Restart Your Flask Server

After updating `.env`, restart:

```bash
# Stop current server (Ctrl+C or)
lsof -ti:8000 | xargs kill -9

# Start server
cd /Users/saraevsviatoslav/Documents/ai_knowledge_assistant
python main.py
```

---

## Testing Your ngrok Setup

### Test 1: Check Tunnel is Active

```bash
curl -s http://localhost:4040/api/tunnels | python3 -m json.tool
```

Should show:
```json
{
  "tunnels": [
    {
      "name": "command_line",
      "public_url": "https://abc123.ngrok-free.app",
      "proto": "https",
      "config": {
        "addr": "http://localhost:8000",
        "inspect": true
      }
    }
  ]
}
```

### Test 2: HTTP Endpoint

```bash
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"https://[^"]*' | cut -d'"' -f4)

curl -s $NGROK_URL/twilio/test-twiml
```

Should return TwiML XML.

### Test 3: WebSocket Endpoint

Open in browser console:
```javascript
const ws = new WebSocket('wss://YOUR_NGROK_URL.ngrok-free.app/twilio/call-status/test-123');

ws.onopen = () => console.log('✅ WebSocket connected');
ws.onerror = (e) => console.error('❌ WebSocket error:', e);
ws.onmessage = (e) => console.log('📥 Received:', e.data);
```

### Test 4: From Twilio

Make a test call and check ngrok dashboard at http://localhost:4040

You should see:
- 📞 POST requests to `/twilio/status`
- 🔌 WebSocket upgrades to `/twilio/media-stream`
- 📊 Request/response details

---

## Common Issues & Solutions

### Issue 1: "ngrok: command not found"

**Solution: Install ngrok**

```bash
# macOS with Homebrew
brew install ngrok/ngrok/ngrok

# Or download directly
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | \
  sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null && \
  echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | \
  sudo tee /etc/apt/sources.list.d/ngrok.list && \
  sudo apt update && sudo apt install ngrok
```

### Issue 2: "ERR_NGROK_108: You must sign up"

**Solution:**
```bash
# Sign up at https://dashboard.ngrok.com/signup
# Get your authtoken from https://dashboard.ngrok.com/get-started/your-authtoken
ngrok config add-authtoken YOUR_AUTHTOKEN
```

### Issue 3: URL Changes Every Time

**Problem:** Free tier generates random URLs

**Solutions:**
1. **Use static domain (Paid plan ~$8/month):**
   ```bash
   ngrok http 8000 --domain=your-name.ngrok-free.app
   ```

2. **Auto-update .env on startup:**
   ```bash
   #!/bin/bash
   # start_dev.sh

   # Start ngrok in background
   ngrok http 8000 > /dev/null 2>&1 &
   sleep 2

   # Get URL
   NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"https://[^"]*' | cut -d'"' -f4)

   # Update .env
   sed -i '' "s|TWILIO_WEBSOCKET_URL=.*|TWILIO_WEBSOCKET_URL=wss://${NGROK_URL#https://}/twilio/media-stream|" .env

   echo "✅ ngrok URL updated: $NGROK_URL"

   # Start Flask
   python main.py
   ```

3. **Use localtunnel (alternative):**
   ```bash
   npm install -g localtunnel
   lt --port 8000 --subdomain your-preferred-name
   ```

### Issue 4: "ngrok: ERR_NGROK_6022: Account limit reached"

**Problem:** Free tier allows 1 tunnel at a time

**Solution:**
```bash
# Stop all existing ngrok processes
pkill ngrok

# Start new tunnel
ngrok http 8000
```

### Issue 5: WebSocket Closes Immediately

**Check:**
1. URL uses `wss://` not `ws://`
2. Flask server is running
3. No firewall blocking WebSocket
4. Check ngrok dashboard for errors

**Debug:**
```bash
# In ngrok dashboard (http://localhost:4040), check:
# - Status code (should be 101 Switching Protocols)
# - Headers (should include "Upgrade: websocket")
```

### Issue 6: Twilio Can't Reach Webhook

**Check:**
1. ngrok is running: `ps aux | grep ngrok`
2. URL is correct in Twilio Console
3. Flask server is running: `curl http://localhost:8000/`
4. No typos in URL

**Test webhook manually:**
```bash
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"https://[^"]*' | cut -d'"' -f4)

curl -X POST "$NGROK_URL/twilio/incoming" \
  -d "From=+15551234567" \
  -d "To=+15557654321" \
  -d "CallSid=CA1234567890abcdef"
```

---

## Production Alternative

For production, ngrok is NOT recommended. Use one of these instead:

### Option 1: Deploy to Cloud with Public Domain

**Providers:**
- **Heroku:** Free tier available
- **Railway:** Free tier with custom domains
- **Render:** Free tier with SSL
- **AWS/GCP/Azure:** Pay-as-you-go

**Setup:**
```bash
# Example with Heroku
heroku create your-app-name
git push heroku main
heroku config:set TWILIO_WEBSOCKET_URL=wss://your-app-name.herokuapp.com/twilio/media-stream
```

### Option 2: VPS with Domain

**Setup:**
```bash
# Buy VPS (DigitalOcean, Linode, Vultr)
# Buy domain (Namecheap, Google Domains)
# Point domain to VPS IP
# Install nginx + Let's Encrypt SSL
# Configure nginx to proxy WebSocket
```

**nginx config:**
```nginx
server {
    listen 443 ssl;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    location /twilio/media-stream {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

### Option 3: Cloudflare Tunnel (Free)

**Setup:**
```bash
# Install cloudflared
brew install cloudflare/cloudflare/cloudflared

# Authenticate
cloudflared tunnel login

# Create tunnel
cloudflared tunnel create my-tunnel

# Route traffic
cloudflared tunnel route dns my-tunnel yourdomain.com

# Run tunnel
cloudflared tunnel --url http://localhost:8000 run my-tunnel
```

**Advantages:**
- ✅ Free
- ✅ Static domain
- ✅ Automatic SSL
- ✅ DDoS protection
- ✅ Better than ngrok for production

---

## Quick Reference

| Command | Purpose |
|---------|---------|
| `ngrok http 8000` | Start tunnel for port 8000 |
| `ngrok http 8000 --domain=xyz.ngrok-free.app` | Static domain |
| `curl http://localhost:4040/api/tunnels` | Get tunnel info (JSON) |
| `pkill ngrok` | Stop all ngrok processes |
| `ps aux \| grep ngrok` | Check if running |
| `ngrok version` | Check version |
| `ngrok config check` | Verify configuration |
| `ngrok diagnose` | Run diagnostics |

---

## Your Current Setup

```bash
# Check status
ps aux | grep ngrok | grep -v grep

# View dashboard
open http://localhost:4040

# Get current URL
curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"https://[^"]*'

# Your configured URL in .env
TWILIO_WEBSOCKET_URL=wss://uncrusted-laurena-reflexly.ngrok-free.dev/twilio/media-stream
```

**Note:** Your ngrok has been running since **November 3rd** (24+ hours of uptime). Free tier ngrok tunnels expire after 2 hours of inactivity, but stay active with traffic.

If you haven't restarted ngrok, the URL `uncrusted-laurena-reflexly.ngrok-free.dev` should still be active!

---

## Next Steps

1. ✅ Verify ngrok is running: `ps aux | grep ngrok`
2. ✅ Check dashboard: http://localhost:4040
3. ✅ Make test call from Twilio interface
4. ✅ Watch requests in ngrok dashboard
5. ✅ Check Flask server logs for WebSocket connections

**Everything should be working already!** 🚀
