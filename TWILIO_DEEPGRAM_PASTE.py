"""
READY-TO-PASTE CODE FOR TWILIO ROUTES
Copy the relevant sections into app/api/twilio_routes.py
"""

# ============================================================================
# SECTION 1: Add at the TOP of twilio_routes.py (with other imports)
# ============================================================================

from app.services.deepgram_twilio_bridge import get_deepgram_twilio_bridge

# ============================================================================
# SECTION 2: Replace the entire @sock.route('/twilio/media-stream/<session_id>')
# ============================================================================

@sock.route('/twilio/media-stream/<session_id>')
def twilio_media_stream(ws, session_id):
    """
    WebSocket endpoint for Twilio Media Streams
    Receives mulaw audio from Twilio phone calls
    """
    import audioop
    import base64

    try:
        logger.info(f"[{session_id}] 📞 Twilio Media Stream WebSocket connected")

        # Get services
        twilio_service = get_twilio_service()
        deepgram_bridge = get_deepgram_twilio_bridge()

        # Initialize stream tracking
        if session_id not in twilio_service.active_streams:
            twilio_service.active_streams[session_id] = {}

        twilio_service.active_streams[session_id]['twilio'] = {
            'websocket': ws,
            'started_at': datetime.utcnow(),
            'stream_sid': None
        }

        # Deepgram connection (will be created when stream starts)
        customer_deepgram = None

        while True:
            message = ws.receive()
            if message is None:
                break

            try:
                data = json.loads(message)
                event_type = data.get('event')

                if event_type == 'start':
                    logger.info(f"[{session_id}] 📞 Twilio stream started")
                    stream_sid = data.get('streamSid')
                    twilio_service.active_streams[session_id]['twilio']['stream_sid'] = stream_sid

                    # Create Deepgram stream for CUSTOMER (phone audio)
                    def on_customer_transcript(result):
                        """Send customer transcriptions to frontend"""
                        try:
                            if session_id in twilio_service.active_streams:
                                tech_ws = twilio_service.active_streams[session_id].get('technician', {}).get('transcription_ws')

                                if tech_ws:
                                    message = {
                                        'type': 'transcription',
                                        'text': result['text'],
                                        'speaker_role': 'customer',  # Phone = Customer
                                        'speaker_label': 'Client',
                                        'is_final': result['is_final'],
                                        'speech_final': result.get('speech_final', False),
                                        'confidence': result['confidence'],
                                        'timestamp': datetime.utcnow().isoformat(),
                                        'language': result['language'],
                                        'model': result['model']
                                    }
                                    tech_ws.send(json.dumps(message))
                                    logger.debug(f"[{session_id}] 📞→💻 Customer: {result['text'][:30]}...")
                        except Exception as e:
                            logger.error(f"[{session_id}] Error sending customer transcript: {e}")

                    customer_deepgram = deepgram_bridge.create_customer_stream(
                        session_id=session_id,
                        language='fr',
                        on_transcript=on_customer_transcript
                    )

                    if customer_deepgram:
                        logger.info(f"[{session_id}] ✅ Customer Deepgram stream ready")
                    else:
                        logger.error(f"[{session_id}] ❌ Failed to create customer Deepgram stream")

                elif event_type == 'media':
                    # Decode mulaw audio from Twilio
                    payload = data.get('media', {}).get('payload', '')
                    if not payload:
                        continue

                    # Decode base64 mulaw
                    mulaw_data = base64.b64decode(payload)

                    # Convert mulaw to PCM (16-bit linear)
                    pcm_data = audioop.ulaw2lin(mulaw_data, 2)

                    # Send to Deepgram
                    if customer_deepgram and customer_deepgram.is_connected:
                        deepgram_bridge.send_customer_audio(session_id, pcm_data)

                elif event_type == 'stop':
                    logger.info(f"[{session_id}] 📞 Twilio stream stopped")
                    break

            except json.JSONDecodeError as e:
                logger.error(f"[{session_id}] JSON decode error: {e}")
            except Exception as e:
                logger.error(f"[{session_id}] Error processing Twilio message: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"[{session_id}] Twilio media stream error: {e}", exc_info=True)
    finally:
        # Close Deepgram connection
        deepgram_bridge.close_session(session_id)

        # Cleanup
        if session_id in twilio_service.active_streams:
            if 'twilio' in twilio_service.active_streams[session_id]:
                del twilio_service.active_streams[session_id]['twilio']

        logger.info(f"[{session_id}] 📞 Twilio media stream closed")


# ============================================================================
# SECTION 3: Replace the entire @sock.route('/twilio/agent-audio-stream/<session_id>')
# ============================================================================

@sock.route('/twilio/agent-audio-stream/<session_id>')
def agent_audio_stream_handler(ws, session_id):
    """
    WebSocket endpoint for agent's browser audio stream (getUserMedia)
    Receives PCM audio data from browser
    """
    try:
        logger.info(f"[{session_id}] 🎤 Agent audio stream WebSocket connected")

        # Get services
        twilio_service = get_twilio_service()
        deepgram_bridge = get_deepgram_twilio_bridge()

        # Initialize stream tracking
        if session_id not in twilio_service.active_streams:
            twilio_service.active_streams[session_id] = {}

        twilio_service.active_streams[session_id]['agent'] = {
            'websocket': ws,
            'started_at': datetime.utcnow()
        }

        # Send confirmation
        ws.send(json.dumps({
            'event': 'connected',
            'session_id': session_id,
            'type': 'agent_audio'
        }))

        # Create Deepgram stream for TECHNICIAN (browser audio)
        def on_technician_transcript(result):
            """Send technician transcriptions to frontend"""
            try:
                if session_id in twilio_service.active_streams:
                    tech_ws = twilio_service.active_streams[session_id].get('technician', {}).get('transcription_ws')

                    if tech_ws:
                        message = {
                            'type': 'transcription',
                            'text': result['text'],
                            'speaker_role': 'technician',  # Browser = Technician
                            'speaker_label': 'Technicien',
                            'is_final': result['is_final'],
                            'speech_final': result.get('speech_final', False),
                            'confidence': result['confidence'],
                            'timestamp': datetime.utcnow().isoformat(),
                            'language': result['language'],
                            'model': result['model']
                        }
                        tech_ws.send(json.dumps(message))
                        logger.debug(f"[{session_id}] 🎤→💻 Technician: {result['text'][:30]}...")
            except Exception as e:
                logger.error(f"[{session_id}] Error sending technician transcript: {e}")

        technician_deepgram = deepgram_bridge.create_technician_stream(
            session_id=session_id,
            language='fr',
            on_transcript=on_technician_transcript
        )

        if technician_deepgram:
            logger.info(f"[{session_id}] ✅ Technician Deepgram stream ready")
        else:
            logger.error(f"[{session_id}] ❌ Failed to create technician Deepgram stream")

        while True:
            message = ws.receive()
            if message is None:
                break

            try:
                # Receive binary PCM audio
                if isinstance(message, bytes):
                    pcm_data = message

                    # Send to Deepgram
                    if technician_deepgram and technician_deepgram.is_connected:
                        deepgram_bridge.send_technician_audio(session_id, pcm_data)

                # Handle JSON control messages
                elif isinstance(message, str):
                    data = json.loads(message)
                    if data.get('event') == 'stop':
                        logger.info(f"[{session_id}] Agent audio stopped")
                        break

            except Exception as e:
                logger.error(f"[{session_id}] Error processing agent audio: {e}")

    except Exception as e:
        logger.error(f"[{session_id}] Agent audio stream error: {e}", exc_info=True)
    finally:
        # Cleanup (Deepgram closed in media stream handler)
        if session_id in twilio_service.active_streams:
            if 'agent' in twilio_service.active_streams[session_id]:
                del twilio_service.active_streams[session_id]['agent']

        logger.info(f"[{session_id}] 🎤 Agent audio stream closed")
