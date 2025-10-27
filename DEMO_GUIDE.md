# 🎤 Microphone Demo Guide - MVP

## Overview

This demo allows you to test the real-time support assistant using your computer's microphone - **no ACD or CRM integration needed!**

You can demonstrate the full system by speaking into your microphone and watching AI-generated suggestions appear in real-time.

---

## 🚀 Quick Start

### Option 1: Web Interface (Easiest)

1. **Start the server:**
   ```bash
   python main.py
   ```

2. **Open the demo in your browser:**
   ```
   http://localhost:8080/demo
   ```

3. **Click the microphone button** and start speaking!

---

### Option 2: Python Script (Advanced)

For a command-line demo with Whisper transcription:

```bash
# Install additional dependency
pip install faster-whisper sounddevice scipy

# Run the demo
python app/demo/microphone_demo.py
```

---

## 🎯 What You Get

### **Web Demo Features:**
- ✅ **Browser-based** speech recognition (Chrome/Edge)
- ✅ **Real-time transcription** display
- ✅ **Live AI suggestions** as you speak
- ✅ **No external dependencies** needed
- ✅ **Beautiful UI** with visual feedback

### **Python Demo Features:**
- ✅ **Whisper AI** for accurate transcription
- ✅ **Works offline** (no internet needed for transcription)
- ✅ **Multiple language support**
- ✅ **Higher accuracy** than browser speech recognition

---

## 📺 Demo Walkthrough

### Step 1: Open the Demo
Navigate to `http://localhost:8080/demo`

You'll see:
- 🎙️ Left panel: Microphone button & transcript
- 💡 Right panel: AI-generated suggestions

### Step 2: Start Recording
1. Enter a customer name (optional)
2. Enter an agent name (optional)
3. Click the microphone button 🎤

### Step 3: Describe a Problem
Speak clearly and describe a technical issue. Examples:

**Example 1:**
> "Hello, I'm having trouble logging into the application. When I try to log in, I get error code 401. I'm using the mobile app version 2.5 on iOS."

**Example 2:**
> "My payment failed. I keep getting an error message saying 'Payment declined' even though my card is valid."

**Example 3:**
> "The application is very slow. It takes forever to load the dashboard."

### Step 4: Watch the Magic! ✨
As you speak, you'll see:
1. **Transcript appears** in real-time
2. **AI analyzes** your speech
3. **Suggestions appear** on the right:
   - 💡 Knowledge base articles
   - ❓ Clarifying questions (if info is missing)
   - 🔍 Possible solutions

### Step 5: Stop Recording
Click the microphone button again to stop.

---

## 💡 Demo Scenarios

### Scenario 1: Clear Problem (Generates Solutions)
**What to say:**
> "I'm getting error 401 when trying to log in to the mobile app version 2.5"

**Expected AI Response:**
- ✅ Detects: Error code 401, login problem, mobile app, version 2.5
- ✅ Generates: Solutions from knowledge base
- ✅ Confidence: High

---

### Scenario 2: Vague Problem (Asks Questions)
**What to say:**
> "My app doesn't work. It's broken."

**Expected AI Response:**
- ❓ Asks clarifying questions:
  - "What specifically isn't working as expected?"
  - "Do you see any error message or error code?"
  - "Which product or feature does this concern?"
- ✅ Confidence: Medium (needs more info)

---

### Scenario 3: Complex Problem (Multiple Suggestions)
**What to say:**
> "I changed my password yesterday and now I can't log in. I keep getting authentication failed error code 401 on the iOS mobile app version 2.5."

**Expected AI Response:**
- ✅ Detects: Password change, authentication, error 401, iOS, mobile app, v2.5
- ✅ Generates: Multiple relevant solutions
- ✅ Shows: Step-by-step troubleshooting
- ✅ Confidence: Very High

---

## 🔧 How It Works

```
1. You speak → Microphone captures audio
2. Browser/Whisper transcribes → Text appears
3. AI Context Analyzer → Detects issue & entities
4. AI Query Formulator → Creates optimized queries
5. RAG Engine → Searches knowledge base
6. Suggestions appear → Support agent sees solutions!
```

---

## 🎨 UI Features

### Status Indicators
- **Green**: Ready to start
- **Red**: Recording in progress
- **Orange**: Processing with AI

### Suggestion Types
- 💡 **Knowledge Base** (green border): Solutions from your docs
- ❓ **Clarifying Questions** (orange border): When AI needs more info

### Confidence Scores
Each suggestion shows how confident the AI is (0-100%)

---

## ⚙️ Configuration

### Change Transcription Language

**Web Demo** (edit HTML):
```javascript
recognition.lang = 'fr-FR';  // French
recognition.lang = 'ru-RU';  // Russian
recognition.lang = 'es-ES';  // Spanish
```

**Python Demo** (edit script):
```python
segments, info = self.whisper_model.transcribe(
    wav_path,
    language="fr"  // French, "ru" for Russian, etc.
)
```

### Adjust Transcription Interval
Change how often audio is transcribed:

**Python Demo:**
```python
demo = MicrophoneDemo(
    segment_duration=2.0,  # Transcribe every 2 seconds (default: 3)
)
```

### Choose Whisper Model
Trade speed vs accuracy:

**Python Demo:**
```python
demo = MicrophoneDemo(
    whisper_model="tiny",   # Fastest, less accurate
    # whisper_model="base",  # Good balance (default)
    # whisper_model="small", # Better accuracy, slower
    # whisper_model="medium" # Best accuracy, slowest
)
```

---

## 🐛 Troubleshooting

### "Microphone access denied"
**Solution:** Grant microphone permission in browser settings

### "Speech recognition not supported"
**Solution:** Use Chrome, Edge, or Safari (not Firefox)

### No suggestions appearing
**Solution:**
1. Make sure knowledge base is loaded in Qdrant
2. Speak clearly with technical terms
3. Check server logs for errors

### Poor transcription quality
**Solution:**
- Use the Python demo with Whisper (more accurate)
- Speak slowly and clearly
- Use a better microphone
- Reduce background noise

### Server crashes during demo
**Solution:**
- Check database connection
- Verify OpenAI API key is valid
- Check Qdrant connection

---

## 📊 Demo Tips

### For Best Results:

1. **Speak clearly** and at normal pace
2. **Use technical terms** (error codes, versions, product names)
3. **Be specific** ("error 401" vs "it doesn't work")
4. **Wait 2-3 seconds** between sentences for processing
5. **Use real scenarios** from your knowledge base

### What Makes Good Demo Content:

✅ **Good:** "I'm getting error 401 authentication failed on mobile app v2.5"
❌ **Bad:** "It's not working"

✅ **Good:** "Payment declined with Stripe error, card ending in 1234"
❌ **Bad:** "Payment problem"

---

## 🎬 Demo Presentation Script

### Opening (30 seconds)
> "This is our AI-powered real-time support assistant. It listens to customer conversations and instantly provides relevant solutions to support agents."

### Demo (2 minutes)
1. Click microphone
2. Say: "I'm having trouble logging in. I get error 401 on the mobile app version 2.5."
3. Watch suggestions appear
4. Point out:
   - Real-time transcription
   - Entity detection (error 401, mobile app, v2.5)
   - Multiple suggestions with confidence scores

### Closing (30 seconds)
> "The system uses AI agents to analyze conversations, search our knowledge base, and provide instant suggestions - reducing resolution time and improving customer satisfaction."

---

## 📈 Measuring Demo Impact

After the demo, you can show:

### Database Analytics
```sql
-- Show suggestions generated
SELECT COUNT(*) FROM suggestions;

-- Show agent processing times
SELECT agent_name, AVG(processing_time_ms)
FROM agent_actions
GROUP BY agent_name;

-- Show suggestion confidence
SELECT AVG(confidence_score) FROM suggestions;
```

### Key Metrics to Highlight:
- ⚡ **Response time**: 200-500ms per suggestion
- 🎯 **Accuracy**: High confidence scores (>80%)
- 📚 **Coverage**: Multiple suggestions per issue
- 🤖 **Intelligence**: Detects entities automatically

---

## 🔄 Next Steps After Demo

1. **Load real knowledge base** (if not done):
   ```bash
   python app/cli/upload.py
   ```

2. **Integrate with real ACD/CRM** for production

3. **Customize agents** for your specific use cases

4. **Train on your data** for better accuracy

5. **Build production UI** based on demo feedback

---

## 🆘 Need Help?

- Check [HOW_TO_LAUNCH.md](HOW_TO_LAUNCH.md) for server setup
- See [QUICK_REFERENCE.md](QUICK_REFERENCE.md) for API details
- Review [REALTIME_SYSTEM_GUIDE.md](REALTIME_SYSTEM_GUIDE.md) for architecture

---

**Ready to demo? Run: `python main.py` and visit `http://localhost:8080/demo`** 🎉
