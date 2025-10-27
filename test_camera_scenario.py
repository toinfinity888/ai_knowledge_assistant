"""
Test Camera Subscription Scenario
Tests the full pipeline with a real customer issue
"""
import asyncio
import sys
import os
from datetime import datetime

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from app.init_realtime_system import initialize_realtime_system


async def test_camera_subscription_issue():
    """
    Test with real customer scenario about camera subscription
    """
    print("="*80)
    print("TESTING CAMERA SUBSCRIPTION SCENARIO")
    print("="*80)
    print()

    # Initialize system
    print("Initializing system...")
    components = initialize_realtime_system()
    orchestrator = components["orchestrator"]
    session_manager = components["session_manager"]
    transcription_service = components["transcription_service"]

    print("✓ System ready\n")

    # Create a test session with unique ID
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    call_id = f"test-camera-{timestamp}"

    print("Creating test call session...")
    result = await transcription_service.handle_call_start(
        call_id=call_id,
        agent_id="agent-test",
        agent_name="Test Agent",
        customer_id="customer-brian",
        customer_name="Brian",
        customer_phone="+1234567890"
    )

    session_id = result["session_id"]
    print(f"✓ Session created: {session_id}\n")

    # Customer describes the issue (from your example)
    customer_issue = """I am paying for a 10 camera subscription and have been for years.
    Last week my camera stopped recording and I show no subscription on my account.
    I can not see any previous recordings nor will any activity record for me to view.
    I get a notification when the motion is tripped and an indicator of a recording
    but when click to view I get "No recordings". I have called support for the past three days
    with no success. This occurs on both the mobile app and on the web link."""

    print("="*80)
    print("CUSTOMER ISSUE:")
    print("="*80)
    print(customer_issue)
    print("="*80)
    print()

    # Process the transcription
    print("Processing with AI agents...")
    print("-"*80)

    result = await transcription_service.process_transcription_segment(
        session_id=session_id,
        speaker="customer",
        text=customer_issue,
        start_time=0.0,
        end_time=10.0,
        confidence=0.95
    )

    print(f"✓ Processing: {result['status']}")
    if result.get('suggestions_count'):
        print(f"✓ Generated {result['suggestions_count']} suggestions")
    if result.get('questions_count'):
        print(f"✓ Generated {result['questions_count']} clarifying questions")
    print()

    # Get suggestions
    print("="*80)
    print("AI-GENERATED SUGGESTIONS FOR SUPPORT AGENT:")
    print("="*80)
    print()

    suggestions_result = await transcription_service.get_session_suggestions(
        session_id=session_id,
        limit=10
    )

    if suggestions_result.get('suggestions'):
        for i, suggestion in enumerate(suggestions_result['suggestions'], 1):
            print(f"\n[SUGGESTION {i}]")
            print(f"Type: {suggestion['type'].upper()}")
            print(f"Title: {suggestion['title']}")
            print("-"*80)
            print(f"Content:\n{suggestion['content']}")
            print("-"*80)
            if suggestion.get('confidence'):
                print(f"Confidence: {suggestion['confidence']:.0%}")
            print()
    else:
        print("⚠ No suggestions found")
        print()
        print("This might mean:")
        print("1. Knowledge base is empty or not loaded")
        print("2. No matching documents for this query")
        print()
        print("To load your knowledge base:")
        print("  python app/cli/upload.py")
        print()

    # Show what entities were detected
    print("="*80)
    print("DETECTED INFORMATION:")
    print("="*80)

    # Get conversation context
    context = session_manager.get_conversation_context(session_id)

    # Get agent actions to see what was detected
    from app.database.postgresql_session import get_db_session
    from app.models.call_session import AgentAction, CallSession

    with get_db_session() as db:
        call_session = db.query(CallSession).filter(
            CallSession.session_id == session_id
        ).first()

        if call_session:
            actions = db.query(AgentAction).filter(
                AgentAction.session_id == call_session.id
            ).order_by(AgentAction.timestamp).all()

            for action in actions:
                print(f"\n{action.agent_name}:")
                print(f"  Status: {action.status}")
                if action.confidence:
                    print(f"  Confidence: {action.confidence:.0%}")

                # Show detected entities
                if action.agent_name == "context_analyzer" and action.output_data:
                    output = action.output_data.get('data', {})
                    if output.get('detected_issue'):
                        print(f"  Detected Issue: {output['detected_issue']}")
                    if output.get('detected_entities'):
                        print(f"  Detected Entities:")
                        for entity in output['detected_entities'][:5]:
                            print(f"    - {entity.get('type')}: {entity.get('value')}")

                # Show generated queries
                if action.agent_name == "query_formulation" and action.output_data:
                    output = action.output_data.get('data', {})
                    if output.get('queries'):
                        print(f"  Generated Queries:")
                        for query in output['queries'][:3]:
                            print(f"    - {query.get('text')} (confidence: {query.get('confidence', 0):.0%})")

    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)

    # End session
    await transcription_service.handle_call_end(session_id, status='completed')


if __name__ == "__main__":
    asyncio.run(test_camera_subscription_issue())
