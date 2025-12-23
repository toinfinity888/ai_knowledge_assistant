"""
Test Real-time Support Assistant Flow
Simulates a complete call session with transcription and suggestions
"""
import sys
import os
import asyncio
import json
import uuid
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.init_realtime_system import initialize_realtime_system


async def simulate_call_session():
    """
    Simulate a complete customer support call with real-time transcription
    """
    print("\n" + "="*80)
    print("SIMULATING CUSTOMER SUPPORT CALL SESSION")
    print("="*80 + "\n")

    # Initialize system
    components = initialize_realtime_system()
    transcription_service = components["transcription_service"]
    session_manager = components["session_manager"]

    # Step 1: Start call
    print("\n[STEP 1] Starting call session...")
    print("-" * 80)

    # Generate unique call_id to avoid database constraint violations
    unique_call_id = f"acd-call-{uuid.uuid4().hex[:8]}-{int(datetime.utcnow().timestamp())}"
    print(f"Generated unique call_id: {unique_call_id}")

    call_result = await transcription_service.handle_call_start(
        call_id=unique_call_id,
        agent_id="agent-john-smith",
        agent_name="John Smith",
        customer_id="cust-999",
        customer_phone="+1234567890",
        customer_name="Jane Doe",
        acd_metadata={"queue": "technical_support", "wait_time": 45},
        crm_metadata={"tier": "premium", "account_age_days": 365},
    )

    print(f"✓ Call started: {json.dumps(call_result, indent=2)}")
    session_id = call_result["session_id"]

    # Step 2: Simulate conversation with transcription segments
    print("\n[STEP 2] Simulating conversation transcription...")
    print("-" * 80)

    conversation_segments = [
        # Customer greeting
        {
            "speaker": "customer",
            "text": "Hello, I need help with something.",
            "start_time": 0.0,
            "end_time": 2.5,
            "confidence": 0.95,
        },
        # Agent greeting
        {
            "speaker": "agent",
            "text": "Hi Jane! I'm John, how can I help you today?",
            "start_time": 2.5,
            "end_time": 5.0,
            "confidence": 0.98,
        },
        # Customer describes issue (vague)
        {
            "speaker": "customer",
            "text": "My application is not working properly. It's really frustrating.",
            "start_time": 5.0,
            "end_time": 9.0,
            "confidence": 0.93,
        },
        # Agent asks for clarification
        {
            "speaker": "agent",
            "text": "I understand that's frustrating. Can you tell me more about what's happening?",
            "start_time": 9.0,
            "end_time": 13.0,
            "confidence": 0.97,
        },
        # Customer provides more details
        {
            "speaker": "customer",
            "text": "When I try to log in, I get an error message. It says 'Authentication failed error code 401'.",
            "start_time": 13.0,
            "end_time": 19.0,
            "confidence": 0.91,
        },
        # More customer details
        {
            "speaker": "customer",
            "text": "I'm using version 2.5 of the mobile app on iOS.",
            "start_time": 19.0,
            "end_time": 22.5,
            "confidence": 0.94,
        },
        # Customer adds context
        {
            "speaker": "customer",
            "text": "This started happening yesterday after I changed my password.",
            "start_time": 22.5,
            "end_time": 26.0,
            "confidence": 0.96,
        },
    ]

    for i, segment in enumerate(conversation_segments):
        print(f"\n--- Segment {i+1}/{len(conversation_segments)} ---")
        print(f"[{segment['speaker'].upper()}] {segment['text']}")

        result = await transcription_service.process_transcription_segment(
            session_id=session_id,
            speaker=segment["speaker"],
            text=segment["text"],
            start_time=segment["start_time"],
            end_time=segment["end_time"],
            confidence=segment["confidence"],
        )

        print(f"Processing result: {result['status']}")

        if result["status"] == "processed":
            print(f"  → Generated {result.get('suggestions_count', 0)} suggestions")
            print(f"  → Generated {result.get('questions_count', 0)} clarifying questions")
            print(f"  → Processing time: {result.get('processing_time_ms', 0)}ms")

        # Small delay to simulate real-time
        await asyncio.sleep(1)

    # Step 3: Retrieve all suggestions
    print("\n[STEP 3] Retrieving all suggestions for the session...")
    print("-" * 80)

    suggestions_result = await transcription_service.get_session_suggestions(
        session_id=session_id,
        limit=20,
    )

    if suggestions_result["status"] == "success":
        suggestions = suggestions_result["suggestions"]
        print(f"\n✓ Found {len(suggestions)} total suggestions:\n")

        for i, suggestion in enumerate(suggestions):
            print(f"{i+1}. [{suggestion['type'].upper()}] {suggestion['title']}")
            print(f"   Confidence: {suggestion.get('confidence', 'N/A')}")
            print(f"   Content preview: {suggestion['content'][:100]}...")
            print(f"   Shown to agent: {suggestion['shown']}")
            print()

    # Step 4: Get conversation context
    print("\n[STEP 4] Retrieving conversation context...")
    print("-" * 80)

    context = session_manager.get_conversation_context(session_id, last_n_segments=10)
    print("\nConversation transcript:")
    print(context)

    # Step 5: End call
    print("\n[STEP 5] Ending call session...")
    print("-" * 80)

    end_result = await transcription_service.handle_call_end(
        session_id=session_id,
        status="completed",
    )

    print(f"✓ Call ended: {json.dumps(end_result, indent=2)}")

    # Summary
    print("\n" + "="*80)
    print("CALL SESSION COMPLETE - SUMMARY")
    print("="*80)
    print(f"Session ID: {session_id}")
    print(f"Total transcription segments: {len(conversation_segments)}")
    print(f"Total suggestions generated: {len(suggestions_result.get('suggestions', []))}")
    print(f"Call duration: {conversation_segments[-1]['end_time']} seconds")

    print("\n✅ Test completed successfully!")


async def test_agent_pipeline():
    """
    Test individual agent components
    """
    print("\n" + "="*80)
    print("TESTING INDIVIDUAL AGENT COMPONENTS")
    print("="*80 + "\n")

    components = initialize_realtime_system()
    orchestrator = components["orchestrator"]

    # Test context
    test_context = {
        "conversation_text": """
        Customer: Hello, I'm having trouble with the login feature.
        Agent: Can you tell me more?
        Customer: When I try to log in to the mobile app, I get error 401.
        Customer: I'm using version 2.5 on iOS.
        """,
        "customer_last_message": "I'm using version 2.5 on iOS.",
    }

    print("\n[TEST 1] Context Analyzer Agent")
    print("-" * 80)
    context_result = await orchestrator.context_agent.process(test_context)
    print(f"Status: {context_result.status}")
    print(f"Has sufficient context: {context_result.data.get('has_sufficient_context')}")
    print(f"Detected issue: {context_result.data.get('detected_issue')}")
    print(f"Detected entities: {context_result.data.get('detected_entities')}")
    print(f"Confidence: {context_result.confidence}")

    print("\n[TEST 2] Query Formulation Agent")
    print("-" * 80)
    query_context = {
        **test_context,
        "detected_issue": context_result.data.get('detected_issue', ''),
        "detected_entities": context_result.data.get('detected_entities', []),
    }
    query_result = await orchestrator.query_agent.process(query_context)
    print(f"Status: {query_result.status}")
    print(f"Generated queries: {len(query_result.data.get('queries', []))}")
    for i, query in enumerate(query_result.data.get('queries', [])[:3]):
        print(f"  {i+1}. {query['text']} (type: {query['type']}, confidence: {query['confidence']})")

    print("\n[TEST 3] Clarification Agent")
    print("-" * 80)
    clarification_context = {
        **test_context,
        "detected_issue": "",
        "detected_entities": [],
        "clarification_needed_for": ["problem_description", "specific_details"],
    }
    clarification_result = await orchestrator.clarification_agent.process(clarification_context)
    print(f"Status: {clarification_result.status}")
    print(f"Generated questions: {len(clarification_result.data.get('questions', []))}")
    for i, question in enumerate(clarification_result.data.get('questions', [])):
        print(f"  {i+1}. {question['text']}")
        print(f"     Purpose: {question.get('purpose', 'N/A')}, Priority: {question.get('priority', 'N/A')}")

    print("\n✅ Agent tests completed!")


if __name__ == "__main__":
    print("\n🚀 Real-time Support Assistant System Test Suite\n")

    # Run tests
    asyncio.run(simulate_call_session())
    print("\n" + "="*80 + "\n")
    asyncio.run(test_agent_pipeline())

    print("\n" + "="*80)
    print("ALL TESTS COMPLETED SUCCESSFULLY!")
    print("="*80 + "\n")
