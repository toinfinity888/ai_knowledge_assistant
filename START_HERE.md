# 🚀 START HERE - Real-time Support Assistant

## Installation (One Command!)

Your real-time support assistant system is built and ready. To install and test it:

```bash
# Make sure you're in the virtual environment
source /Users/saraevsviatoslav/Documents/.venv/bin/activate

# Run the installation script
./install_and_test.sh
```

This script will:
1. ✅ Install all dependencies
2. ✅ Check system configuration
3. ✅ Initialize database tables
4. ✅ Run complete integration tests

---

## If You Get "ModuleNotFoundError"

If you see errors like `ModuleNotFoundError: No module named 'sqlalchemy'`, it means dependencies aren't installed yet. Just run:

```bash
pip install -r requirements.txt
```

Then try again:
```bash
python examples/test_realtime_flow.py
```

---

## After Installation

Once tests pass, your system is ready! Next steps:

### 1. Load Knowledge Base (if not already done)
```bash
python app/cli/upload.py
```

### 2. Start the Server
```bash
python main.py
```

Server will run on `http://localhost:8080`

### 3. API Endpoints Available
- `POST /api/realtime/call/start` - Start call session
- `POST /api/realtime/transcription` - Send transcription
- `POST /api/realtime/call/end` - End call
- `WS /api/realtime/ws/<session_id>` - WebSocket connection
- `GET /api/realtime/suggestions/<session_id>` - Get suggestions

### 4. Configure ACD Webhooks
Point your ACD system to send events to:
- Call start: `http://your-server:8080/api/realtime/call/start`
- Transcription: `http://your-server:8080/api/realtime/transcription`
- Call end: `http://your-server:8080/api/realtime/call/end`

### 5. Connect Support Agent UI
Use WebSocket to receive real-time suggestions:
```javascript
const ws = new WebSocket('ws://your-server:8080/api/realtime/ws/<session_id>');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // Display suggestions to support agent
};
```

---

## Documentation

📚 **Complete Guides:**
- [INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md) - Detailed installation
- [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - Quick commands & API
- [REALTIME_SYSTEM_GUIDE.md](REALTIME_SYSTEM_GUIDE.md) - Full integration guide
- [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) - Visual diagrams
- [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - What was built

---

## Troubleshooting

### "ModuleNotFoundError"
```bash
pip install -r requirements.txt
```

### "Field required for 'host'"
Your `.env` file is already configured correctly. If you see this error, check that `QDRANT_HOST` is set.

### "Database connection failed"
Make sure PostgreSQL is running:
```bash
brew services start postgresql@14
# Or check status
brew services list | grep postgresql
```

### Still Having Issues?
Run the setup check:
```bash
python check_setup.py
```

This will verify:
- ✅ Python version
- ✅ Environment variables
- ✅ Dependencies
- ✅ Database connection
- ✅ Qdrant connection
- ✅ OpenAI API

---

## What Was Built

This system provides **AI-powered real-time suggestions** to support agents during customer calls:

### 🤖 **3 AI Agents**
- **Context Analyzer** - Extracts entities (error codes, products, versions)
- **Query Formulator** - Creates optimized search queries
- **Clarification Agent** - Generates questions when info is missing

### 📊 **Database Schema**
- `call_sessions` - Call tracking
- `transcription_segments` - Conversation history
- `agent_actions` - AI decision logs
- `suggestions` - Generated suggestions with feedback

### 🔌 **Integrations**
- **ACD Adapters** - Twilio, Genesys, Avaya, Generic Webhook
- **CRM Adapters** - Salesforce, Zendesk, HubSpot

### 🌐 **Real-time APIs**
- REST endpoints for ACD integration
- WebSocket for live UI updates
- Complete logging and analytics

---

## System Flow

```
Customer Call → ACD Transcription → AI Agents → RAG Search → Suggestions → Support Agent UI
```

The system:
1. Receives transcription from your ACD
2. Analyzes conversation context with AI
3. Searches your knowledge base
4. Sends real-time suggestions to support agent's screen

---

## Quick Test

After installation, test the full flow:

```bash
python examples/test_realtime_flow.py
```

This simulates:
- Starting a call
- Customer describing an issue ("Error 401 on login")
- Agents analyzing context
- Generating suggestions
- Ending the call

---

**Ready to get started? Run: `./install_and_test.sh`** 🚀
