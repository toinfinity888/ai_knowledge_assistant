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
from app.services.deepgram_twilio_bridge import get_deepgram_twilio_bridge
from app.services.realtime_transcription_service import get_transcription_service

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
        # DEBUG: Use print() to bypass any logger filtering
        print(f"🔥 VOICE WEBHOOK CALLED - Form keys: {list(request.form.keys())}")
        print(f"🔥 VOICE WEBHOOK - Full form data: {dict(request.form)}")

        # DEBUG: Log ALL form data and values received from Twilio
        logger.info(f"📋 DEBUG: Form data keys: {list(request.form.keys())}")
        logger.info(f"📋 DEBUG: Values keys: {list(request.values.keys())}")
        logger.info(f"📋 DEBUG: Full form data: {dict(request.form)}")

        # Get the phone number to call from the request
        to_number = request.form.get('To', request.values.get('To'))
        from_number = request.form.get('From', request.values.get('From'))

        # Get session_id passed from frontend (CRITICAL for WebSocket matching)
        session_id = request.form.get('session_id', request.values.get('session_id'))

        logger.info(f"📞 Browser calling {to_number} from {from_number}")
        logger.info(f"📋 Session ID from frontend: {session_id}")

        # CRITICAL: If session_id is None, log a clear warning
        if not session_id:
            logger.error(f"📋 ❌ CRITICAL: session_id is None! WebSocket matching will FAIL!")
            logger.error(f"📋 ❌ This means frontend didn't pass session_id in params, or Twilio stripped it")

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

        twiml_output = str(response)
        logger.info(f"✅ Generated TwiML for call to {to_number}")
        logger.info(f"📜 TwiML output:\n{twiml_output}")
        return twiml_output, 200, {'Content-Type': 'text/xml'}

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
        import audioop
        import base64
        import uuid
        import time

        session_id = None
        stream_sid = None
        audio_buffer = []

        # Get services
        twilio_service = get_twilio_service()
        deepgram_bridge = get_deepgram_twilio_bridge()

        # Deepgram connection (will be created when stream starts)
        customer_deepgram = None

        # Utterance tracking: maps speaker_role -> current utterance_id
        current_utterance_ids = {}

        # Timestamp tracking for pause-based segmentation (maps speaker_role -> last_timestamp)
        last_transcript_time = {}

        # Finalized text accumulation: maps speaker_role -> finalized text (locked-in from final results)
        finalized_text = {}

        # Pause threshold in milliseconds (from transcription_config.json: backend_segment_pause)
        PAUSE_THRESHOLD_MS = 2000

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

                    if event_type != 'media':  # Skip verbose media events
                        print(f"🔥 MEDIA STREAM EVENT: {event_type}")
                    logger.info(f"Event type: {event_type}")

                    if event_type == 'start':
                        # Extract session_id from custom parameters
                        stream_sid = data['start']['streamSid']
                        custom_params = data['start'].get('customParameters', {})
                        session_id = custom_params.get('session_id', stream_sid)

                        # CRITICAL DEBUG with print()
                        print(f"🔥 START EVENT - stream_sid: {stream_sid}")
                        print(f"🔥 START EVENT - customParameters: {custom_params}")
                        print(f"🔥 START EVENT - session_id extracted: {session_id}")
                        print(f"🔥 START EVENT - twilio_service id: {id(twilio_service)}")

                        # Check what's already in active_streams
                        all_sessions = list(twilio_service.active_streams.keys())
                        print(f"🔥 START EVENT - All sessions in active_streams: {all_sessions}")

                        if session_id in twilio_service.active_streams:
                            existing = twilio_service.active_streams[session_id]
                            print(f"🔥 START EVENT - Existing session data keys: {list(existing.keys())}")
                            if 'technician' in existing:
                                tech_data = existing['technician']
                                print(f"🔥 START EVENT - Existing technician keys: {list(tech_data.keys())}")
                                print(f"🔥 START EVENT - transcription_ws exists: {'transcription_ws' in tech_data}")
                            else:
                                print(f"🔥 START EVENT - NO 'technician' key in existing session!")
                        else:
                            print(f"🔥 START EVENT - session_id NOT in active_streams yet!")

                        # Log detailed start info including track configuration
                        logger.info(f"📞 Media stream started: stream_sid={stream_sid}, session_id={session_id}")
                        logger.info(f"📞 Start event tracks: {data['start'].get('tracks', 'unknown')}")
                        logger.info(f"📞 Custom params: {custom_params}")

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

                        # Create Deepgram stream for TECHNICIAN (phone audio)
                        def on_phone_technician_transcript(result):
                            """Send phone technician transcriptions to frontend with pause-based segmentation"""
                            try:
                                print(f"🔥 PHONE TRANSCRIPT: '{result.get('text', '')[:50]}' (is_final={result.get('is_final')})")
                                logger.info(f"[{session_id}] 📞 PHONE TRANSCRIPT CALLBACK FIRED: '{result.get('text', '')[:50]}...' (is_final={result.get('is_final')})")

                                if session_id in twilio_service.active_streams:
                                    tech_ws = twilio_service.active_streams[session_id].get('technician', {}).get('transcription_ws')

                                    # DEBUG: Log the state of active_streams for this session
                                    session_data = twilio_service.active_streams[session_id]
                                    tech_data = session_data.get('technician', {})
                                    logger.info(f"[{session_id}] 📞 DEBUG: session has keys={list(session_data.keys())}, technician has keys={list(tech_data.keys())}")

                                    if tech_ws:
                                        speaker_role = 'technician'
                                        current_time = time.time()

                                        # Check if pause exceeded threshold (time-based segmentation)
                                        if speaker_role in last_transcript_time:
                                            pause_duration_ms = (current_time - last_transcript_time[speaker_role]) * 1000
                                            logger.info(f"[{session_id}] 🕐 Technician (phone) pause check: {pause_duration_ms:.0f}ms (threshold: {PAUSE_THRESHOLD_MS}ms)")
                                            if pause_duration_ms > PAUSE_THRESHOLD_MS:
                                                # Pause exceeded threshold - start new bubble
                                                if speaker_role in current_utterance_ids:
                                                    old_id = current_utterance_ids[speaker_role]
                                                    logger.info(f"[{session_id}] ⏸️ Technician (phone) pause {pause_duration_ms:.0f}ms detected, closing utterance {old_id[:8]}")
                                                    del current_utterance_ids[speaker_role]
                                                    # Clear finalized text for new bubble
                                                    if speaker_role in finalized_text:
                                                        del finalized_text[speaker_role]
                                        else:
                                            logger.info(f"[{session_id}] 🆕 First technician (phone) transcript, no pause check")

                                        # Get or create utterance_id for this speaker
                                        if speaker_role not in current_utterance_ids:
                                            # New utterance - generate new UUID
                                            current_utterance_ids[speaker_role] = str(uuid.uuid4())

                                        utterance_id = current_utterance_ids[speaker_role]

                                        # Get current segment text from Deepgram (cumulative within segment)
                                        current_segment = result['text'].strip()

                                        # Build full text: finalized text + current segment
                                        if speaker_role in finalized_text and finalized_text[speaker_role]:
                                            # We have finalized text, append current segment
                                            full_text = finalized_text[speaker_role] + " " + current_segment
                                        else:
                                            # No finalized text yet, just use current segment
                                            full_text = current_segment

                                        # If this is a final result, update finalized_text
                                        if result['is_final']:
                                            finalized_text[speaker_role] = full_text

                                        message = {
                                            'type': 'transcription',
                                            'utterance_id': utterance_id,
                                            'speaker_role': speaker_role,
                                            'speaker_label': 'Technicien',
                                            'text': full_text,
                                            'is_final': result['is_final'],
                                            'speech_final': result.get('speech_final', False),
                                            'confidence': result['confidence'],
                                            'timestamp': datetime.utcnow().isoformat(),
                                            'language': result['language'],
                                            'model': result['model']
                                        }
                                        tech_ws.send(json.dumps(message))
                                        print(f"🔥 ✅ TRANSCRIPT SENT TO FRONTEND: '{message['text'][:40]}' (is_final={message['is_final']})")
                                        logger.debug(f"[{session_id}] Technician (phone) [{utterance_id[:8]}]: {result['text'][:30]}...")

                                        # Update timestamp for this speaker
                                        last_transcript_time[speaker_role] = current_time

                                        # ============================================================
                                        # TRIGGER AGENT PIPELINE FOR RAG/KNOWLEDGE BASE SUGGESTIONS
                                        # Process when speech_final=True (complete utterance from speaker)
                                        # This sends the transcription to the agent orchestrator which:
                                        # 1. Analyzes context to determine if enough info for KB query
                                        # 2. Generates optimized queries for Qdrant vector search
                                        # 3. Retrieves relevant knowledge and generates suggestions
                                        # ============================================================
                                        if result.get('speech_final', False) and full_text.strip():
                                            try:
                                                transcription_service = get_transcription_service()
                                                if transcription_service:
                                                    # Use speaker="technician" - the person calling for help
                                                    # The orchestrator expects "technician" for customer_last_message
                                                    logger.info(f"[{session_id}] 🧠 TRIGGERING AGENT PIPELINE for: '{full_text[:50]}...'")
                                                    run_async(transcription_service.process_transcription_segment(
                                                        session_id=session_id,
                                                        speaker="technician",  # Person on phone seeking help
                                                        text=full_text,
                                                        start_time=0.0,  # We don't have exact timing from Deepgram streaming
                                                        end_time=0.0,
                                                        confidence=result.get('confidence', 0.0),
                                                        language=result.get('language', 'en'),
                                                    ))
                                                    logger.info(f"[{session_id}] ✅ Agent pipeline triggered successfully")
                                                else:
                                                    logger.warning(f"[{session_id}] ⚠️ Transcription service not initialized")
                                            except Exception as agent_error:
                                                logger.error(f"[{session_id}] ❌ Error triggering agent pipeline: {agent_error}", exc_info=True)
                                    else:
                                        logger.warning(f"[{session_id}] No tech_ws available to send transcript")
                                else:
                                    logger.warning(f"[{session_id}] Session not in active_streams")

                            except Exception as e:
                                logger.error(f"[{session_id}] Error sending phone technician transcript: {e}", exc_info=True)

                        phone_technician_deepgram = deepgram_bridge.create_customer_stream(
                            session_id=session_id,
                            language='en',  # TESTING: Changed from 'fr' to 'en' to diagnose empty transcripts
                            on_transcript=on_phone_technician_transcript
                        )

                        if phone_technician_deepgram:
                            logger.info(f"[{session_id}] Phone Technician Deepgram stream ready (is_connected={phone_technician_deepgram.is_connected})")
                        else:
                            logger.error(f"[{session_id}] Failed to create phone technician Deepgram stream")

                    elif event_type == 'media':
                        # Audio data received - process it synchronously
                        if session_id:
                            # IMPORTANT: Filter by track to avoid mixing audio sources
                            # With track='both_tracks' in browser-initiated calls to phone:
                            #   - 'inbound' track: audio FROM the browser/agent (the caller)
                            #   - 'outbound' track: audio FROM the phone/customer (the callee)
                            # We only want to transcribe the OUTBOUND track (phone customer's voice)
                            # Browser audio is already captured directly via browser MediaRecorder
                            track = data['media'].get('track', 'unknown')

                            # Log ALL tracks received for debugging
                            audio_buffer.append(track)  # Store track names
                            if len(audio_buffer) <= 5 or len(audio_buffer) % 100 == 0:
                                # Log first 5 and then every 100th
                                inbound_count = audio_buffer.count('inbound')
                                outbound_count = audio_buffer.count('outbound')
                                other_count = len(audio_buffer) - inbound_count - outbound_count
                                logger.info(f"[{session_id}] Twilio media #{len(audio_buffer)}: track='{track}' (inbound:{inbound_count}, outbound:{outbound_count}, other:{other_count})")

                                # DEBUG: Log tech_ws availability periodically
                                if session_id in twilio_service.active_streams:
                                    tech_ws_check = twilio_service.active_streams[session_id].get('technician', {}).get('transcription_ws')
                                    logger.info(f"[{session_id}] 🔍 DEBUG tech_ws check: available={tech_ws_check is not None}")
                                else:
                                    logger.warning(f"[{session_id}] 🔍 DEBUG: session_id NOT in active_streams!")

                            # Only process OUTBOUND track (phone customer's voice)
                            if track != 'outbound':
                                # Skip inbound track - browser audio is already captured via browser WebSocket
                                continue

                            payload = data['media']['payload']

                            # DEBUG: Log that we're processing OUTBOUND/phone audio (only first 3 and every 500th)
                            if len(audio_buffer) <= 3 or len(audio_buffer) % 500 == 0:
                                print(f"🔥 OUTBOUND/PHONE AUDIO: chunk #{len(audio_buffer)}, payload_len={len(payload) if payload else 0}")

                            # Decode mulaw audio and CONVERT TO PCM before sending to Deepgram
                            if payload and phone_technician_deepgram and phone_technician_deepgram.is_connected:
                                # Decode base64 mulaw
                                mulaw_data = base64.b64decode(payload)

                                # Convert mulaw to PCM (16-bit linear)
                                # Deepgram expects PCM, not raw mulaw
                                pcm_data = audioop.ulaw2lin(mulaw_data, 2)

                                # Send PCM to Deepgram (phone = technician)
                                sent = deepgram_bridge.send_customer_audio(session_id, pcm_data)
                                if len(audio_buffer) <= 3:
                                    print(f"🔥 AUDIO SENT TO DEEPGRAM: chunk #{len(audio_buffer)}, pcm_bytes={len(pcm_data)}, sent={sent}")
                            elif payload:
                                # Log why we're not sending audio
                                if not phone_technician_deepgram:
                                    logger.warning(f"[{session_id}] ❌ phone_technician_deepgram is None - cannot send audio!")
                                elif not phone_technician_deepgram.is_connected:
                                    logger.warning(f"[{session_id}] ❌ phone_technician_deepgram is not connected yet!")

                            # Old transcription service removed - now using Deepgram bridge exclusively
                            # run_async(twilio_service._process_audio_chunk_sync(
                            #     session_id=session_id,
                            #     payload=payload
                            # ))
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
            # Close Deepgram connection
            if session_id:
                deepgram_bridge.close_session(session_id)

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
        import uuid
        import time

        # Utterance tracking for technician
        current_utterance_ids = {}

        # Timestamp tracking for pause-based segmentation
        last_transcript_time = {}

        # Finalized text accumulation: maps speaker_role -> finalized text (locked-in from final results)
        finalized_text = {}

        # Pause threshold in milliseconds (from transcription_config.json: backend_segment_pause)
        PAUSE_THRESHOLD_MS = 2000

        try:
            logger.info(f"Agent audio stream WebSocket connected for session {session_id}")

            # Get services
            twilio_service = get_twilio_service()
            deepgram_bridge = get_deepgram_twilio_bridge()

            # Initialize stream tracking for agent
            print(f"🔥 AGENT WS - Before init, session exists: {session_id in twilio_service.active_streams}")
            if session_id in twilio_service.active_streams:
                print(f"🔥 AGENT WS - Existing keys: {list(twilio_service.active_streams[session_id].keys())}")

            if session_id not in twilio_service.active_streams:
                twilio_service.active_streams[session_id] = {}

            twilio_service.active_streams[session_id]['agent'] = {
                'websocket': ws,
                'started_at': datetime.utcnow(),
                'audio_buffer': []
            }

            print(f"🔥 AGENT WS - After init, keys: {list(twilio_service.active_streams[session_id].keys())}")
            print(f"🔥 AGENT WS - twilio_service id: {id(twilio_service)}")
            logger.info(f"📝 Registered agent WebSocket for session {session_id}")

            # Send confirmation to frontend that WebSocket is registered
            ws.send(json.dumps({
                'event': 'connected',
                'session_id': session_id,
                'type': 'agent_audio'
            }))

            # Create Deepgram stream for AGENT (browser audio)
            def on_agent_transcript(result):
                """Send agent (browser) transcriptions to frontend with pause-based segmentation"""
                try:
                    if session_id in twilio_service.active_streams:
                        tech_ws = twilio_service.active_streams[session_id].get('technician', {}).get('transcription_ws')

                        if tech_ws:
                            speaker_role = 'agent'
                            current_time = time.time()

                            # Check if pause exceeded threshold (time-based segmentation)
                            if speaker_role in last_transcript_time:
                                pause_duration_ms = (current_time - last_transcript_time[speaker_role]) * 1000
                                logger.info(f"[{session_id}] 🕐 Agent (browser) pause check: {pause_duration_ms:.0f}ms (threshold: {PAUSE_THRESHOLD_MS}ms)")
                                if pause_duration_ms > PAUSE_THRESHOLD_MS:
                                    # Pause exceeded threshold - start new bubble
                                    if speaker_role in current_utterance_ids:
                                        old_id = current_utterance_ids[speaker_role]
                                        logger.info(f"[{session_id}] ⏸️ Agent (browser) pause {pause_duration_ms:.0f}ms detected, closing utterance {old_id[:8]}")
                                        del current_utterance_ids[speaker_role]
                                        # Clear finalized text for new bubble
                                        if speaker_role in finalized_text:
                                            del finalized_text[speaker_role]
                            else:
                                logger.info(f"[{session_id}] 🆕 First agent (browser) transcript, no pause check")

                            # Get or create utterance_id for this speaker
                            if speaker_role not in current_utterance_ids:
                                # New utterance - generate new UUID
                                current_utterance_ids[speaker_role] = str(uuid.uuid4())

                            utterance_id = current_utterance_ids[speaker_role]

                            # Get current segment text from Deepgram (cumulative within segment)
                            current_segment = result['text'].strip()

                            # Build full text: finalized text + current segment
                            if speaker_role in finalized_text and finalized_text[speaker_role]:
                                # We have finalized text, append current segment
                                full_text = finalized_text[speaker_role] + " " + current_segment
                            else:
                                # No finalized text yet, just use current segment
                                full_text = current_segment

                            # If this is a final result, update finalized_text
                            if result['is_final']:
                                finalized_text[speaker_role] = full_text

                            message = {
                                'type': 'transcription',
                                'utterance_id': utterance_id,
                                'speaker_role': speaker_role,
                                'speaker_label': 'Agent',
                                'text': full_text,
                                'is_final': result['is_final'],
                                'speech_final': result.get('speech_final', False),
                                'confidence': result['confidence'],
                                'timestamp': datetime.utcnow().isoformat(),
                                'language': result['language'],
                                'model': result['model']
                            }
                            tech_ws.send(json.dumps(message))
                            logger.debug(f"[{session_id}] Agent (browser) [{utterance_id[:8]}]: {result['text'][:30]}...")

                            # Update timestamp for this speaker
                            last_transcript_time[speaker_role] = current_time

                except Exception as e:
                    logger.error(f"[{session_id}] Error sending agent (browser) transcript: {e}")

            agent_deepgram = deepgram_bridge.create_technician_stream(
                session_id=session_id,
                language='en',  # TESTING: Changed from 'fr' to 'en' to diagnose empty transcripts
                on_transcript=on_agent_transcript
            )

            if agent_deepgram:
                logger.info(f"[{session_id}] ✅ Agent (browser) Deepgram stream ready")
            else:
                logger.error(f"[{session_id}] ❌ Failed to create agent (browser) Deepgram stream")

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

                        # Send to Deepgram
                        if agent_deepgram and agent_deepgram.is_connected:
                            deepgram_bridge.send_technician_audio(session_id, pcm_data)

                        # Old transcription service removed - now using Deepgram bridge exclusively
                        # run_async(twilio_service._process_agent_audio(
                        #     session_id=session_id,
                        #     audio_data=pcm_data
                        # ))

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
            print(f"🔥 TECH TRANSCRIPTION WS CONNECTED for session: {session_id}")
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
            print(f"🔥 TECH WS STORED - session: {session_id}, stored: {stored_ws is not None}")
            print(f"🔥 TECH WS - active_streams keys: {list(twilio_service.active_streams.keys())}")
            print(f"🔥 TECH WS - session keys: {list(twilio_service.active_streams[session_id].keys())}")
            print(f"🔥 TECH WS - twilio_service id: {id(twilio_service)}")
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