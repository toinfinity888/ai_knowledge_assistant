"""
Web-based Demo Routes
Simple web interface for testing the system with microphone
"""
from flask import Blueprint, render_template, request, jsonify, session as flask_session
import asyncio
import time
import json
import logging

logger = logging.getLogger(__name__)

# Create blueprint for demo
demo_bp = Blueprint('demo', __name__, url_prefix='/demo')

# Store active suggestion WebSocket connections
_suggestion_connections = {}


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


@demo_bp.route('/technician')
def technician_support():
    """Technician support interface with 3-column layout"""
    # Ensure demo user session is set up for analytics API calls
    if not flask_session.get('user_id'):
        flask_session['user_id'] = 1  # Demo admin user
        flask_session['user_email'] = 'admin@example.com'
        flask_session['company_id'] = 1
        flask_session['company_slug'] = 'demo'
        flask_session['role'] = 'admin'
        logger.info("Demo session initialized for technician support")
    return render_template('demo/technician_support.html')


@demo_bp.route('/twilio-technician')
def twilio_technician():
    """Twilio-based two-way calling interface"""
    return render_template('demo/twilio_technician.html')


@demo_bp.route('/console')
def support_console():
    """
    Simplified Support Console interface.

    Layout:
    - Left 1/3: Transcription (top 2/3) + Call Controls (bottom 1/3, demo only)
    - Right 2/3: Search Results (top 2/3) + Context Analysis (bottom 1/3)
    """
    return render_template('demo/support_console.html')


@demo_bp.route('/get-session-suggestions', methods=['GET'])
def get_session_suggestions():
    """Get suggestions for a session (for polling)"""
    from app.services.realtime_transcription_service import get_transcription_service

    session_id = request.args.get('session_id')
    limit = request.args.get('limit', 10, type=int)

    if not session_id:
        return jsonify({'error': 'Missing session_id'}), 400

    transcription_service = get_transcription_service()

    result = run_async(transcription_service.get_session_suggestions(
        session_id=session_id,
        limit=limit
    ))

    return jsonify(result), 200


@demo_bp.route('/start-demo-call', methods=['POST'])
def start_demo_call():
    """Start a demo call session"""
    from app.services.realtime_transcription_service import get_transcription_service

    data = request.get_json()

    call_id = f"demo-{int(time.time())}"
    customer_name = data.get('customer_name', 'Demo Customer')
    agent_name = data.get('agent_name', 'Demo Agent')

    # Get company_id and user_id from session for analytics tracking
    company_id = flask_session.get('company_id', 1)
    agent_user_id = flask_session.get('user_id')

    transcription_service = get_transcription_service()

    # Run async function in sync context
    result = run_async(transcription_service.handle_call_start(
        call_id=call_id,
        agent_id="demo-agent-1",
        company_id=company_id,
        agent_name=agent_name,
        agent_user_id=agent_user_id,
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
    language_code = data.get('language', 'fr-FR')
    language = language_code.split('-')[0]  # Get just the language part

    # Run async function in sync context
    result = run_async(transcription_service.process_transcription_segment(
        session_id=data['session_id'],
        speaker=data.get('speaker', 'technician'),  # Default to 'technician' (phone caller)
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


@demo_bp.route('/analyze', methods=['POST'])
def demo_analyze():
    """
    Manual analyze & search endpoint (Intelligence Gatekeeper).
    Called when agent clicks "Analyze & Search" button.
    """
    from flask import session as flask_session
    from app.init_realtime_system import get_gatekeeper_orchestrator

    data = request.get_json()
    session_id = data.get('session_id')
    force_search = data.get('force_search', False)
    validate_only = data.get('validate_only', False)
    language = data.get('language', 'fr')
    edited_fields = data.get('edited_fields', {})
    fields_query = data.get('fields_query', '')

    logger.info(f"[Demo Analyze] Request: session_id={session_id}, force_search={force_search}, validate_only={validate_only}, language={language}")
    if edited_fields:
        logger.info(f"[Demo Analyze] Edited fields: {edited_fields}")

    if not session_id:
        logger.warning("[Demo Analyze] Missing session_id in request")
        return jsonify({'error': 'Missing session_id'}), 400

    gatekeeper = get_gatekeeper_orchestrator()
    if gatekeeper is None:
        logger.error("[Demo Analyze] Gatekeeper not initialized - check GROQ_API_KEY")
        return jsonify({
            'error': 'Intelligence Gatekeeper not initialized. Check GROQ_API_KEY.',
            'status': 'error',
        }), 503

    company_id = flask_session.get('company_id', 1)
    logger.info(f"[Demo Analyze] Using company_id={company_id}")

    result = gatekeeper.analyze_and_search(
        session_id=session_id,
        company_id=company_id,
        language=language,
        force_search=force_search,
        validate_only=validate_only,
        edited_fields_query=fields_query,
    )

    logger.info(f"[Demo Analyze] Result: status={result.get('status')}, validation={result.get('validation')}, suggestions_count={len(result.get('suggestions', []))}")

    # Broadcast results via WebSocket if available
    if result.get('suggestions'):
        for suggestion in result['suggestions']:
            broadcast_suggestion(session_id, suggestion)

    return jsonify(result), 200


@demo_bp.route('/session-state/<session_id>', methods=['GET'])
def get_session_state(session_id):
    """
    Get session state for restoring after page reload or connection loss.
    Returns transcription messages and suggestions.
    """
    from app.services.call_session_manager import get_call_session_manager
    from app.database.postgresql_session import get_db_session
    from app.models.call_session import CallSession, TranscriptionSegment, Suggestion

    logger.info(f"[Session State] Fetching state for session: {session_id}")
    session_manager = get_call_session_manager()

    try:
        with get_db_session() as db:
            # Get session
            session = db.query(CallSession).filter(
                CallSession.session_id == session_id
            ).first()

            if not session:
                logger.warning(f"[Session State] Session not found: {session_id}")
                return jsonify({'error': 'Session not found'}), 404

            logger.info(f"[Session State] Found session id={session.id}, status={session.status}")

            # Get transcription segments
            segments = db.query(TranscriptionSegment).filter(
                TranscriptionSegment.session_id == session.id
            ).order_by(TranscriptionSegment.timestamp.asc()).all()

            logger.info(f"[Session State] Found {len(segments)} transcription segments")

            messages = [
                {
                    'text': seg.text,
                    'speaker': seg.speaker,
                    'timestamp': seg.timestamp.isoformat() if seg.timestamp else None,
                }
                for seg in segments
            ]

            # Get suggestions
            suggestions_db = db.query(Suggestion).filter(
                Suggestion.session_id == session.id
            ).order_by(Suggestion.created_at.desc()).all()

            suggestions = [
                {
                    'id': s.id,
                    'type': s.suggestion_type,
                    'title': s.title,
                    'content': s.content,
                    'confidence': s.confidence_score,
                    'source_metadata': s.source_metadata or [],
                }
                for s in suggestions_db
            ]

            logger.info(f"[Session State] Found {len(suggestions)} suggestions")
            logger.info(f"[Session State] Returning: {len(messages)} messages, {len(suggestions)} suggestions")

            return jsonify({
                'session_id': session_id,
                'status': session.status,
                'messages': messages,
                'suggestions': suggestions,
                'start_time': session.start_time.isoformat() if session.start_time else None,
            }), 200

    except Exception as e:
        logger.error(f"Error getting session state: {e}")
        return jsonify({'error': str(e)}), 500


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


def register_demo_websocket_routes(sock):
    """
    Register WebSocket routes for demo functionality

    Args:
        sock: Flask-Sock instance
    """

    @sock.route('/demo/suggestions-stream/<session_id>')
    def suggestions_stream_handler(ws, session_id):
        """
        WebSocket endpoint for streaming suggestions to frontend
        The frontend connects here to receive real-time suggestions
        """
        try:
            logger.info(f"✅ Suggestions WebSocket connected for session {session_id}")

            # Store connection
            _suggestion_connections[session_id] = ws

            # Send connection confirmation
            ws.send(json.dumps({
                'type': 'connected',
                'session_id': session_id,
                'message': 'Connected to suggestions stream'
            }))

            # Keep connection alive and handle messages
            while True:
                message = ws.receive()
                if message is None:
                    break

                # Handle ping/pong for keep-alive
                try:
                    data = json.loads(message)
                    if data.get('type') == 'ping':
                        ws.send(json.dumps({'type': 'pong'}))
                    elif data.get('type') == 'get_suggestions':
                        # Client requesting suggestions
                        from app.services.realtime_transcription_service import get_transcription_service
                        transcription_service = get_transcription_service()

                        result = run_async(transcription_service.get_session_suggestions(
                            session_id=session_id,
                            limit=10
                        ))

                        ws.send(json.dumps({
                            'type': 'suggestions',
                            'suggestions': result.get('suggestions', [])
                        }))
                except json.JSONDecodeError:
                    pass

        except Exception as e:
            logger.error(f"❌ Suggestions WebSocket error for session {session_id}: {e}")
        finally:
            # Clean up
            if session_id in _suggestion_connections:
                del _suggestion_connections[session_id]
            logger.info(f"Suggestions WebSocket closed for session {session_id}")


def broadcast_suggestion(session_id: str, suggestion: dict):
    """
    Broadcast a suggestion to connected WebSocket client

    Args:
        session_id: Session identifier
        suggestion: Suggestion data to send
    """
    if session_id in _suggestion_connections:
        try:
            ws = _suggestion_connections[session_id]
            ws.send(json.dumps({
                'type': 'suggestion',
                **suggestion
            }))
            logger.info(f"📤 Broadcasted suggestion to session {session_id}")
        except Exception as e:
            logger.error(f"Error broadcasting suggestion to {session_id}: {e}")
            # Remove dead connection
            del _suggestion_connections[session_id]
