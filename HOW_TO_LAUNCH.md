# 🚀 How to Launch Your Real-time Support Assistant

## Quick Start (One Command)

```bash
./launch.sh
```

That's it! The script will:
- Check dependencies
- Start the Flask server
- Display all available endpoints

---

## Manual Launch

### Step 1: Navigate to project
```bash
cd /Users/saraevsviatoslav/Documents/ai_knowledge_assistant
```

### Step 2: Start the server
```bash
python main.py
```

The server starts on **`http://localhost:8080`**

---

## What Happens When You Launch

When you run the server, it will:

1. ✅ Initialize RAG engine
2. ✅ Load AI agents (Context Analyzer, Query Formulator, Clarification)
3. ✅ Connect to Qdrant vector database
4. ✅ Connect to PostgreSQL
5. ✅ Setup WebSocket server
6. ✅ Register all API endpoints

You'll see output like:
```
======================================================================
INITIALIZING REAL-TIME SUPPORT ASSISTANT SYSTEM
======================================================================

[1/6] Initializing Call Session Manager...
✓ Call Session Manager ready

[2/6] Initializing RAG Engine...
✓ RAG Engine ready

[3/6] Initializing LLM (OpenAI GPT-4o)...
✓ LLM ready

[4/6] Initializing Agent Orchestrator...
✓ Agent Orchestrator ready

[5/6] Initializing Real-time Transcription Service...
✓ Transcription Service ready

[6/6] Checking database tables...
✓ Database ready

System ready!

 * Running on http://0.0.0.0:8080
```

---

## Available Endpoints

Once running, your API endpoints are:

### REST API
```bash
# Start a call session
POST http://localhost:8080/api/realtime/call/start

# Send transcription segment
POST http://localhost:8080/api/realtime/transcription

# End call session
POST http://localhost:8080/api/realtime/call/end

# Get suggestions
GET http://localhost:8080/api/realtime/suggestions/<session_id>

# Feedback on suggestion
POST http://localhost:8080/api/realtime/suggestions/<id>/feedback
```

### WebSocket
```
ws://localhost:8080/api/realtime/ws/<session_id>
```

### Server-Sent Events
```
http://localhost:8080/api/realtime/stream/<session_id>
```

---

## Testing the Running Server

### Test 1: Start a Call (with curl)
```bash
curl -X POST http://localhost:8080/api/realtime/call/start \
  -H "Content-Type: application/json" \
  -d '{
    "call_id": "test-call-001",
    "agent_id": "agent-john",
    "agent_name": "John Smith",
    "customer_phone": "+1234567890"
  }'
```

### Test 2: Send Transcription
```bash
curl -X POST http://localhost:8080/api/realtime/transcription \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "YOUR_SESSION_ID_FROM_STEP_1",
    "speaker": "customer",
    "text": "I am getting error 401 when trying to log in",
    "start_time": 0.0,
    "end_time": 3.5
  }'
```

### Test 3: Get Suggestions
```bash
curl http://localhost:8080/api/realtime/suggestions/YOUR_SESSION_ID
```

---

## WebSocket Test (JavaScript)

Open your browser console on any page and run:

```javascript
const sessionId = "YOUR_SESSION_ID";
const ws = new WebSocket(`ws://localhost:8080/api/realtime/ws/${sessionId}`);

ws.onopen = () => {
  console.log("✓ Connected to real-time suggestions");
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log("Received:", data);

  if (data.type === "suggestions") {
    console.log("New suggestions:", data.suggestions);
  }
};

ws.onerror = (error) => {
  console.error("WebSocket error:", error);
};
```

---

## Stopping the Server

Press **`Ctrl+C`** in the terminal where the server is running.

---

## Production Deployment

### With Gunicorn (Recommended)
```bash
gunicorn -w 4 -b 0.0.0.0:8080 main:app --timeout 120
```

Options:
- `-w 4` = 4 worker processes
- `-b 0.0.0.0:8080` = Bind to all interfaces on port 8080
- `--timeout 120` = 2 minute timeout for long-running requests

### With Docker
```bash
# Build image
docker build -t ai-support-assistant .

# Run container
docker run -p 8080:8080 \
  -e OPENAI_API_KEY=your_key \
  -e QDRANT_HOST=your_host \
  -e DATABASE_URL=your_db_url \
  ai-support-assistant
```

---

## Troubleshooting

### Port Already in Use
If you see "Address already in use":
```bash
# Find process using port 8080
lsof -i :8080

# Kill it
kill -9 <PID>

# Or use a different port
PORT=8081 python main.py
```

### Database Connection Error
Make sure PostgreSQL is running:
```bash
brew services start postgresql@14
```

### Qdrant Connection Error
Check your `.env` file has correct Qdrant credentials:
```bash
cat .env | grep QDRANT
```

### Dependencies Missing
```bash
pip install -r requirements.txt
```

---

## Next Steps After Launch

### 1. Configure Your ACD System
Point your ACD webhooks to:
- `http://your-server:8080/api/realtime/call/start`
- `http://your-server:8080/api/realtime/transcription`
- `http://your-server:8080/api/realtime/call/end`

### 2. Build Support Agent UI
Connect via WebSocket to receive real-time suggestions:
```javascript
const ws = new WebSocket('ws://your-server:8080/api/realtime/ws/<session_id>');
```

### 3. Monitor Performance
Check logs and database for agent performance:
```sql
SELECT agent_name, AVG(processing_time_ms), COUNT(*)
FROM agent_actions
GROUP BY agent_name;
```

---

## Quick Commands Reference

```bash
# Launch server
./launch.sh

# Or manually
python main.py

# With Gunicorn (production)
gunicorn -w 4 -b 0.0.0.0:8080 main:app

# Check if running
curl http://localhost:8080/

# View logs
tail -f logs/app.log

# Stop server
Ctrl+C
```

---

**Your real-time support assistant is ready to launch!** 🎉

Simply run: **`./launch.sh`**
