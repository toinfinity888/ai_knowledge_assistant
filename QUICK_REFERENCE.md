# Real-time Support Assistant - Quick Reference

## 🚀 Getting Started (5 minutes)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables
```bash
export OPENAI_API_KEY="sk-..."
export QDRANT_URL="https://your-cluster.cloud.qdrant.io"
export QDRANT_API_KEY="your_key"
export DATABASE_URL="postgresql://user:pass@localhost:5432/db"
```

### 3. Initialize Database
```bash
python app/database/init_call_tracking.py
```

### 4. Test the System
```bash
python examples/test_realtime_flow.py
```

### 5. Start Server
```bash
python main.py
```

---

## 📡 API Quick Reference

### Start Call
```bash
POST /api/realtime/call/start
{
  "call_id": "acd-12345",
  "agent_id": "agent-42",
  "customer_phone": "+1234567890"
}
```

### Send Transcription
```bash
POST /api/realtime/transcription
{
  "session_id": "uuid",
  "speaker": "customer",
  "text": "I have error 401",
  "start_time": 10.5,
  "end_time": 15.2
}
```

### WebSocket (JavaScript)
```javascript
const ws = new WebSocket(`ws://localhost:8080/api/realtime/ws/${sessionId}`);
ws.onmessage = (e) => console.log(JSON.parse(e.data));
```

### End Call
```bash
POST /api/realtime/call/end
{
  "session_id": "uuid",
  "status": "completed"
}
```

---

## 🤖 Agent Pipeline

```
Transcription → Context Analyzer → Query Formulator → RAG → Suggestions
                      ↓ (if needed)
                 Clarification Agent → Questions
```

**Context Analyzer:** Extracts entities, detects issue
**Query Formulator:** Creates optimized search queries
**Clarification Agent:** Generates questions when info is missing
**RAG Engine:** Searches knowledge base and generates answers

---

## 📊 Database Queries

### Active Calls
```sql
SELECT * FROM call_sessions WHERE status = 'active';
```

### Recent Suggestions
```sql
SELECT suggestion_type, title, confidence_score
FROM suggestions
ORDER BY created_at DESC LIMIT 10;
```

### Agent Performance
```sql
SELECT agent_name, AVG(processing_time_ms), COUNT(*)
FROM agent_actions
WHERE timestamp > NOW() - INTERVAL '1 day'
GROUP BY agent_name;
```

### Suggestion Effectiveness
```sql
SELECT
  agent_feedback,
  COUNT(*) as count,
  AVG(confidence_score) as avg_confidence
FROM suggestions
WHERE agent_feedback IS NOT NULL
GROUP BY agent_feedback;
```

---

## 🔧 Configuration Options

### Agent Orchestrator
```python
config = {
    "min_context_confidence": 0.6,  # Minimum confidence to proceed
    "min_query_results": 1,          # Minimum results needed
    "max_suggestions": 5,            # Max suggestions per call
}
```

### Transcription Service
```python
service.min_processing_interval = 2.0  # Seconds between processing
service.process_only_customer = True    # Only process customer speech
```

---

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| No suggestions | Check knowledge base in Qdrant, verify OpenAI API key |
| WebSocket fails | Install `flask-sock`, check firewall |
| Slow processing | Enable throttling, check DB connection pool |
| Agent errors | Check logs: `tail -f logs/app.log` |

---

## 📁 File Structure

```
ai_knowledge_assistant/
├── app/
│   ├── agents/              # AI agents
│   │   ├── context_analyzer_agent.py
│   │   ├── query_formulation_agent.py
│   │   ├── clarification_agent.py
│   │   └── agent_orchestrator.py
│   ├── api/                 # API endpoints
│   │   └── realtime_routes.py
│   ├── services/            # Business logic
│   │   ├── call_session_manager.py
│   │   └── realtime_transcription_service.py
│   ├── models/              # Database models
│   │   └── call_session.py
│   ├── integrations/        # External systems
│   │   ├── acd_integration.py
│   │   └── crm_integration.py
│   └── init_realtime_system.py  # System initialization
├── examples/
│   └── test_realtime_flow.py    # Testing
├── REALTIME_SYSTEM_GUIDE.md     # Full documentation
└── IMPLEMENTATION_SUMMARY.md    # What we built
```

---

## 🔗 Integration Checklist

- [ ] Database tables created
- [ ] Environment variables set
- [ ] Knowledge base loaded in Qdrant
- [ ] Test flow runs successfully
- [ ] ACD webhook configured
- [ ] Support agent UI connected via WebSocket
- [ ] Monitoring/analytics set up

---

## 💡 Common Patterns

### Test Single Agent
```python
from app.init_realtime_system import initialize_realtime_system
components = initialize_realtime_system()
result = await components["orchestrator"].context_agent.process({
    "conversation_text": "Customer: Error 401 on login"
})
print(result.data)
```

### Get Call History
```python
from app.services.call_session_manager import get_call_session_manager
manager = get_call_session_manager()
context = manager.get_conversation_context(session_id, last_n_segments=10)
```

### Record Feedback
```bash
POST /api/realtime/suggestions/123/feedback
{"feedback": "helpful"}
```

---

## 📚 Documentation Links

- **Full Guide:** [REALTIME_SYSTEM_GUIDE.md](REALTIME_SYSTEM_GUIDE.md)
- **Implementation Details:** [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)
- **Test Suite:** [examples/test_realtime_flow.py](examples/test_realtime_flow.py)

---

## 🆘 Support

**Common Issues:**
1. Import errors → Run `pip install -r requirements.txt`
2. Database errors → Run `python app/database/init_call_tracking.py`
3. No suggestions → Check RAG engine has data in Qdrant
4. Slow performance → Enable throttling, check async processing

**Logs:** `tail -f logs/app.log`
**Database:** `psql -d ai_knowledge_assistant`

---

**Last Updated:** 2025-10-23
