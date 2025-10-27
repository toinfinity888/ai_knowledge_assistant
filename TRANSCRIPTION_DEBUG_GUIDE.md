# Transcription Not Showing - Debug Guide

## Changes Made ✅

I've updated the demo to show:
1. **Real-time interim transcripts** (you'll see text appear as you speak)
2. **Better error messages** (tells you exactly what's wrong)
3. **Console logging** (so we can debug)

## How to Test

### Step 1: Reload the page
The server doesn't need restarting (Flask auto-reloads templates), just:
1. Go to: http://localhost:8080/demo/
2. Press **Cmd+Shift+R** (Mac) or **Ctrl+Shift+R** (Windows) to hard refresh

### Step 2: Open Browser Console
**Before clicking the microphone button:**
1. Press **F12** (or Cmd+Option+I on Mac)
2. Click the **Console** tab
3. Keep it open

### Step 3: Click Start Button
Watch for these console messages:
```
Starting speech recognition with language: fr-FR
Speech recognition started
```

### Step 4: Speak in French
Say something like:
- "Bonjour, j'ai un problème avec mon abonnement"
- "Ma caméra ne fonctionne pas"
- "Je ne peux pas voir mes enregistrements"

### What You Should See

#### ✅ If it's working:
1. **Status changes to:** "Listening... Speak in French"
2. **Console shows:** "Speech recognized: [your text] isFinal: false"
3. **Transcript shows:** Faded italic text (interim)
4. **When you pause:** Text becomes solid (final)
5. **Console shows:** "Speech recognized: [your text] isFinal: true"

#### ❌ If there's an error:
**Status will show one of:**
- "No speech detected - try speaking louder"
- "Microphone permission denied"
- "French not supported - try Chrome/Edge"
- Other error message

---

## Common Issues & Solutions

### Issue 1: "Microphone permission denied"
**Solution:**
1. Click the 🔒 or 🎤 icon in browser address bar
2. Set "Microphone" to "Allow"
3. Reload the page

### Issue 2: "French not supported"
**Your browser doesn't support French speech recognition**

**Solutions:**
a) **Switch to English temporarily:**
```
Edit line 414 in demo/index.html:
recognition.lang = 'en-US';  // Changed from fr-FR
```

b) **Use Python demo instead** (supports 99+ languages):
```bash
python -m app.demo.microphone_demo
```

### Issue 3: No console messages at all
**The button click isn't working**

**Check:**
1. Are you on the right page? Should be `/demo/` not `/`
2. Any JavaScript errors in console?
3. Try a different browser (Chrome recommended)

### Issue 4: Console shows recognition starting, but no text
**Possible causes:**

**A) You're not speaking French**
- Browser expects French (fr-FR)
- Try saying clear French phrases
- Or switch to English (see Issue 2)

**B) Speaking too quietly**
- Speak louder and clearer
- Check microphone volume in system settings
- Test mic: visit https://webcammictest.com/

**C) Wrong microphone selected**
- Check browser is using correct mic
- System Preferences > Sound > Input

### Issue 5: Interim text shows but never becomes final
**Browser is recognizing speech but not finalizing**

**Solutions:**
- Pause for 1-2 seconds between sentences
- Speak more clearly
- Try shorter phrases

---

## Quick Browser Test

### Test 1: Check if webkitSpeechRecognition exists
Open Console (F12) and type:
```javascript
'webkitSpeechRecognition' in window
```
Should return: `true` (if false, browser not supported)

### Test 2: Test French support
```javascript
const recognition = new webkitSpeechRecognition();
recognition.lang = 'fr-FR';
console.log('Lang set to:', recognition.lang);
```
Should show: "Lang set to: fr-FR"

### Test 3: Start recognition manually
```javascript
const recognition = new webkitSpeechRecognition();
recognition.lang = 'fr-FR';
recognition.onresult = (e) => console.log('Result:', e.results[0][0].transcript);
recognition.onerror = (e) => console.log('Error:', e.error);
recognition.start();
// Now speak in French
```

---

## Alternative: Use English Instead

If French isn't working, here's how to switch to English:

**1. Edit the demo file:**
```bash
# Open in your editor
open /Users/saraevsviatoslav/Documents/ai_knowledge_assistant/app/frontend/templates/demo/index.html
```

**2. Find line 414:**
```javascript
recognition.lang = 'fr-FR';
```

**3. Change to:**
```javascript
recognition.lang = 'en-US';
```

**4. Reload the page** (Cmd+Shift+R)

**5. Speak in English:**
- "Hello, I have a problem with my subscription"
- "My camera is not recording"

---

## Check What the Server Sees

**1. Watch the server terminal** where `python main.py` is running

**2. When you speak, you should see:**
```
POST /demo/send-demo-transcription
Session: [session-id]
Text: [what you said]
```

**3. If you don't see these logs:**
- Speech recognition is failing before reaching the server
- Check browser console for errors

---

## Still Not Working?

### Get detailed logs:

**1. Add this to console:**
```javascript
// Enable verbose logging
localStorage.debug = '*';
```

**2. Refresh and click Start**

**3. Copy all console output and check for:**
- "Speech recognition error"
- "Network error"
- "Session not created"

### Try the Python demo instead:
```bash
# This uses Whisper AI - more reliable
python -m app.demo.microphone_demo
```

Python demo advantages:
- Better French support
- More accurate
- Shows debug output directly
- Doesn't depend on browser

---

## Summary of What Should Happen

| Step | What You See | Where to Look |
|------|--------------|---------------|
| 1. Click Start | Status: "Listening..." | Main page |
| 2. Browser asks permission | Popup: "Allow microphone?" | Browser popup |
| 3. Start speaking | Console: "Speech recognized..." | F12 Console |
| 4. Still speaking | Faded italic text appears | Transcript panel (left) |
| 5. Pause speaking | Text becomes solid | Transcript panel |
| 6. AI processing | Status: "Processing with AI..." | Main page |
| 7. Results ready | Suggestions appear | Suggestions panel (right) |

If you don't see these steps happening, note which step fails and check the corresponding section above.
