"""
Configuration Testing Routes
Provides routes and WebSocket endpoints for testing transcription with different configurations
"""
import logging
import base64
import io
import json
from datetime import datetime
from flask import Blueprint, render_template
from simple_websocket import Server, ConnectionClosed

from app.services.enhanced_transcription_service import get_enhanced_transcription_service

logger = logging.getLogger(__name__)

config_test_bp = Blueprint('config_test', __name__)


@config_test_bp.route('/config')
def config_interface():
    """
    Serve the configuration interface page

    Returns:
        HTML page for configuration and testing
    """
    return render_template('config_interface.html')


def register_config_websocket_routes(sock):
    """
    Register WebSocket routes for configuration testing

    Args:
        sock: Flask-Sock instance
    """

    @sock.route('/ws/config/test-audio')
    def config_test_audio(ws: Server):
        """
        WebSocket endpoint for testing audio transcription
        Receives audio from browser, processes it through the transcription pipeline,
        and sends back transcriptions
        """
        session_id = f"config-test-{datetime.now().timestamp()}"
        logger.info(f"[{session_id}] Configuration test WebSocket connected")

        # Get transcription service
        transcription_service = get_enhanced_transcription_service()

        # Audio buffer
        audio_buffer = bytearray()
        chunk_count = 0

        try:
            while True:
                # Receive message from client
                message = ws.receive()

                if message is None:
                    break

                try:
                    data = json.loads(message)
                    message_type = data.get('type')

                    if message_type == 'audio':
                        # Receive raw PCM audio data (Int16Array from browser AudioWorklet)
                        audio_base64 = data.get('data')
                        if not audio_base64:
                            continue

                        # Decode from base64 - this is raw PCM Int16 data
                        pcm_data = base64.b64decode(audio_base64)

                        chunk_count += 1
                        logger.info(f"[{session_id}] Received audio chunk #{chunk_count}: {len(pcm_data)} bytes PCM")

                        # Calculate audio metrics from PCM data
                        import struct
                        import numpy as np

                        samples = struct.unpack(f'{len(pcm_data)//2}h', pcm_data)
                        if len(samples) > 0:
                            audio_rms = float(np.sqrt(np.mean(np.square(samples))))
                            max_amplitude = float(max(abs(s) for s in samples))
                        else:
                            audio_rms = 0.0
                            max_amplitude = 0.0

                        # Get current buffer size from transcription service
                        buffer_key = f"{session_id}_agent"
                        current_buffer = transcription_service.audio_buffers.get(buffer_key, {})
                        buffer_size = sum(len(chunk) for chunk in current_buffer.get('chunks', []))

                        # Send real-time audio metrics to frontend
                        ws.send(json.dumps({
                            'type': 'audio_metrics',
                            'rms': round(audio_rms, 1),
                            'max_amplitude': int(max_amplitude),
                            'buffer_size': buffer_size
                        }))

                        # Process through transcription service
                        import asyncio

                        # Create event loop if needed
                        try:
                            loop = asyncio.get_event_loop()
                        except RuntimeError:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)

                        # Process audio (already 16kHz PCM from browser)
                        result = loop.run_until_complete(
                            transcription_service.process_audio_stream(
                                session_id=session_id,
                                audio_chunk=pcm_data,
                                timestamp=datetime.now().timestamp(),
                                speaker='agent',  # Browser audio = agent
                                sample_rate=16000
                            )
                        )

                        # Send transcription back to client if available
                        if result:
                            pause_ms = result.get('pause_duration_ms', 0.0)
                            logger.info(f"[{session_id}] Transcription (pause={pause_ms:.0f}ms): {result.get('text', '')[:50]}...")
                            ws.send(json.dumps({
                                'type': 'transcription',
                                'text': result.get('text', ''),
                                'timestamp': result.get('timestamp', datetime.utcnow().isoformat()),
                                'confidence': result.get('confidence', 0.0),
                                'language': result.get('language', 'unknown'),
                                'pause_duration_ms': pause_ms
                            }))

                    elif message_type == 'ping':
                        # Heartbeat
                        ws.send(json.dumps({'type': 'pong'}))

                    else:
                        logger.warning(f"[{session_id}] Unknown message type: {message_type}")

                except json.JSONDecodeError as e:
                    logger.error(f"[{session_id}] JSON decode error: {e}")
                    continue

                except Exception as e:
                    logger.error(f"[{session_id}] Error processing message: {e}", exc_info=True)
                    ws.send(json.dumps({
                        'type': 'error',
                        'message': f'Error: {str(e)}'
                    }))

        except ConnectionClosed:
            logger.info(f"[{session_id}] WebSocket connection closed by client")

        except Exception as e:
            logger.error(f"[{session_id}] WebSocket error: {e}", exc_info=True)

        finally:
            # Cleanup session
            try:
                transcription_service.end_session(session_id)
                logger.info(f"[{session_id}] Session ended, processed {chunk_count} audio chunks")
            except Exception as e:
                logger.error(f"[{session_id}] Error ending session: {e}")

    logger.info("Configuration test WebSocket routes registered")
