"""
Real-time Support Assistant System Initialization
This script initializes all components for the ACD/CRM integrated system
"""
import sys
import os
import asyncio

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.call_session_manager import get_call_session_manager
from app.agents.agent_orchestrator import create_agent_orchestrator
from app.agents.gatekeeper_orchestrator import GatekeeperOrchestrator
from app.services.realtime_transcription_service import get_transcription_service
from app.services.validator_service import ValidatorService
from app.services.domain_schema_service import get_domain_schema_service
from app.core.rag_singleton import get_rag_engine
from app.llm.llm_openai import OpenAILLM
from app.llm.llm_groq import GroqLLM
from app.demo.web_demo_routes import broadcast_suggestion

# Module-level gatekeeper for access from API endpoints
_gatekeeper_orchestrator = None


def get_gatekeeper_orchestrator() -> GatekeeperOrchestrator:
    """Get the singleton GatekeeperOrchestrator instance."""
    return _gatekeeper_orchestrator


async def broadcast_suggestions_to_demo(payload: dict):
    """
    Wrapper callback for RealtimeTranscriptionService that broadcasts
    suggestions to the demo WebSocket connections.

    Args:
        payload: Dict containing session_id, suggestions, and clarifying_questions
    """
    session_id = payload.get('session_id')
    suggestions = payload.get('suggestions', [])
    clarifying_questions = payload.get('clarifying_questions', [])

    if not session_id:
        return

    # Broadcast each suggestion
    for suggestion in suggestions:
        broadcast_suggestion(session_id, suggestion)

    # Broadcast clarifying questions as suggestions with type 'clarification_question'
    for question in clarifying_questions:
        question_suggestion = {
            'type': 'clarification_question',
            **question
        }
        broadcast_suggestion(session_id, question_suggestion)

    print(f"📤 Broadcasted {len(suggestions)} suggestions and {len(clarifying_questions)} questions to session {session_id}")


def initialize_realtime_system(config: dict = None):
    """
    Initialize the complete real-time support assistant system

    Returns:
        Dict with all initialized components
    """
    print("=" * 70)
    print("INITIALIZING REAL-TIME SUPPORT ASSISTANT SYSTEM")
    print("=" * 70)

    config = config or {}

    # Step 1: Initialize Session Manager
    print("\n[1/6] Initializing Call Session Manager...")
    session_manager = get_call_session_manager()
    print("✓ Call Session Manager ready")

    # Step 2: Initialize RAG Engine
    print("\n[2/6] Initializing RAG Engine...")
    rag_engine = get_rag_engine()
    print("✓ RAG Engine ready")

    # Step 3: Initialize LLM
    print("\n[3/6] Initializing LLM (OpenAI GPT-4o)...")
    llm = OpenAILLM()
    print("✓ LLM ready")

    # Step 4: Initialize Agent Orchestrator (legacy, kept for transcription service)
    print("\n[4/7] Initializing Agent Orchestrator...")
    orchestrator = create_agent_orchestrator(
        llm=llm,
        rag_engine=rag_engine,
        session_manager=session_manager,
        config={
            "min_context_confidence": config.get("min_context_confidence", 0.6),
            "min_query_results": config.get("min_query_results", 1),
            "max_suggestions": config.get("max_suggestions", 5),
        }
    )
    print("✓ Agent Orchestrator ready")

    # Step 4b: Initialize Intelligence Gatekeeper
    print("\n[4b/7] Initializing Intelligence Gatekeeper...")
    global _gatekeeper_orchestrator
    try:
        groq_llm = GroqLLM()
        domain_schema_service = get_domain_schema_service()
        validator_service = ValidatorService(
            groq_llm=groq_llm,
            domain_schema_service=domain_schema_service,
        )
        _gatekeeper_orchestrator = GatekeeperOrchestrator(
            validator_service=validator_service,
            rag_engine=rag_engine,
            session_manager=session_manager,
        )
        print("✓ Intelligence Gatekeeper ready")
        print("  - Groq Llama 8B Validator")
        print("  - Domain Schema Registry")
    except Exception as e:
        print(f"⚠ Gatekeeper initialization issue: {e}")
        print("  Manual analyze will not work until GROQ_API_KEY is configured")

    # Step 5: Initialize Real-time Transcription Service
    print("\n[5/6] Initializing Real-time Transcription Service...")
    transcription_service = get_transcription_service(
        session_manager=session_manager,
        orchestrator=orchestrator,
        on_suggestions_ready=broadcast_suggestions_to_demo,  # WebSocket callback to demo UI
    )
    print("✓ Transcription Service ready")

    # Step 6: Database initialization check
    print("\n[6/6] Checking database tables...")
    try:
        from app.database.init_call_tracking import init_database
        init_database()
    except Exception as e:
        print(f"⚠ Database initialization issue: {e}")
        print("  You may need to run: python app/database/init_call_tracking.py")

    print("\n" + "=" * 70)
    print("SYSTEM INITIALIZATION COMPLETE!")
    print("=" * 70)

    print("\n📋 System Components:")
    print(f"  • Session Manager: {session_manager}")
    print(f"  • RAG Engine: {rag_engine}")
    print(f"  • LLM: {llm.__class__.__name__}")
    print(f"  • Orchestrator: {orchestrator}")
    print(f"  • Gatekeeper: {_gatekeeper_orchestrator}")
    print(f"  • Transcription Service: {transcription_service}")

    print("\n🌐 API Endpoints Available:")
    print("  POST /api/realtime/call/start - Start new call session")
    print("  POST /api/realtime/call/end - End call session")
    print("  POST /api/realtime/transcription - Send transcription segment")
    print("  POST /api/realtime/analyze - Manual analyze & search (Gatekeeper)")
    print("  POST /demo/analyze - Demo analyze & search (Gatekeeper)")
    print("  GET  /api/realtime/suggestions/<session_id> - Get suggestions")
    print("  WS   /api/realtime/ws/<session_id> - WebSocket connection")
    print("  SSE  /api/realtime/stream/<session_id> - Server-sent events")

    print("\n📚 Next Steps:")
    print("  1. Configure your ACD system to send webhooks to /api/realtime/transcription")
    print("  2. Connect support agent UI to WebSocket endpoint")
    print("  3. Test with example call flow (see examples/test_realtime_flow.py)")

    return {
        "session_manager": session_manager,
        "rag_engine": rag_engine,
        "llm": llm,
        "orchestrator": orchestrator,
        "gatekeeper": _gatekeeper_orchestrator,
        "transcription_service": transcription_service,
    }


if __name__ == "__main__":
    # Initialize system
    components = initialize_realtime_system()

    print("\n✅ System ready for integration!")
    print("\nTo start the Flask application with real-time support:")
    print("  python main.py")
