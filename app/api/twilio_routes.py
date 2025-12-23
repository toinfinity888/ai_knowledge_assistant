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
from datetime import datetime

from app.services.twilio_audio_service import get_twilio_service
from app.services.enhanced_transcription_service import get_enhanced_transcription_service
from app.config.twilio_config import get_twilio_settings

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------------------------
# Stores all active WebSocket connections per session.
# Key: session_id (our internal session identifier)
# Value: set of WebSocket connections associated with this session.
#
# Used to broadcast statuses, transcriptions, and UI updates to all clients
# that opened a WebSocket within the same session.
# For example: operator dashboard, dev tools, admin UI, etc.
# ------------------------------------------------------------------------------------
_active_status_connections: Dict[str, Set] = {}


# ------------------------------------------------------------------------------------
# Maps Twilio call SID → our internal session_id.
# Key: call_sid (Twilio's unique identifier for the call)
# Value: session_id (our own ID used by the UI, WebSockets, and internal logic)
#
# Twilio only sends the call_sid, so we need to map it to our session_id
# in order to understand which UI and which WebSockets should receive updates.
# ------------------------------------------------------------------------------------
_call_sid_to_session: Dict[str, str] = {}


# ------------------------------------------------------------------------------------
# Stores messages that should be delivered later if the UI is not yet connected.
# Key: session_id
# Value: list of pending messages (transcriptions, agent replies, statuses)
#
# If the frontend WebSocket is not connected yet or has been reloaded,
# we temporarily store all events and send them later when the client connects.
# This ensures that no data is lost.
# ------------------------------------------------------------------------------------
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


@twilio_bp.route('/voice', methods=['POST'])
def voice_webhook():
    """
    TwiML webhook for OUTGOING calls from browser
    Called when browser makes an outgoing call via Twilio Device

    This endpoint is REQUIRED for browser-based calling to work.
    The TwiML App in Twilio Console calls this webhook to get instructions.
    """
    try:
        # Get the phone number to call from the request
        to_number = request.form.get('To', request.values.get('To'))
        from_number = request.form.get('From', request.values.get('From'))

        # Get session_id passed from frontend (CRITICAL for WebSocket matching)
        session_id = request.form.get('session_id', request.values.get('session_id'))

        logger.info(f"📞 Browser calling {to_number} from {from_number}")
        logger.info(f"📋 Session ID from frontend: {session_id}")

        settings = get_twilio_settings()

        # Create TwiML response
        response = VoiceResponse()

        # Start media stream for real-time transcription
        stream_url = settings.websocket_url
        logger.info(f"🔌 Starting media stream to {stream_url}")

        start = response.start()
        stream = start.stream(url=stream_url, track='both_tracks')

        # Pass session_id as custom parameter to the media stream WebSocket
        # This allows the WebSocket handler to use the same session_id as the frontend
        if session_id:
            stream.parameter(name='session_id', value=session_id)
            logger.info(f"📋 Passing session_id={session_id} to media stream")

        # Dial the number
        dial = Dial(caller_id=settings.phone_number)
        dial.number(to_number)
        response.append(dial)

        logger.info(f"✅ Generated TwiML for call to {to_number}")
        return str(response), 200, {'Content-Type': 'text/xml'}

    except Exception as e:
        logger.error(f"❌ Error in voice webhook: {e}", exc_info=True)
        response = VoiceResponse()
        response.say("Sorry, there was an error connecting your call.")
        return str(response), 200, {'Content-Type': 'text/xml'}


@twilio_bp.route('/start-session', methods=['POST'])
def start_session():
    """
    Initialize a session for real-time transcription.
    Must be called BEFORE the call starts to ensure session exists in database.

    Expected JSON payload:
    {
        "session_id": "session-123456",
        "technician_name": "Jean Dupont",
        "agent_name": "Support Agent"
    }
    """
    from app.services.realtime_transcription_service import get_transcription_service

    try:
        data = request.get_json()

        session_id = data.get('session_id')
        if not session_id:
            return jsonify({'error': 'Missing session_id'}), 400

        technician_name = data.get('technician_name', 'Technicien')
        agent_name = data.get('agent_name', 'Agent Support')

        transcription_service = get_transcription_service()

        # Initialize session in database
        result = run_async(transcription_service.handle_call_start(
            call_id=session_id,
            agent_id="agent-1",
            agent_name=agent_name,
            customer_id="technician-1",
            customer_name=technician_name,
            acd_metadata={"type": "twilio", "source": "browser"},
            crm_metadata={"twilio": True},
        ))

        logger.info(f"✅ Session initialized: {session_id}")

        return jsonify({
            'success': True,
            'session_id': session_id,
            **result
        }), 200

    except Exception as e:
        logger.error(f"❌ Error starting session: {e}", exc_info=True)
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
    def media_stream_handler(ws):
        """
        Handle Twilio media stream WebSocket connection

        Twilio sends JSON messages with audio data
        We process, transcribe, and can send audio back
        """
        session_id = None
        stream_sid = None
        audio_buffer = []

        # Get services
        twilio_service = get_twilio_service()

        try:
            logger.info("Twilio media stream WebSocket connected")

            while True: # Main loop to receive messages from Twilio WebSocket in real-time 
                message = ws.receive() 
                if message is None:
                    logger.info("WebSocket receive returned None, closing connection")
                    break

                logger.debug(f"Received raw message: {message}")

                try:
                    data = json.loads(message)
                    event_type = data.get('event')

                    logger.info(f"Event type: {event_type}")

                    if event_type == 'start':
                        # Extract session_id from custom parameters
                        stream_sid = data['start']['streamSid']
                        custom_params = data['start'].get('customParameters', {})
                        session_id = custom_params.get('session_id', stream_sid)

                        # Log detailed start info including track configuration
                        logger.info(f"📞 Media stream started: stream_sid={stream_sid}, session_id={session_id}")
                        logger.info(f"📞 Start event tracks: {data['start'].get('tracks', 'unknown')}")
                        logger.info(f"📞 Custom params: {custom_params}")

                        # DEBUG: Log ALL known session IDs in active_streams
                        all_sessions = list(twilio_service.active_streams.keys())
                        logger.info(f"📞 DEBUG: All known sessions in active_streams: {all_sessions}")

                        # Initialize stream tracking which holds WebSocket and metadata for this session
                        # IMPORTANT: Merge with existing data to preserve transcription_ws from earlier connection
                        existing_stream = twilio_service.active_streams.get(session_id, {})
                        existing_technician = existing_stream.get('technician', {})
                        existing_agent = existing_stream.get('agent', {})

                        # Preserve any existing WebSocket connections (e.g., transcription_ws)
                        transcription_ws = existing_technician.get('transcription_ws')
                        agent_ws = existing_agent.get('websocket')

                        logger.info(f"📞 Existing WebSockets before init: tech_ws={transcription_ws is not None}, agent_ws={agent_ws is not None}")

                        twilio_service.active_streams[session_id] = {
                            'websocket': ws,
                            'stream_sid': stream_sid,
                            'started_at': datetime.utcnow(),
                            'audio_buffer': [],
                            'technician': {
                                'started_at': datetime.utcnow(),
                                'audio_buffer': [],
                                'wav_file': twilio_service._create_wav_file(session_id, speaker='technician'),
                                'transcription_ws': transcription_ws  # Preserve existing WS connection
                            },
                            # Preserve agent stream if it exists
                            'agent': {
                                **existing_agent,
                                'websocket': agent_ws  # Ensure agent websocket is preserved
                            } if existing_agent else {}
                        }

                        # Remove empty agent dict if no agent stream exists
                        if not twilio_service.active_streams[session_id].get('agent'):
                            del twilio_service.active_streams[session_id]['agent']

                        logger.info(f"📞 Stream initialized. tech_ws preserved: {transcription_ws is not None}, agent_ws preserved: {agent_ws is not None}")

                    elif event_type == 'media':
                        # Audio data received - process it synchronously
                        if session_id:
                            # IMPORTANT: Filter by track to avoid mixing audio sources
                            # With track='both_tracks', Twilio sends:
                            #   - 'inbound' track: audio FROM the remote party (technician on phone)
                            #   - 'outbound' track: audio TO the remote party (could include agent's voice)
                            # We only want to transcribe the INBOUND track (technician's voice)
                            track = data['media'].get('track', 'unknown')

                            # Log ALL tracks received for debugging
                            audio_buffer.append(track)  # Store track names
                            if len(audio_buffer) <= 5 or len(audio_buffer) % 100 == 0:
                                # Log first 5 and then every 100th
                                inbound_count = audio_buffer.count('inbound')
                                outbound_count = audio_buffer.count('outbound')
                                other_count = len(audio_buffer) - inbound_count - outbound_count
                                logger.info(f"[{session_id}] 📥 Twilio media #{len(audio_buffer)}: track='{track}' (inbound:{inbound_count}, outbound:{outbound_count}, other:{other_count})")

                            if track != 'inbound':
                                # Skip outbound track to avoid transcribing agent's voice as technician
                                continue

                            payload = data['media']['payload']

                            # Process audio chunk synchronously
                            run_async(twilio_service._process_audio_chunk_sync(
                                session_id=session_id,
                                payload=payload
                            ))
                        else:
                            logger.warning(f"📥 Received media event but session_id is None!")

                    elif event_type == 'stop':
                        logger.info(f"Media stream stopped for session {session_id}")
                        break

                    else:
                        logger.warning(f"Unknown event type: {event_type}, full data: {data}")

                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON from Twilio: {message}")
                except Exception as e:
                    logger.error(f"Error processing media message: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"WebSocket error: {e}", exc_info=True)
        finally:
            # Clean up - close WAV file if open
            if session_id and session_id in twilio_service.active_streams:
                stream = twilio_service.active_streams[session_id]
                if 'technician' in stream and 'wav_file' in stream['technician']:
                    wav_file = stream['technician']['wav_file']
                    twilio_service._close_wav_file(wav_file, session_id)
                del twilio_service.active_streams[session_id]
            logger.info(f"Media stream closed for session {session_id}")
            
    @sock.route('/twilio/call-status/<session_id>')
    def call_status_handler(ws, session_id):
        """
        WebSocket endpoint for real-time call status updates
        Frontend connects here to receive notifications when call ends
        """
        import time

        try:
            logger.info(f"Call status WebSocket connected for session {session_id}")

            # Register this connection
            if session_id not in _active_status_connections:
                _active_status_connections[session_id] = set()
            _active_status_connections[session_id].add(ws)

            # Send initial connection confirmation
            ws.send(json.dumps({
                'event': 'connected',
                'session_id': session_id
            }))

            # Keep connection alive and send pending messages
            while True:
                try:
                    # Check for pending messages
                    if session_id in _pending_messages and _pending_messages[session_id]:
                        messages = _pending_messages[session_id].copy()
                        _pending_messages[session_id].clear()

                        for msg in messages:
                            ws.send(json.dumps(msg))
                            logger.info(f"Sent status message to session {session_id}")

                    # Try to receive message with timeout
                    message = ws.receive(timeout=0.5)

                    if message is None:
                        break

                    try:
                        data = json.loads(message)
                        # Handle any client messages if needed (e.g., ping/pong)
                        if data.get('type') == 'ping':
                            ws.send(json.dumps({'type': 'pong'}))
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON from client: {message}")

                except Exception as e:
                    # Timeout or connection closed
                    if "timeout" not in str(e).lower():
                        logger.error(f"Error in call status handler: {e}")
                        break

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

    @sock.route('/twilio/agent-audio-stream/<session_id>')
    def agent_audio_stream_handler(ws, session_id):
        """
        WebSocket endpoint for agent's browser audio stream (WebRTC MediaStream)
        Receives PCM audio data from browser's getUserMedia
        """
        import struct

        try:
            logger.info(f"Agent audio stream WebSocket connected for session {session_id}")

            # Get Twilio service
            twilio_service = get_twilio_service()

            # Initialize stream tracking for agent
            if session_id not in twilio_service.active_streams:
                twilio_service.active_streams[session_id] = {}

            twilio_service.active_streams[session_id]['agent'] = {
                'websocket': ws,
                'started_at': datetime.utcnow(),
                'audio_buffer': []
            }

            logger.info(f"📝 Registered agent WebSocket for session {session_id}")

            # Send confirmation to frontend that WebSocket is registered
            ws.send(json.dumps({
                'event': 'connected',
                'session_id': session_id,
                'type': 'agent_audio'
            }))

            while True:
                message = ws.receive()
                if message is None:
                    break

                try:
                    # Receive binary audio data (Int16Array from browser)
                    if isinstance(message, bytes):
                        # Browser now sends Int16Array directly (already in PCM format)
                        # No conversion needed - just use the data as-is
                        pcm_data = message

                        # Process audio chunk
                        run_async(twilio_service._process_agent_audio(
                            session_id=session_id,
                            audio_data=pcm_data
                        ))

                    # Handle JSON control messages
                    elif isinstance(message, str):
                        data = json.loads(message)
                        if data.get('event') == 'stop':
                            logger.info(f"Agent audio stream stopped for session {session_id}")
                            break

                except Exception as e: 
                    logger.error(f"Error processing agent audio message: {e}")

        except Exception as e:
            logger.error(f"Agent audio WebSocket error: {e}")
        finally:
            # Clean up
            if session_id in twilio_service.active_streams:
                if 'agent' in twilio_service.active_streams[session_id]:
                    del twilio_service.active_streams[session_id]['agent']
            logger.info(f"Agent audio stream closed for session {session_id}")

    @sock.route('/twilio/technician-transcription/<session_id>')
    def technician_transcription_handler(ws, session_id):
        """
        WebSocket endpoint for receiving technician transcriptions from backend
        Frontend connects here to display technician's speech transcriptions
        """
        try:
            logger.info(f"✅ Technician transcription WebSocket connected for session {session_id}")

            # Get Twilio service
            twilio_service = get_twilio_service()

            # DEBUG: Log all known sessions before adding
            all_sessions_before = list(twilio_service.active_streams.keys())
            logger.info(f"📝 DEBUG: Sessions BEFORE adding tech WS: {all_sessions_before}")

            # Initialize stream tracking if needed
            if session_id not in twilio_service.active_streams:
                logger.info(f"📝 Creating new active_streams entry for session {session_id}")
                twilio_service.active_streams[session_id] = {}

            # Store the WebSocket for technician transcriptions
            if 'technician' not in twilio_service.active_streams[session_id]:
                logger.info(f"📝 Creating 'technician' dict for session {session_id}")
                twilio_service.active_streams[session_id]['technician'] = {}

            twilio_service.active_streams[session_id]['technician']['transcription_ws'] = ws

            # DEBUG: Verify the WebSocket was stored
            stored_ws = twilio_service.active_streams[session_id]['technician'].get('transcription_ws')
            logger.info(f"📝 Registered technician transcription WebSocket for session {session_id}")
            logger.info(f"📝 DEBUG: WebSocket stored successfully: {stored_ws is not None}")

            # Send connection confirmation
            ws.send(json.dumps({
                'event': 'connected',
                'session_id': session_id,
                'type': 'technician_transcription'
            }))

            # Keep connection alive - receive messages (mostly for ping/pong)
            while True:
                message = ws.receive()
                if message is None:
                    break

                # Handle control messages
                try:
                    if isinstance(message, str):
                        data = json.loads(message)
                        if data.get('event') == 'ping':
                            ws.send(json.dumps({'event': 'pong'}))
                        elif data.get('event') == 'close':
                            logger.info(f"Technician transcription WebSocket close requested for session {session_id}")
                            break
                except Exception as e:
                    logger.warning(f"Error handling technician transcription message: {e}")

        except Exception as e:
            logger.error(f"❌ Technician transcription WebSocket error for session {session_id}: {e}")
        finally:
            # Clean up
            if session_id in twilio_service.active_streams:
                if 'technician' in twilio_service.active_streams[session_id]:
                    if 'transcription_ws' in twilio_service.active_streams[session_id]['technician']:
                        del twilio_service.active_streams[session_id]['technician']['transcription_ws']
            logger.info(f"Technician transcription WebSocket closed for session {session_id}")