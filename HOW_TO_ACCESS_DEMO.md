# How to Access the Demo with Transcription

## ❌ Wrong Page
You opened: **http://localhost:8080/**
- This is the OLD simple RAG interface
- No microphone, no transcription
- Just a text input box

## ✅ Correct Page
Go to: **http://localhost:8080/demo/**
- Has microphone button
- Shows live transcription
- Displays AI suggestions
- French language configured (fr-FR)

---

## Step-by-Step Guide

### 1. Make sure the server is running
```bash
# Check if it's running
ps aux | grep "python.*main.py"

# If not running, start it:
python main.py
```

### 2. Open the correct URL
```
http://localhost:8080/demo/
```

**NOT:** ~~http://localhost:8080/~~ (this is the old page)

### 3. You should see:
- 🎤 Large microphone button
- 📝 "Transcription" section (on the left)
- 💡 "AI Suggestions" section (on the right)
- Status indicator

### 4. Click the microphone button
- Browser will ask for microphone permission → Allow it
- Button should turn red (recording)
- Speak in **French** (configured on line 414 of demo/index.html)

### 5. Watch for transcription
As you speak, you should see:
- **Transcription appears** in the left panel
- Shows "Customer:" or "Agent:" label
- Text updates in real-time

### 6. AI Suggestions appear
After a few seconds:
- Right panel shows **AI-generated suggestions**
- Based on what you said
- Includes solutions from knowledge base

---

## Troubleshooting

### Problem: "There is no transcript"

**Check these:**

1. **Are you on the right URL?**
   - ✅ Correct: `http://localhost:8080/demo/`
   - ❌ Wrong: `http://localhost:8080/`

2. **Did you click the microphone button?**
   - Should be RED when recording
   - Check browser's microphone icon (top right)

3. **Is your browser supported?**
   - ✅ Chrome/Edge: Full support
   - ⚠️ Firefox: Limited support
   - ❌ Safari: Not working

4. **Did you allow microphone permission?**
   - Check browser's address bar
   - Look for 🎤 icon
   - Click and select "Allow"

5. **Are you speaking in French?**
   - Currently configured for French (fr-FR)
   - Browser might not recognize other languages

### Problem: Microphone button doesn't work

**Solution:**
1. Open browser console (F12)
2. Check for errors
3. Look for "Speech recognition error"
4. Try Chrome instead of Safari

### Problem: Transcription appears but no suggestions

**Check:**
1. Open browser console (F12)
2. Look for network errors
3. Check if backend is running: `ps aux | grep python`
4. Test backend: `curl http://localhost:8080/demo/start-demo-call -X POST -H "Content-Type: application/json" -d '{}'`

---

## Alternative: Python Demo (No Browser Needed)

If the web demo doesn't work, use Python demo:

```bash
python -m app.demo.microphone_demo
```

This uses:
- Whisper AI (better accuracy)
- Terminal output (no browser)
- Already configured for French

---

## Quick Test

Run this in your terminal:
```bash
# Test that server is responding
curl http://localhost:8080/demo/

# Should return HTML with "Real-time Support Assistant Demo"
```

If you see HTML, the server is working. Just open:
```
http://localhost:8080/demo/
```

---

## Current Configuration Summary

| Setting | Value |
|---------|-------|
| Server | Running on port 8080 |
| Demo URL | http://localhost:8080/demo/ |
| Language | French (fr-FR) |
| Browser | Chrome/Edge recommended |
| Whisper Model | base (for Python demo) |

---

## Still Not Working?

1. Restart the server:
```bash
# Kill all Python processes
pkill -f "python.*main.py"

# Start fresh
python main.py
```

2. Clear browser cache:
   - Press Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows)

3. Try incognito mode:
   - Cmd+Shift+N (Mac) or Ctrl+Shift+N (Windows)

4. Check the logs:
```bash
# In the terminal where main.py is running
# Look for errors when you click the microphone button
```
