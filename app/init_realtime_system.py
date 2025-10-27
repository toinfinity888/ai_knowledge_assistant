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
from app.services.realtime_transcription_service import get_transcription_service
from app.core.rag_singleton import get_rag_engine
from app.llm.llm_openai import OpenAILLM
from app.api.realtime_routes import broadcast_to_session


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

    # Step 4: Initialize Agent Orchestrator
    print("\n[4/6] Initializing Agent Orchestrator...")
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
    print("  - Context Analyzer Agent")
    print("  - Query Formulation Agent")
    print("  - Clarification Agent")

    # Step 5: Initialize Real-time Transcription Service
    print("\n[5/6] Initializing Real-time Transcription Service...")
    transcription_service = get_transcription_service(
        session_manager=session_manager,
        orchestrator=orchestrator,
        on_suggestions_ready=broadcast_to_session,  # WebSocket callback
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
    print(f"  • Transcription Service: {transcription_service}")

    print("\n🌐 API Endpoints Available:")
    print("  POST /api/realtime/call/start - Start new call session")
    print("  POST /api/realtime/call/end - End call session")
    print("  POST /api/realtime/transcription - Send transcription segment")
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
        "transcription_service": transcription_service,
    }


if __name__ == "__main__":
    # Initialize system
    components = initialize_realtime_system()

    print("\n✅ System ready for integration!")
    print("\nTo start the Flask application with real-time support:")
    print("  python main.py")
