"""
Twilio Routes for Two-Way Calling
Handles Twilio webhooks, TwiML generation, and WebSocket media streaming
"""
import asyncio
import logging
from flask import Blueprint, request, jsonify
from twilio.twiml.voice_response import VoiceResponse, Dial
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
import json
from typing import Dict, Set

from app.services.twilio_audio_service import get_twilio_service
from app.services.enhanced_transcription_service import get_enhanced_transcription_service
from app.config.twilio_config import get_twilio_settings

logger = logging.getLogger(__name__)

# Store active WebSocket connections for broadcasting call status
# Key: session_id, Value: set of WebSocket connections
_active_status_connections: Dict[str, Set] = {}

# Store mapping between call_sid and session_id
_call_sid_to_session: Dict[str, str] = {}

# Store pending messages for each session
_pending_messages: Dict[str, list] = {}

# Create blueprint
twilio_bp = Blueprint('twilio', __name__, url_prefix='/twilio')


def run_async(coro):
    """Helper to run async functions in sync Flask routes"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@twilio_bp.route('/token', methods=['GET', 'POST'])
def generate_token():
    """
    Generate Twilio Access Token for browser-based calling

    Returns a token that allows the browser to:
    - Make outgoing calls through Twilio
    - Receive incoming calls
    - Access audio devices
    """
    try:
        settings = get_twilio_settings()

        # Get identity from request or generate one
        data = request.get_json() if request.is_json else {}
        identity = data.get('identity', f'support-agent-{request.remote_addr}')

        # Create access token
        # Use API Keys if available, otherwise fallback to Account SID + Auth Token
        signing_key_sid = settings.api_key_sid if settings.api_key_sid else settings.account_sid
        secret = settings.api_key_secret if settings.api_key_secret else settings.auth_token

        logger.info(f"Generating token with signing key: {signing_key_sid[:10]}...")

        token = AccessToken(
            settings.account_sid,
            signing_key_sid,
            secret,
            identity=identity,
            ttl=3600  # Token valid for 1 hour
        )

        # Create Voice grant
        voice_grant = VoiceGrant(
            outgoing_application_sid=settings.twiml_app_sid if settings.twiml_app_sid else None,
            incoming_allow=True  # Allow incoming calls
        )

        # Add grant to token
        token.add_grant(voice_grant)

        # Generate JWT token
        jwt_token = token.to_jwt()

        logger.info(f"Generated access token for identity: {identity}")

        return jsonify({
            'token': jwt_token,
            'identity': identity
        }), 200

    except Exception as e:
        logger.error(f"Error generating token: {e}")
        return jsonify({'error': str(e)}), 500


@twilio_bp.route('/incoming', methods=['POST'])
def incoming_call():
    """
    TwiML webhook for INCOMING calls to your Twilio number
    Routes incoming calls to browser (Twilio Device)
    """
    try:
        from_number = request.form.get('From', request.values.get('From'))
        to_number = request.form.get('To', request.values.get('To'))
        call_sid = request.form.get('CallSid')

        logger.info(f"Incoming call from {from_number} to {to_number} (CallSid: {call_sid})")
        logger.info(f"Attempting to dial to Twilio Device client 'support-agent'")

        # Create TwiML response
        response = VoiceResponse()

        # Greet the caller
        response.say(
            "Bonjour, veuillez patienter pendant que nous vous mettons en relation avec un agent.",
            language='fr-FR',
            voice='alice'
        )

        # Dial to the browser (Twilio Device)
        # This will ring all connected support agents
        dial = Dial(
            record='record-from-answer',  # Record for transcription
            recording_status_callback='/twilio/recording-status',
            timeout=30,  # Ring for 30 seconds
            action='/twilio/incoming-completed'  # Called after dial completes
        )

        # Ring all logged-in support agents
        # IMPORTANT: The identity in the token must match this client name
        dial.client('support-agent')

        response.append(dial)

        logger.info(f"TwiML generated: {str(response)}")

        # If no one answers
        response.say(
            "Désolé, aucun agent n'est disponible pour le moment. Veuillez rappeler plus tard.",
            language='fr-FR',
            voice='alice'
        )

        return str(response), 200, {'Content-Type': 'text/xml'}

    except Exception as e:
        logger.error(f"Error in incoming call webhook: {e}")
        response = VoiceResponse()
        response.say("Désolé, une erreur s'est produite.", language='fr-FR', voice='alice')
        return str(response), 200, {'Content-Type': 'text/xml'}


@twilio_bp.route('/incoming-completed', methods=['POST'])
def incoming_completed():
    """
    Called after incoming call dial attempt completes
    """
    dial_call_status = request.form.get('DialCallStatus')
    call_sid = request.form.get('CallSid')

    logger.info(f"Incoming call {call_sid} completed with status: {dial_call_status}")

    response = VoiceResponse()

    if dial_call_status == 'no-answer':
        response.say("Aucun agent n'a répondu. Au revoir.", language='fr-FR', voice='alice')
    elif dial_call_status == 'busy':
        response.say("Tous nos agents sont occupés. Veuillez rappeler.", language='fr-FR', voice='alice')
    elif dial_call_status == 'failed':
        response.say("L'appel a échoué. Veuillez réessayer.", language='fr-FR', voice='alice')

    return str(response), 200, {'Content-Type': 'text/xml'}


@twilio_bp.route('/voice', methods=['POST'])
def voice_webhook():
    """
    TwiML webhook for OUTGOING calls from browser
    Called when browser makes an outgoing call via Twilio Device
    """
    try:
        # Get the phone number to call from the request
        to_number = request.form.get('To', request.values.get('To'))
        from_number = request.form.get('From', request.values.get('From'))

        logger.info(f"Browser calling {to_number} from {from_number}")

        settings = get_twilio_settings()

        # Create TwiML response
        response = VoiceResponse()

        # Dial the number
        dial = Dial(
            caller_id=settings.phone_number,  # Use your Twilio number as caller ID
            record='record-from-answer',  # Record for transcription
            recording_status_callback='/twilio/recording-status'
        )
        dial.number(to_number)

        response.append(dial)

        return str(response), 200, {'Content-Type': 'text/xml'}

    except Exception as e:
        logger.error(f"Error in voice webhook: {e}")
        response = VoiceResponse()
        response.say("Sorry, there was an error connecting your call.")
        return str(response), 200, {'Content-Type': 'text/xml'}


@twilio_bp.route('/recording-status', methods=['POST'])
def recording_status():
    """Handle recording status callbacks"""
    recording_url = request.form.get('RecordingUrl')
    recording_sid = request.form.get('RecordingSid')
    call_sid = request.form.get('CallSid')

    logger.info(f"Recording available: {recording_sid} for call {call_sid} at {recording_url}")

    # Here you can download and process the recording for transcription
    # For now, just log it

    return '', 204


@twilio_bp.route('/initiate-call', methods=['POST'])
def initiate_call():
    """
    Initiate an outbound call to a technician

    Expected JSON payload:
    {
        "phone_number": "+33612345678",
        "technician_id": "tech_123",
        "technician_name": "Jean Dupont",
        "session_id": "session_abc123",
        "worksite_info": {...}
    }
    """
    try:
        data = request.get_json()

        phone_number = data.get('phone_number')
        technician_id = data.get('technician_id')
        technician_name = data.get('technician_name', 'Technician')
        session_id = data.get('session_id')

        if not phone_number or not session_id:
            return jsonify({
                'error': 'Missing required fields: phone_number, session_id'
            }), 400

        # Get base URL for webhooks
        base_url = request.url_root.rstrip('/')

        # Initialize transcription session
        transcription_service = get_enhanced_transcription_service()
        transcription_service.initialize_session(
            session_id=session_id,
            technician_id=technician_id or 'unknown',
            technician_name=technician_name,
            technician_phone=phone_number
        )

        # Initiate call via Twilio
        twilio_service = get_twilio_service()
        call_result = twilio_service.initiate_call(
            to_number=phone_number,
            session_id=session_id,
            websocket_url=base_url
        )

        # Store call_sid to session_id mapping for status callbacks
        _call_sid_to_session[call_result['call_sid']] = session_id

        logger.info(f"Call initiated: {call_result['call_sid']} for session {session_id}")

        return jsonify({
            'success': True,
            'call_sid': call_result['call_sid'],
            'session_id': session_id,
            'status': 'initiated'
        }), 200

    except Exception as e:
        logger.error(f"Error initiating call: {e}")
        return jsonify({'error': str(e)}), 500


@twilio_bp.route('/end-call', methods=['POST'])
def end_call():
    """
    End an active call

    Expected JSON payload:
    {
        "call_sid": "CAxxxx",
        "session_id": "session_abc123"
    }
    """
    try:
        data = request.get_json()

        call_sid = data.get('call_sid')
        session_id = data.get('session_id')

        if not call_sid:
            return jsonify({'error': 'Missing call_sid'}), 400

        # End call via Twilio
        twilio_service = get_twilio_service()
        result = twilio_service.end_call(call_sid)

        # End transcription session
        if session_id:
            transcription_service = get_enhanced_transcription_service()
            stats = transcription_service.end_session(session_id)

            result['session_stats'] = stats

        logger.info(f"Call ended: {call_sid}")

        return jsonify({
            'success': True,
            **result
        }), 200

    except Exception as e:
        logger.error(f"Error ending call: {e}")
        return jsonify({'error': str(e)}), 500


@twilio_bp.route('/status', methods=['POST'])
def call_status_callback():
    """
    Twilio callback for call status updates

    Twilio sends: CallSid, CallStatus, Direction, etc.
    """
    try:
        call_sid = request.form.get('CallSid')
        call_status = request.form.get('CallStatus')
        direction = request.form.get('Direction')

        logger.info(
            f"Call status update: {call_sid} - {call_status} ({direction})"
        )

        # Get session_id from call_sid
        session_id = _call_sid_to_session.get(call_sid)

        # If call is completed or failed, notify frontend
        if call_status in ['completed', 'failed', 'busy', 'no-answer', 'canceled'] and session_id:
            # Broadcast to all connections for this session
            _broadcast_status_to_session(session_id, {
                'event': 'call_ended',
                'call_sid': call_sid,
                'status': call_status,
                'reason': 'customer_disconnected' if call_status == 'completed' else call_status
            })

            # Clean up mapping
            if call_sid in _call_sid_to_session:
                del _call_sid_to_session[call_sid]

        return '', 204  # No content response

    except Exception as e:
        logger.error(f"Error in status callback: {e}")
        return '', 500


def _broadcast_status_to_session(session_id: str, message: dict):
    """Queue status message for delivery to WebSocket connections"""
    # Store the message for the session
    if session_id not in _pending_messages:
        _pending_messages[session_id] = []

    _pending_messages[session_id].append(message)
    logger.info(f"Queued status message for session {session_id}: {message}")


@twilio_bp.route('/call-status/<call_sid>', methods=['GET'])
def get_call_status(call_sid: str):
    """
    Get current status of a call

    Args:
        call_sid: Twilio call SID
    """
    try:
        twilio_service = get_twilio_service()
        status = twilio_service.get_call_status(call_sid)

        return jsonify(status), 200

    except Exception as e:
        logger.error(f"Error getting call status: {e}")
        return jsonify({'error': str(e)}), 500


# WebSocket route for media streaming
# This needs to be registered with Flask-Sock or similar WebSocket library
def register_websocket_routes(sock):
    """
    Register WebSocket routes for Twilio media streaming

    Args:
        sock: Flask-Sock instance
    """

    @sock.route('/twilio/media-stream')
    async def media_stream_handler(ws):
        """
        Handle Twilio media stream WebSocket connection

        Twilio sends JSON messages with audio data
        We process, transcribe, and can send audio back
        """
        session_id = None

        try:
            logger.info("Twilio media stream WebSocket connected")

            async for message in ws:
                try:
                    data = json.loads(message)
                    event_type = data.get('event')

                    if event_type == 'start':
                        # Extract session_id from custom parameters
                        stream_sid = data['start']['streamSid']
                        custom_params = data['start'].get('customParameters', {})
                        session_id = custom_params.get('session_id', stream_sid)

                        logger.info(f"Media stream started: {stream_sid} for session {session_id}")

                        # Store WebSocket connection in Twilio service
                        twilio_service = get_twilio_service()
                        await twilio_service.handle_media_stream(ws, session_id)

                    elif event_type == 'media':
                        # Audio data received
                        # This is handled inside twilio_service.handle_media_stream
                        pass

                    elif event_type == 'stop':
                        logger.info(f"Media stream stopped for session {session_id}")
                        break

                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON from Twilio: {message}")
                except Exception as e:
                    logger.error(f"Error processing media message: {e}")

        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            logger.info(f"Media stream closed for session {session_id}")

    @sock.route('/twilio/call-status/<session_id>')
    async def call_status_handler(ws, session_id):
        """
        WebSocket endpoint for real-time call status updates
        Frontend connects here to receive notifications when call ends
        """
        import asyncio

        try:
            logger.info(f"Call status WebSocket connected for session {session_id}")

            # Register this connection
            if session_id not in _active_status_connections:
                _active_status_connections[session_id] = set()
            _active_status_connections[session_id].add(ws)

            # Send initial connection confirmation
            await ws.send(json.dumps({
                'event': 'connected',
                'session_id': session_id
            }))

            # Create tasks for sending pending messages and receiving client messages
            async def send_pending_messages():
                """Background task to send pending messages"""
                while True:
                    try:
                        # Check for pending messages
                        if session_id in _pending_messages and _pending_messages[session_id]:
                            messages = _pending_messages[session_id].copy()
                            _pending_messages[session_id].clear()

                            for msg in messages:
                                await ws.send(json.dumps(msg))
                                logger.info(f"Sent status message to session {session_id}")

                        await asyncio.sleep(0.5)  # Check every 500ms
                    except Exception as e:
                        logger.error(f"Error sending pending message: {e}")
                        break

            async def receive_client_messages():
                """Handle incoming client messages"""
                async for message in ws:
                    try:
                        data = json.loads(message)
                        # Handle any client messages if needed (e.g., ping/pong)
                        if data.get('type') == 'ping':
                            await ws.send(json.dumps({'type': 'pong'}))
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON from client: {message}")
                    except Exception as e:
                        logger.error(f"Error processing client message: {e}")

            # Run both tasks concurrently
            await asyncio.gather(
                send_pending_messages(),
                receive_client_messages(),
                return_exceptions=True
            )

        except Exception as e:
            logger.error(f"WebSocket error in call status handler: {e}")
        finally:
            # Clean up connection
            if session_id in _active_status_connections:
                _active_status_connections[session_id].discard(ws)
                if not _active_status_connections[session_id]:
                    del _active_status_connections[session_id]

            # Clean up pending messages
            if session_id in _pending_messages:
                del _pending_messages[session_id]

            logger.info(f"Call status WebSocket closed for session {session_id}")


# Helper endpoint to generate TwiML for testing
@twilio_bp.route('/test-twiml', methods=['GET', 'POST'])
def test_twiml():
    """
    Generate test TwiML for manual testing

    Returns:
        TwiML XML response
    """
    response = VoiceResponse()

    response.say(
        "Bonjour, ceci est un test de l'assistant de support technique.",
        language='fr-FR',
        voice='alice'
    )

    response.pause(length=1)

    response.say(
        "Veuillez décrire votre problème après le bip.",
        language='fr-FR',
        voice='alice'
    )

    # Record for testing
    response.record(
        max_length=30,
        transcribe=False,
        action='/twilio/recording-complete'
    )

    return str(response), 200, {'Content-Type': 'text/xml'}


@twilio_bp.route('/recording-complete', methods=['POST'])
def recording_complete():
    """
    Handle recording completion callback

    Used for testing without streaming
    """
    recording_url = request.form.get('RecordingUrl')
    recording_sid = request.form.get('RecordingSid')

    logger.info(f"Recording complete: {recording_sid} - {recording_url}")

    response = VoiceResponse()
    response.say(
        "Merci, votre message a été enregistré.",
        language='fr-FR',
        voice='alice'
    )
    response.hangup()

    return str(response), 200, {'Content-Type': 'text/xml'}
