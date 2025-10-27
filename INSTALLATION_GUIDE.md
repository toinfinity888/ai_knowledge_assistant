# Installation Guide - Real-time Support Assistant

## Prerequisites

- Python 3.9 or higher
- PostgreSQL 14+
- Access to OpenAI API
- Access to Qdrant Cloud (or local Qdrant instance)

---

## Step-by-Step Installation

### Step 1: Activate Your Virtual Environment

You already have a virtual environment at `/Users/saraevsviatoslav/Documents/.venv`. Activate it:

```bash
cd /Users/saraevsviatoslav/Documents/ai_knowledge_assistant
source /Users/saraevsviatoslav/Documents/.venv/bin/activate
```

You should see `(.venv)` in your terminal prompt.

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- Flask & Flask-Sock (web framework + WebSocket)
- SQLAlchemy & psycopg2 (database)
- OpenAI (LLM)
- Qdrant-client (vector database)
- Pydantic (configuration)
- And all other dependencies

### Step 3: Verify .env File

Your `.env` file should already be configured. Verify it has:

```bash
cat .env
```

Should show:
```
QDRANT_HOST=c5eca447-18c1-469d-9d27-41e6f6a4172e.eu-west-2-0.aws.cloud.qdrant.io
QDRANT_API_KEY=your_key
OPENAI_API_KEY=sk-proj-...
DATABASE_URL=postgresql://postgres:password@localhost:5433/ai_assistant_evaluation_history
```

### Step 4: Check Setup

```bash
python check_setup.py
```

This will verify:
- ✅ Python version
- ✅ Environment variables
- ✅ Required packages
- ✅ Database connection
- ✅ Qdrant connection
- ✅ OpenAI API access

### Step 5: Initialize Database Tables

```bash
python app/database/init_call_tracking.py
```

This creates 4 new tables:
- `call_sessions`
- `transcription_segments`
- `agent_actions`
- `suggestions`

### Step 6: Run Tests

```bash
python examples/test_realtime_flow.py
```

This simulates a complete call session with:
- Call start
- Multiple transcription segments
- Agent processing
- Suggestion generation
- Call end

---

## Troubleshooting

### Issue: "No module named 'flask'"

**Solution:** Make sure you're in the virtual environment:
```bash
source /Users/saraevsviatoslav/Documents/.venv/bin/activate
pip install -r requirements.txt
```

### Issue: "Field required for 'host'"

**Solution:** Your `.env` file needs `QDRANT_HOST`:
```bash
# Add this line to .env
QDRANT_HOST=c5eca447-18c1-469d-9d27-41e6f6a4172e.eu-west-2-0.aws.cloud.qdrant.io
```

### Issue: "Database connection failed"

**Solution:** Check PostgreSQL is running:
```bash
# Check if PostgreSQL is running
ps aux | grep postgres

# Or start it (macOS)
brew services start postgresql@14

# Or start manually
pg_ctl -D /usr/local/var/postgres start
```

### Issue: "Qdrant connection failed"

**Solution:** Verify your Qdrant credentials:
```bash
# Test connection manually
python -c "from qdrant_client import QdrantClient; client = QdrantClient(url='https://your-host:6333', api_key='your_key'); print(client.get_collections())"
```

---

## Quick Commands Reference

```bash
# Activate environment
source /Users/saraevsviatoslav/Documents/.venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Check setup
python check_setup.py

# Initialize database
python app/database/init_call_tracking.py

# Run tests
python examples/test_realtime_flow.py

# Start server
python main.py
```

---

## What to Do Next (After Installation)

Once all checks pass:

1. **Load Knowledge Base** (if not done):
   ```bash
   python app/cli/upload.py
   ```

2. **Test the system**:
   ```bash
   python examples/test_realtime_flow.py
   ```

3. **Start the server**:
   ```bash
   python main.py
   ```

4. **Configure ACD webhooks** to point to:
   - `http://your-server:8080/api/realtime/call/start`
   - `http://your-server:8080/api/realtime/transcription`
   - `http://your-server:8080/api/realtime/call/end`

5. **Connect support agent UI** via WebSocket:
   - `ws://your-server:8080/api/realtime/ws/<session_id>`

---

## Directory Structure After Installation

```
ai_knowledge_assistant/
├── .env                    ← Environment variables
├── .venv/                  ← Virtual environment (already exists)
├── requirements.txt        ← Dependencies
├── check_setup.py          ← Setup verification script
├── main.py                 ← Flask application entry point
│
├── app/
│   ├── agents/             ← AI agents (new)
│   ├── api/                ← API endpoints (new)
│   ├── services/           ← Business logic (new)
│   ├── models/             ← Database models (new)
│   ├── integrations/       ← ACD/CRM adapters (new)
│   └── database/           ← Database utilities
│
├── examples/
│   └── test_realtime_flow.py   ← End-to-end test (new)
│
└── docs/
    ├── REALTIME_SYSTEM_GUIDE.md
    ├── QUICK_REFERENCE.md
    ├── SYSTEM_ARCHITECTURE.md
    └── IMPLEMENTATION_SUMMARY.md
```

---

## Dependencies Installed

### Core Framework
- **flask** - Web framework
- **flask-sock** - WebSocket support
- **gunicorn** - Production WSGI server

### Database
- **sqlalchemy** - ORM
- **psycopg2-binary** - PostgreSQL adapter

### AI/ML
- **openai** - GPT-4o and embeddings
- **qdrant-client** - Vector database
- **sentence-transformers** - Alternative embeddings
- **langchain** - LLM utilities
- **ragas** - RAG evaluation

### Utilities
- **pydantic** - Configuration and validation
- **pydantic-settings** - Settings management
- **python-dotenv** - Environment variables
- **pandas** - Data processing

---

## Success Checklist

- [ ] Virtual environment activated
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] `.env` file configured
- [ ] `check_setup.py` passes all checks
- [ ] Database tables created
- [ ] Test script runs successfully
- [ ] Server starts without errors

---

**Once all items are checked, your system is ready for integration!**

For detailed usage, see [REALTIME_SYSTEM_GUIDE.md](REALTIME_SYSTEM_GUIDE.md)
