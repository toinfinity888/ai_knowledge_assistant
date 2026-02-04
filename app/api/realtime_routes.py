"""
Real-time API Routes for ACD/CRM Integration
Provides WebSocket and REST endpoints for call transcription and suggestions
"""
from flask import Blueprint, request, jsonify, Response, g
from flask_sock import Sock
import json
import asyncio
from typing import Dict, Any
import logging

from app.services.call_session_manager import get_call_session_manager
from app.services.realtime_transcription_service import get_transcription_service
from app.middleware.auth_middleware import require_auth, optional_auth
from app.middleware.tenant_context import get_current_tenant
from app.middleware.websocket_auth import websocket_auth_required, WebSocketAuthenticator


logger = logging.getLogger(__name__)

# Create blueprint
realtime_bp = Blueprint('realtime', __name__, url_prefix='/api/realtime')

# WebSocket support
sock = Sock()

# Store active WebSocket connections per session
_active_connections: Dict[str, Any] = {}


# ==================== REST API Endpoints ====================

@realtime_bp.route('/call/start', methods=['POST'])
@require_auth
async def start_call():
    """
    Start a new call session

    POST /api/realtime/call/start
    Body:
    {
        "call_id": "acd-call-12345",
        "agent_id": "agent-42",
        "agent_name": "John Smith",
        "customer_id": "cust-999",
        "customer_phone": "+1234567890",
        "customer_name": "Jane Doe",
        "acd_metadata": {...},
        "crm_metadata": {...}
    }

    Returns:
    {
        "status": "success",
        "session_id": "uuid",
        "call_id": "acd-call-12345",
        "company_id": 123
    }

    Requires authentication. Company ID and agent_user_id are automatically
    injected from the authenticated user's context.
    """
    try:
        tenant = get_current_tenant()
        data = request.get_json()

        if not data.get('call_id'):
            return jsonify({
                "status": "error",
                "error": "Missing required field: call_id"
            }), 400

        transcription_service = get_transcription_service()

        if not transcription_service:
            return jsonify({
                "status": "error",
                "error": "Transcription service not initialized"
            }), 500

        # Inject company_id and agent_user_id from authenticated user
        result = await transcription_service.handle_call_start(
            call_id=data['call_id'],
            agent_id=data.get('agent_id', str(tenant.user_id)),
            company_id=tenant.company_id,
            agent_user_id=tenant.user_id,
            agent_name=data.get('agent_name'),
            customer_id=data.get('customer_id'),
            customer_phone=data.get('customer_phone'),
            customer_name=data.get('customer_name'),
            acd_metadata=data.get('acd_metadata'),
            crm_metadata=data.get('crm_metadata'),
        )

        if result['status'] == 'success':
            return jsonify(result), 200
        else:
            return jsonify(result), 500

    except Exception as e:
        logger.error(f"Error starting call: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@realtime_bp.route('/call/end', methods=['POST'])
@require_auth
async def end_call():
    """
    End a call session

    POST /api/realtime/call/end
    Body:
    {
        "session_id": "uuid",
        "status": "completed"  // or "transferred", "dropped"
    }

    Returns:
    {
        "status": "success",
        "session_id": "uuid"
    }

    Requires authentication. Only sessions belonging to the user's company
    can be ended.
    """
    try:
        tenant = get_current_tenant()
        data = request.get_json()

        if not data.get('session_id'):
            return jsonify({
                "status": "error",
                "error": "Missing required field: session_id"
            }), 400

        session_id = data['session_id']

        # Verify session ownership
        session_manager = get_call_session_manager()
        if not session_manager.verify_session_ownership(session_id, tenant.company_id):
            return jsonify({
                "status": "error",
                "error": "Session not found or access denied"
            }), 404

        transcription_service = get_transcription_service()

        result = await transcription_service.handle_call_end(
            session_id=session_id,
            status=data.get('status', 'completed'),
        )

        # Close WebSocket connection if exists
        if session_id in _active_connections:
            try:
                ws = _active_connections[session_id]
                ws.close()
                del _active_connections[session_id]
            except:
                pass

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error ending call: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@realtime_bp.route('/transcription', methods=['POST'])
@require_auth
async def receive_transcription():
    """
    Receive transcription segment from ACD

    POST /api/realtime/transcription
    Body:
    {
        "session_id": "uuid",
        "speaker": "customer",  // or "agent"
        "text": "Hello, I have a problem with...",
        "start_time": 10.5,  // seconds from call start
        "end_time": 15.2,
        "confidence": 0.95,
        "metadata": {...}
    }

    Returns:
    {
        "status": "processed",
        "segment_id": 123,
        "suggestions_count": 2,
        "processing_time_ms": 450
    }

    Requires authentication. Only transcriptions for sessions belonging
    to the user's company can be submitted.
    """
    try:
        tenant = get_current_tenant()
        data = request.get_json()

        required = ['session_id', 'speaker', 'text', 'start_time', 'end_time']
        if not all(field in data for field in required):
            return jsonify({
                "status": "error",
                "error": f"Missing required fields: {required}"
            }), 400

        session_id = data['session_id']

        # Verify session ownership
        session_manager = get_call_session_manager()
        if not session_manager.verify_session_ownership(session_id, tenant.company_id):
            return jsonify({
                "status": "error",
                "error": "Session not found or access denied"
            }), 404

        transcription_service = get_transcription_service()

        result = await transcription_service.process_transcription_segment(
            session_id=session_id,
            speaker=data['speaker'],
            text=data['text'],
            start_time=data['start_time'],
            end_time=data['end_time'],
            confidence=data.get('confidence'),
            metadata=data.get('metadata'),
            company_id=tenant.company_id,  # Pass company_id for KB filtering
        )

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error processing transcription: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@realtime_bp.route('/analyze', methods=['POST'])
@require_auth
def manual_analyze():
    """
    Manual analyze & search endpoint (Intelligence Gatekeeper).
    Called when agent clicks "Analyze & Search" button.

    POST /api/realtime/analyze
    Body:
    {
        "session_id": "uuid",
        "force_search": false,
        "language": "en"
    }
    """
    from app.init_realtime_system import get_gatekeeper_orchestrator

    data = request.get_json()
    session_id = data.get('session_id')
    force_search = data.get('force_search', False)
    language = data.get('language', 'en')

    if not session_id:
        return jsonify({"status": "error", "error": "Missing session_id"}), 400

    gatekeeper = get_gatekeeper_orchestrator()
    if gatekeeper is None:
        return jsonify({
            "status": "error",
            "error": "Intelligence Gatekeeper not initialized. Check GROQ_API_KEY.",
        }), 503

    try:
        tenant = get_current_tenant()

        # Verify session ownership
        session_manager = get_call_session_manager()
        if not session_manager.verify_session_ownership(session_id, tenant.company_id):
            return jsonify({
                "status": "error",
                "error": "Session not found or access denied"
            }), 404

        result = gatekeeper.analyze_and_search(
            session_id=session_id,
            company_id=tenant.company_id,
            language=language,
            force_search=force_search,
        )

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error in manual analyze: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@realtime_bp.route('/suggestions/<session_id>', methods=['GET'])
@require_auth
async def get_suggestions(session_id: str):
    """
    Get all suggestions for a session

    GET /api/realtime/suggestions/<session_id>?limit=10

    Returns:
    {
        "status": "success",
        "suggestions": [...]
    }

    Requires authentication. Only suggestions for sessions belonging
    to the user's company can be retrieved.
    """
    try:
        tenant = get_current_tenant()
        limit = request.args.get('limit', 10, type=int)

        # Verify session ownership
        session_manager = get_call_session_manager()
        if not session_manager.verify_session_ownership(session_id, tenant.company_id):
            return jsonify({
                "status": "error",
                "error": "Session not found or access denied"
            }), 404

        transcription_service = get_transcription_service()

        result = await transcription_service.get_session_suggestions(
            session_id=session_id,
            limit=limit,
        )

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error getting suggestions: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@realtime_bp.route('/suggestions/<int:suggestion_id>/feedback', methods=['POST'])
@require_auth
def record_feedback(suggestion_id: int):
    """
    Record agent feedback on a suggestion

    POST /api/realtime/suggestions/<suggestion_id>/feedback
    Body:
    {
        "feedback": "helpful"  // or "not_helpful", "irrelevant"
    }

    Returns:
    {
        "status": "success"
    }

    Requires authentication.
    """
    try:
        data = request.get_json()
        feedback = data.get('feedback')

        if not feedback:
            return jsonify({
                "status": "error",
                "error": "Missing feedback"
            }), 400

        session_manager = get_call_session_manager()
        session_manager.record_suggestion_feedback(suggestion_id, feedback)

        return jsonify({"status": "success"}), 200

    except Exception as e:
        logger.error(f"Error recording feedback: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


# ==================== Server-Sent Events (SSE) ====================

@realtime_bp.route('/stream/<session_id>')
@require_auth
def suggestion_stream(session_id: str):
    """
    Server-Sent Events stream for real-time suggestions

    GET /api/realtime/stream/<session_id>

    Streams:
    data: {"type": "suggestion", "data": {...}}
    data: {"type": "question", "data": {...}}

    Requires authentication. Only streams for sessions belonging
    to the user's company are allowed.
    """
    tenant = get_current_tenant()

    # Verify session ownership
    session_manager = get_call_session_manager()
    if not session_manager.verify_session_ownership(session_id, tenant.company_id):
        return jsonify({
            "status": "error",
            "error": "Session not found or access denied"
        }), 404

    def generate():
        """SSE generator function"""
        # Send initial connection message
        yield f"data: {json.dumps({'type': 'connected', 'session_id': session_id, 'company_id': tenant.company_id})}\n\n"

        # TODO: Implement actual streaming logic
        # For now, this is a placeholder
        # You would typically:
        # 1. Register this generator with the transcription service
        # 2. Queue messages when suggestions are ready
        # 3. Yield them here

        import time
        while True:
            # Heartbeat every 30 seconds
            time.sleep(30)
            yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': time.time()})}\n\n"

    return Response(generate(), mimetype='text/event-stream')


# ==================== WebSocket Endpoint ====================

def setup_websocket(sock_instance: Sock):
    """Setup WebSocket routes"""

    @sock_instance.route('/api/realtime/ws/<session_id>')
    def websocket_handler(ws, session_id: str):
        """
        WebSocket endpoint for real-time bidirectional communication

        WS /api/realtime/ws/<session_id>?token=<jwt_token>

        Authentication:
        - Pass JWT token as query parameter: ?token=<jwt_token>
        - Or authenticate via first message: {"type": "auth", "token": "<jwt_token>"}

        Client -> Server:
        {
            "type": "feedback",
            "suggestion_id": 123,
            "feedback": "helpful"
        }

        Server -> Client:
        {
            "type": "suggestions",
            "data": {
                "suggestions": [...],
                "clarifying_questions": [...]
            }
        }
        """
        from flask import request as flask_request
        from app.middleware.websocket_auth import authenticate_websocket

        # Try to authenticate from query parameter first
        token = flask_request.args.get('token')
        tenant_context = authenticate_websocket(token) if token else None

        # If no token in query, try message-based auth
        if not tenant_context:
            authenticator = WebSocketAuthenticator(ws)
            tenant_context = authenticator.authenticate_from_message()
            if not tenant_context:
                return  # Connection closed by authenticator

        # Verify session ownership
        session_manager = get_call_session_manager()
        if not session_manager.verify_session_ownership(session_id, tenant_context.company_id):
            ws.send(json.dumps({
                "type": "error",
                "error": "Session not found or access denied"
            }))
            ws.close()
            logger.warning(f"WebSocket access denied for session {session_id}")
            return

        logger.info(f"WebSocket connected for session: {session_id} (company: {tenant_context.company_id})")

        # Store connection
        _active_connections[session_id] = ws

        try:
            # Send welcome message
            import time
            ws.send(json.dumps({
                "type": "connected",
                "session_id": session_id,
                "company_id": tenant_context.company_id,
                "timestamp": time.time()
            }))

            # Listen for messages from client
            while True:
                message = ws.receive()

                if message is None:
                    break

                try:
                    data = json.loads(message)
                    message_type = data.get('type')

                    if message_type == 'feedback':
                        # Handle feedback
                        suggestion_id = data.get('suggestion_id')
                        feedback = data.get('feedback')

                        session_manager.record_suggestion_feedback(suggestion_id, feedback)

                        ws.send(json.dumps({
                            "type": "feedback_received",
                            "suggestion_id": suggestion_id
                        }))

                    elif message_type == 'ping':
                        # Respond to ping
                        ws.send(json.dumps({"type": "pong"}))

                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON from client: {message}")
                    ws.send(json.dumps({
                        "type": "error",
                        "error": "Invalid JSON"
                    }))

        except Exception as e:
            logger.error(f"WebSocket error for session {session_id}: {e}")

        finally:
            logger.info(f"WebSocket disconnected for session: {session_id}")
            if session_id in _active_connections:
                del _active_connections[session_id]


async def broadcast_to_session(session_id: str, message: Dict[str, Any]):
    """
    Broadcast message to WebSocket client for a specific session

    This function should be used as the callback for RealtimeTranscriptionService
    """
    if session_id in _active_connections:
        try:
            ws = _active_connections[session_id]
            ws.send(json.dumps(message))
            logger.info(f"Broadcasted message to session {session_id}")
        except Exception as e:
            logger.error(f"Error broadcasting to session {session_id}: {e}")
            # Remove dead connection
            del _active_connections[session_id]


# Export broadcast function for use in service initialization
__all__ = ['realtime_bp', 'setup_websocket', 'broadcast_to_session']
