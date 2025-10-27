# 🎤 MVP Demo - Real-time Support Assistant

## 🚀 Quick Launch

### **One Command to Start Demo:**

```bash
./launch_demo.sh
```

Then open: **`http://localhost:8080/demo`**

---

## 🎯 What This Is

A **fully functional MVP demo** that shows your real-time AI support assistant in action - **without needing ACD or CRM integration!**

### You Get:
- ✅ **Browser-based demo** with beautiful UI
- ✅ **Real-time speech recognition** (uses your microphone)
- ✅ **AI-powered suggestions** as you speak
- ✅ **Complete agent pipeline** (Context Analyzer, Query Formulator, Clarification)
- ✅ **Knowledge base search** with RAG
- ✅ **Instant feedback** with confidence scores

---

## 📺 How to Demo

### Step 1: Launch
```bash
./launch_demo.sh
```

### Step 2: Open Browser
Go to: `http://localhost:8080/demo`

### Step 3: Speak
Click the 🎤 microphone button and describe a technical problem:

**Good Example:**
> "I'm getting error 401 when trying to log in to the mobile app version 2.5"

**What Happens:**
1. Your speech is transcribed in real-time
2. AI analyzes: "Error 401", "login", "mobile app", "v2.5"
3. Knowledge base is searched
4. Suggestions appear instantly on screen! 💡

---

## 🎨 Demo Interface

### Left Panel - Customer Voice
- 🎙️ Microphone button (click to start/stop)
- 📝 Live transcription of your speech
- 👤 Customer & agent name fields

### Right Panel - AI Suggestions
- 💡 Knowledge base solutions
- ❓ Clarifying questions (when needed)
- 🎯 Confidence scores for each suggestion

---

## 💡 Demo Scenarios

### Scenario 1: Technical Issue (Best Demo!)
**Say:**
> "I'm getting error 401 authentication failed when logging in"

**AI Will:**
- ✅ Detect: error code, issue type, feature
- ✅ Generate: Relevant solutions from knowledge base
- ✅ Show: High confidence suggestions

---

### Scenario 2: Vague Problem
**Say:**
> "My app doesn't work"

**AI Will:**
- ❓ Ask clarifying questions:
  - "What specifically isn't working?"
  - "Do you see any error message?"
  - "Which product does this concern?"

---

## 🎬 Presentation Script (3 minutes)

### Opening (30 sec)
> "I'll demonstrate our AI-powered support assistant that provides real-time suggestions to agents during customer calls."

### Demo (2 min)
1. **Click microphone** → "Now recording"
2. **Speak clearly:** "I'm getting error 401 when trying to log in to the mobile app version 2.5"
3. **Point out:**
   - Real-time transcription appearing
   - AI detecting entities (401, login, mobile app, v2.5)
   - Multiple suggestions appearing
   - Confidence scores

### Closing (30 sec)
> "The system analyzed the conversation, identified the issue, searched our knowledge base, and provided instant suggestions - all in under a second. This helps agents resolve issues faster and improves customer satisfaction."

---

## 🔧 Technical Details

### What's Running Behind the Scenes:

```
Your Voice → Browser Speech API → Text
     ↓
Context Analyzer Agent → Detects: entities, intent, confidence
     ↓
Query Formulation Agent → Creates: optimized queries
     ↓
RAG Engine → Searches: Qdrant + OpenAI
     ↓
Suggestions → Display: Real-time to UI
```

### Components Active:
- ✅ 3 AI Agents (Context, Query, Clarification)
- ✅ RAG Engine with Qdrant vector search
- ✅ OpenAI GPT-4o for generation
- ✅ PostgreSQL for logging
- ✅ WebSocket for real-time updates

---

## 📊 Metrics to Show

After demo, you can display:

### Processing Speed
```sql
SELECT AVG(processing_time_ms) FROM agent_actions;
-- Expected: 200-500ms
```

### AI Confidence
```sql
SELECT AVG(confidence_score) FROM suggestions WHERE confidence_score > 0.8;
-- Expected: 80-95%
```

### Coverage
```sql
SELECT COUNT(*) FROM suggestions WHERE shown_to_agent = true;
-- Shows how many suggestions were generated
```

---

## 🎯 Demo Best Practices

### Do's ✅
- Speak clearly and at normal pace
- Use technical terms (error codes, versions)
- Wait 2-3 seconds between sentences
- Use realistic customer scenarios
- Show both successful suggestions AND clarifying questions

### Don'ts ❌
- Don't mumble or speak too fast
- Don't use only vague phrases
- Don't speak in noisy environment
- Don't expect instant results (allow 2-3 sec processing)

---

## 🔄 Alternative: Python Demo

For offline demo with better transcription:

```bash
# Install Whisper dependencies
pip install faster-whisper sounddevice scipy

# Run Python demo
python app/demo/microphone_demo.py
```

**Advantages:**
- ✅ Works offline (no internet for transcription)
- ✅ More accurate (Whisper AI)
- ✅ Multi-language support
- ✅ Better for production testing

---

## 🐛 Troubleshooting

### Microphone not working
- Grant browser microphone permission
- Check browser console for errors
- Try Chrome or Edge (best support)

### No suggestions appearing
- Check knowledge base is loaded in Qdrant
- Verify OpenAI API key in `.env`
- Check server logs for errors

### Poor transcription
- Reduce background noise
- Use better microphone
- Speak more clearly
- Try Python demo with Whisper

---

## 📚 Documentation

- **[DEMO_GUIDE.md](DEMO_GUIDE.md)** ← Complete demo instructions
- **[HOW_TO_LAUNCH.md](HOW_TO_LAUNCH.md)** ← Server setup
- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** ← API reference
- **[REALTIME_SYSTEM_GUIDE.md](REALTIME_SYSTEM_GUIDE.md)** ← Full system guide

---

## 🎉 Ready to Demo!

### Quick Start:
```bash
# Launch demo server
./launch_demo.sh

# Open in browser
open http://localhost:8080/demo
```

### What to Say:
> "I'm getting error 401 when trying to log in to the mobile app version 2.5"

### What You'll See:
- 📝 Real-time transcription
- 🤖 AI entity detection
- 💡 Instant suggestions
- 🎯 Confidence scores

---

**Your MVP demo is ready to impress! 🚀**

No ACD, no CRM needed - just your voice and AI magic! ✨
