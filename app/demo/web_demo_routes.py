"""
Web-based Demo Routes
Simple web interface for testing the system with microphone
"""
from flask import Blueprint, render_template, request, jsonify
import asyncio
import time

# Create blueprint for demo
demo_bp = Blueprint('demo', __name__, url_prefix='/demo')


def run_async(coro):
    """Helper to run async functions in sync Flask routes"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@demo_bp.route('/')
def index():
    """Demo homepage with microphone interface"""
    return render_template('demo/index.html')


@demo_bp.route('/agent-ui')
def agent_ui():
    """Support agent UI demo"""
    return render_template('demo/agent_ui.html')


@demo_bp.route('/start-demo-call', methods=['POST'])
def start_demo_call():
    """Start a demo call session"""
    from app.services.realtime_transcription_service import get_transcription_service

    data = request.get_json()

    call_id = f"demo-{int(time.time())}"
    customer_name = data.get('customer_name', 'Demo Customer')
    agent_name = data.get('agent_name', 'Demo Agent')

    transcription_service = get_transcription_service()

    # Run async function in sync context
    result = run_async(transcription_service.handle_call_start(
        call_id=call_id,
        agent_id="demo-agent-1",
        agent_name=agent_name,
        customer_id="demo-customer-1",
        customer_name=customer_name,
        acd_metadata={"type": "demo", "source": "web"},
        crm_metadata={"demo": True},
    ))

    return jsonify(result), 200


@demo_bp.route('/send-demo-transcription', methods=['POST'])
def send_demo_transcription():
    """Send transcription from web demo"""
    from app.services.realtime_transcription_service import get_transcription_service

    data = request.get_json()

    transcription_service = get_transcription_service()

    # Extract language code (e.g., 'fr-FR' -> 'fr', 'en-US' -> 'en')
    language_code = data.get('language', 'en-US')
    language = language_code.split('-')[0]  # Get just the language part

    # Run async function in sync context
    result = run_async(transcription_service.process_transcription_segment(
        session_id=data['session_id'],
        speaker=data.get('speaker', 'customer'),
        text=data['text'],
        start_time=data.get('start_time', 0.0),
        end_time=data.get('end_time', 0.0),
        confidence=data.get('confidence', 0.9),
        language=language  # Pass language to processing
    ))

    # Get suggestions
    suggestions_result = run_async(transcription_service.get_session_suggestions(
        session_id=data['session_id'],
        limit=10
    ))

    return jsonify({
        'processing': result,
        'suggestions': suggestions_result.get('suggestions', [])
    }), 200


@demo_bp.route('/end-demo-call', methods=['POST'])
def end_demo_call():
    """End demo call session"""
    from app.services.realtime_transcription_service import get_transcription_service

    data = request.get_json()

    transcription_service = get_transcription_service()

    # Run async function in sync context
    result = run_async(transcription_service.handle_call_end(
        session_id=data['session_id'],
        status='completed'
    ))

    return jsonify(result), 200
