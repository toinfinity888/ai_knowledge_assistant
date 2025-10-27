# Real-time Support Assistant System - Integration Guide

## Overview

This system provides **AI-powered real-time suggestions** to customer support agents during live calls. It integrates between your ACD (Automatic Call Distribution) system and CRM, analyzing call transcriptions in real-time to surface relevant knowledge base articles, solutions, and clarifying questions.

---

## Architecture

```
┌─────────────────┐
│   ACD System    │ (Twilio, Genesys, Avaya, etc.)
│   - Call Events │
│   - Transcripts │
└────────┬────────┘
         │ Webhooks/API
         ▼
┌────────────────────────────────────────────────┐
│        Real-time Transcription Service         │
│  - Receives transcription segments             │
│  - Triggers agent pipeline                     │
└────────┬───────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────────┐
│           Agent Orchestrator                   │
│  ┌──────────────────────────────────────────┐  │
│  │  1. Context Analyzer Agent               │  │
│  │     • Analyzes conversation context      │  │
│  │     • Extracts entities (errors, products)│  │
│  │     • Determines if context is sufficient │  │
│  └──────────────────┬───────────────────────┘  │
│                     ▼                           │
│  ┌──────────────────────────────────────────┐  │
│  │  2. Query Formulation Agent              │  │
│  │     • Generates optimized queries        │  │
│  │     • Combines entities + issue          │  │
│  │     • Creates semantic queries           │  │
│  └──────────────────┬───────────────────────┘  │
│                     ▼                           │
│  ┌──────────────────────────────────────────┐  │
│  │  3. RAG Engine                           │  │
│  │     • Searches knowledge base            │  │
│  │     • Retrieves relevant articles        │  │
│  │     • Generates answers                  │  │
│  └──────────────────┬───────────────────────┘  │
│                     ▼                           │
│  ┌──────────────────────────────────────────┐  │
│  │  4. Clarification Agent (if needed)      │  │
│  │     • Generates clarifying questions     │  │
│  │     • Identifies missing information     │  │
│  └──────────────────────────────────────────┘  │
└────────┬───────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────────┐
│        Support Agent UI (WebSocket/SSE)        │
│  - Displays real-time suggestions              │
│  - Shows clarifying questions                  │
│  - Provides feedback mechanism                 │
└────────────────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────────┐
│            CRM System Integration              │
│  - Customer data                               │
│  - Case creation                               │
│  - Interaction history                         │
└────────────────────────────────────────────────┘
```

---

## Quick Start

### 1. Database Initialization

```bash
# Initialize database tables
python app/database/init_call_tracking.py
```

This creates tables:
- `call_sessions` - Active and historical call sessions
- `transcription_segments` - Transcribed conversation segments
- `agent_actions` - AI agent decision logs
- `suggestions` - Generated suggestions for support agents

### 2. System Initialization

```python
from app.init_realtime_system import initialize_realtime_system

# Initialize all components
components = initialize_realtime_system({
    "min_context_confidence": 0.6,
    "max_suggestions": 5,
})
```

### 3. Start Flask Application

```bash
python main.py
```

The following endpoints will be available:

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/realtime/call/start` | Start new call session |
| POST | `/api/realtime/call/end` | End call session |
| POST | `/api/realtime/transcription` | Receive transcription segment |
| GET | `/api/realtime/suggestions/<session_id>` | Get suggestions |
| WS | `/api/realtime/ws/<session_id>` | WebSocket for real-time updates |
| GET | `/api/realtime/stream/<session_id>` | Server-Sent Events stream |

---

## API Integration Examples

### Starting a Call Session

```bash
curl -X POST http://localhost:8080/api/realtime/call/start \
  -H "Content-Type: application/json" \
  -d '{
    "call_id": "acd-call-12345",
    "agent_id": "agent-42",
    "agent_name": "John Smith",
    "customer_id": "cust-999",
    "customer_phone": "+1234567890",
    "customer_name": "Jane Doe",
    "acd_metadata": {
      "queue": "technical_support",
      "wait_time": 45
    },
    "crm_metadata": {
      "tier": "premium",
      "account_age_days": 365
    }
  }'
```

**Response:**
```json
{
  "status": "success",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "call_id": "acd-call-12345"
}
```

### Sending Transcription Segments

```bash
curl -X POST http://localhost:8080/api/realtime/transcription \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "speaker": "customer",
    "text": "I am getting error 401 when trying to log in to the mobile app version 2.5",
    "start_time": 10.5,
    "end_time": 15.2,
    "confidence": 0.95
  }'
```

**Response:**
```json
{
  "status": "processed",
  "segment_id": 123,
  "suggestions_count": 2,
  "questions_count": 1,
  "processing_time_ms": 450
}
```

### WebSocket Connection (JavaScript)

```javascript
const sessionId = "550e8400-e29b-41d4-a716-446655440000";
const ws = new WebSocket(`ws://localhost:8080/api/realtime/ws/${sessionId}`);

ws.onopen = () => {
  console.log("Connected to real-time suggestions");
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  if (data.type === "suggestions") {
    // Display suggestions to support agent
    displaySuggestions(data.suggestions);
    displayQuestions(data.clarifying_questions);
  }
};

// Send feedback
function sendFeedback(suggestionId, feedback) {
  ws.send(JSON.stringify({
    type: "feedback",
    suggestion_id: suggestionId,
    feedback: feedback  // "helpful", "not_helpful", "irrelevant"
  }));
}
```

### Ending a Call

```bash
curl -X POST http://localhost:8080/api/realtime/call/end \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "completed"
  }'
```

---

## ACD Integration

### Supported ACD Systems

The system provides integration adapters for:

1. **Generic Webhook** - Works with any ACD that can send webhooks
2. **Twilio Flex** - Native Twilio integration
3. **Genesys Cloud** - Genesys Platform API
4. **Avaya** - Avaya Experience Platform

### Configuring ACD Integration

```python
from app.integrations.acd_integration import create_acd_integration

# Example: Twilio Flex
acd = create_acd_integration("twilio", {
    "account_sid": "ACxxxxx",
    "auth_token": "your_token",
    "workspace_sid": "WSxxxxx"
})

await acd.connect()
await acd.subscribe_to_call_events(agent_id="agent-42")
```

### Webhook Configuration

Configure your ACD to send events to:

- **Call Start:** `POST /api/realtime/call/start`
- **Transcription:** `POST /api/realtime/transcription`
- **Call End:** `POST /api/realtime/call/end`

---

## CRM Integration

### Supported CRM Systems

1. **Salesforce** - Full integration with Contacts, Cases
2. **Zendesk** - Users, Tickets, Comments
3. **HubSpot** - Contacts, Tickets

### Configuring CRM Integration

```python
from app.integrations.crm_integration import create_crm_integration

# Example: Salesforce
crm = create_crm_integration("salesforce", {
    "instance_url": "https://your-instance.salesforce.com",
    "username": "your_username",
    "password": "your_password",
    "security_token": "your_token"
})

await crm.connect()

# Get customer info
customer = await crm.get_customer_by_phone("+1234567890")
history = await crm.get_customer_history(customer["id"])
```

---

## Agent System Details

### 1. Context Analyzer Agent

**Purpose:** Analyzes conversation context to determine if there's enough information to search the knowledge base.

**Outputs:**
- `has_sufficient_context`: Boolean
- `detected_issue`: Main customer problem
- `detected_entities`: List of entities (products, error codes, versions)
- `needs_clarification`: Whether more info is needed

**Example:**
```python
Input: "I can't log in, getting error 401 on mobile app v2.5"

Output:
{
  "has_sufficient_context": True,
  "detected_issue": "login_problem",
  "detected_entities": [
    {"type": "error_code", "value": "401"},
    {"type": "product_name", "value": "mobile app"},
    {"type": "version", "value": "2.5"}
  ],
  "confidence": 0.85
}
```

### 2. Query Formulation Agent

**Purpose:** Transforms conversation context into optimized queries for the knowledge base.

**Strategies:**
- **Entity-based:** Combines entities with issue ("401 login_problem mobile app")
- **Semantic:** Uses customer's natural language
- **LLM-enhanced:** Reformulates queries for better results

**Example:**
```python
Output:
{
  "queries": [
    {
      "text": "401 authentication error mobile app login",
      "type": "entity_based_error_code",
      "confidence": 0.9
    },
    {
      "text": "mobile app version 2.5 login failed",
      "type": "entity_combination",
      "confidence": 0.85
    }
  ]
}
```

### 3. Clarification Agent

**Purpose:** Generates intelligent clarifying questions when context is insufficient.

**Activates when:**
- Vague problem description
- Missing key entities
- No search results found

**Example:**
```python
Input: "My app doesn't work"

Output:
{
  "questions": [
    {
      "text": "What specifically isn't working as expected?",
      "purpose": "clarify_vague_issue",
      "priority": 1
    },
    {
      "text": "Do you see any error message or error code?",
      "purpose": "get_error_code",
      "priority": 1
    }
  ]
}
```

---

## Monitoring & Analytics

### Agent Performance Tracking

All agent actions are logged to the `agent_actions` table:

```sql
SELECT
    agent_name,
    action_type,
    AVG(processing_time_ms) as avg_time,
    AVG(confidence) as avg_confidence,
    COUNT(*) as total_actions
FROM agent_actions
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY agent_name, action_type;
```

### Suggestion Effectiveness

```sql
SELECT
    suggestion_type,
    COUNT(*) as total_suggestions,
    SUM(CASE WHEN shown_to_agent THEN 1 ELSE 0 END) as shown,
    SUM(CASE WHEN agent_clicked THEN 1 ELSE 0 END) as clicked,
    AVG(confidence_score) as avg_confidence
FROM suggestions
GROUP BY suggestion_type;
```

### Feedback Analysis

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

## Testing

### Run Complete System Test

```bash
python examples/test_realtime_flow.py
```

This simulates:
1. Call start
2. Full conversation with transcription
3. Suggestion generation
4. Call end

### Test Individual Agents

```python
from app.init_realtime_system import initialize_realtime_system
import asyncio

components = initialize_realtime_system()
orchestrator = components["orchestrator"]

# Test context analyzer
result = await orchestrator.context_agent.process({
    "conversation_text": "Customer: I have error 401 on login",
    "customer_last_message": "I have error 401 on login"
})

print(result.data)
```

---

## Deployment Considerations

### Environment Variables

```bash
# OpenAI
OPENAI_API_KEY=sk-...

# Qdrant
QDRANT_URL=https://your-cluster.cloud.qdrant.io
QDRANT_API_KEY=your_api_key
QDRANT_COLLECTION=enterprise_docs

# PostgreSQL
DATABASE_URL=postgresql://user:password@localhost:5432/ai_knowledge_assistant

# ACD (if using Twilio)
TWILIO_ACCOUNT_SID=ACxxxxx
TWILIO_AUTH_TOKEN=xxxxx

# CRM (if using Salesforce)
SALESFORCE_USERNAME=your_username
SALESFORCE_PASSWORD=your_password
SALESFORCE_SECURITY_TOKEN=your_token
```

### Performance Optimization

1. **Agent Processing:** Runs asynchronously, typically 200-500ms per transcription
2. **Throttling:** Minimum 2 seconds between processing for same session
3. **Caching:** Active sessions cached in memory
4. **Query Optimization:** Top 3 queries executed per context

### Scaling

- **Horizontal:** Run multiple Flask instances behind load balancer
- **WebSocket:** Use Redis for WebSocket session persistence
- **Database:** Connection pooling with SQLAlchemy
- **Qdrant:** Cloud cluster for vector search

---

## Troubleshooting

### Common Issues

**1. No suggestions generated**
- Check RAG engine is initialized with knowledge base
- Verify Qdrant collection has embedded documents
- Check OpenAI API key is valid

**2. WebSocket connection fails**
- Ensure `flask-sock` is installed
- Check firewall allows WebSocket connections
- Verify session_id is valid

**3. Transcription not processed**
- Verify speaker is "customer" (by default, only customer speech is processed)
- Check throttling (minimum 2s between processing)
- Review logs for agent errors

### Logs

```bash
# Check application logs
tail -f logs/app.log

# Check agent actions in database
psql -d ai_knowledge_assistant -c "SELECT * FROM agent_actions ORDER BY timestamp DESC LIMIT 10;"
```

---

## Support & Documentation

- **System Architecture:** See [Architecture](#architecture)
- **API Reference:** See [API Integration Examples](#api-integration-examples)
- **Agent Details:** See [Agent System Details](#agent-system-details)
- **Examples:** `examples/test_realtime_flow.py`

---

## License

Internal company use only.

---

**Last Updated:** 2025-10-23
