"""
Twilio Audio Service for Bidirectional Audio Streaming
Handles real-time audio streaming between technician and AI system
"""
import asyncio
import base64
import json
import logging
from typing import Dict, Optional, Any
from datetime import datetime
import audioop
import wave
import os
from pathlib import Path
from twilio.rest import Client

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Логируем всё
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
logger.addHandler(ch)


class TwilioAudioService:
    """
    Manages bidirectional audio streaming with Twilio
    - Receives audio from technician
    - Sends AI-generated audio responses back
    - Handles audio format conversion (mulaw <-> linear PCM)
    """

    def __init__(self, account_sid: str, auth_token: str, phone_number: str, enable_recording: bool = True):
        self.client = Client(account_sid, auth_token)
        self.phone_number = phone_number
        self.active_streams: Dict[str, Dict[str, Any]] = {}

        self.TWILIO_SAMPLE_RATE = 8000
        self.TWILIO_CHANNELS = 1
        self.WHISPER_SAMPLE_RATE = 16000

        # Audio recording configuration
        self.enable_recording = enable_recording
        self.recordings_dir = Path("audio_recordings")
        if self.enable_recording:
            self.recordings_dir.mkdir(exist_ok=True)
            logger.info(f"Audio recording ENABLED - files will be saved to: {self.recordings_dir.absolute()}")
        else:
            logger.info("Audio recording DISABLED")

        logger.info(f"TwilioAudioService initialized with phone {phone_number}")

    def _create_wav_file(self, session_id: str, speaker: str = "technician") -> Optional[wave.Wave_write]:
        """
        Create a WAV file for recording audio

        Args:
            session_id: Session identifier
            speaker: Speaker type (technician or agent)

        Returns:
            Wave file object or None if recording disabled
        """
        if not self.enable_recording:
            return None

        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"{speaker}_{session_id}_{timestamp}.wav"
            filepath = self.recordings_dir / filename

            wav_file = wave.open(str(filepath), 'wb')
            wav_file.setnchannels(self.TWILIO_CHANNELS)  # Mono
            wav_file.setsampwidth(2)  # 16-bit = 2 bytes
            wav_file.setframerate(self.TWILIO_SAMPLE_RATE)  # 8kHz (native Twilio format)

            logger.info(f"📼 Created recording file: {filepath}")
            return wav_file

        except Exception as e:
            logger.error(f"Failed to create WAV file for {session_id}: {e}")
            return None

    def _close_wav_file(self, wav_file: Optional[wave.Wave_write], session_id: str):
        """
        Close WAV file and log statistics

        Args:
            wav_file: Wave file object to close
            session_id: Session identifier for logging
        """
        if wav_file:
            try:
                # Get info before closing
                nframes = wav_file.getnframes()
                duration_seconds = nframes / self.TWILIO_SAMPLE_RATE  # 8kHz

                # Try to get filename before closing
                filename = 'unknown'
                try:
                    if hasattr(wav_file, '_file') and wav_file._file and hasattr(wav_file._file, 'name'):
                        filename = wav_file._file.name
                except:
                    pass

                # Close the file
                wav_file.close()

                # Log statistics
                logger.info(f"📼 Closed recording for session {session_id}")
                logger.info(f"   Duration: {duration_seconds:.2f} seconds")
                logger.info(f"   Frames: {nframes}")
                logger.info(f"   File: {filename}")
            except Exception as e:
                logger.error(f"Error closing WAV file for {session_id}: {e}")

    async def _process_audio_chunk_sync(self, session_id: str, payload: str):
        """
        Process incoming audio chunk from Twilio media stream
        NEW ARCHITECTURE: Buffer 8kHz audio, resample entire 1-second buffer once
        """
        try:
            # logger.info(f"[{session_id}] 🔧 STAGE 7: _process_audio_chunk_sync called")
            # logger.info(f"[{session_id}]    Input: Base64 payload length={len(payload)} chars")

            # Decode base64
            mulaw_audio = base64.b64decode(payload)
            # logger.info(f"[{session_id}] ✅ STAGE 8: Base64 decoded → {len(mulaw_audio)} bytes mulaw")

            # Decode mulaw to PCM (KEEP AT 8kHz - don't resample yet!)
            pcm_8k = audioop.ulaw2lin(mulaw_audio, 2)
            # logger.info(f"[{session_id}] ✅ STAGE 9: Mulaw decoded → {len(pcm_8k)} bytes PCM (8kHz, 16-bit)")

            # Calculate audio characteristics at 8kHz (for monitoring)
            import struct
            import numpy as np
            num_samples_8k = len(pcm_8k) // 2
            duration_ms = (num_samples_8k / self.TWILIO_SAMPLE_RATE) * 1000
            samples_8k = struct.unpack(f'{num_samples_8k}h', pcm_8k)
            rms_8k = np.sqrt(np.mean(np.square(samples_8k))) if len(samples_8k) > 0 else 0
            max_amplitude_8k = max(abs(s) for s in samples_8k) if len(samples_8k) > 0 else 0

            logger.info(f"[{session_id}] 📊 Audio chunk: RMS={rms_8k:.1f}, Max={max_amplitude_8k}, Samples={num_samples_8k}, Duration={duration_ms:.1f}ms")

            if rms_8k < 5:
                logger.warning(f"[{session_id}] ⚠️ WARNING: Very low audio level (RMS={rms_8k:.1f}) - may be silence or mic issue")
            elif rms_8k > 2500:
                logger.warning(f"[{session_id}] ⚠️ WARNING: Very high audio level (RMS={rms_8k:.1f}) - may be clipping")

            # Buffer 8kHz audio (NEW: buffer BEFORE resampling)
            await self._process_audio_chunk(session_id, pcm_8k)

        except Exception as e:
            logger.error(f"[{session_id}] ❌ ERROR in audio decoding: {e}", exc_info=True)


    async def _process_audio_chunk(self, session_id: str, audio_data: bytes):
        """
        Pass audio chunk directly to transcription service (no buffering here).
        Buffering is handled in enhanced_transcription_service.py
        """
        if session_id not in self.active_streams:
            logger.warning(f"[{session_id}] ❌ TECHNICIAN: Received audio for inactive session")
            return

        stream = self.active_streams[session_id]

        if 'technician' not in stream:
            logger.warning(f"[{session_id}] ❌ TECHNICIAN: Stream not initialized in active_streams")
            return

        tech_stream = stream['technician']

        # Write to WAV file for recording (every chunk)
        wav_file = tech_stream.get('wav_file')
        if wav_file:
            try:
                wav_file.writeframes(audio_data)
            except Exception as wav_error:
                logger.error(f"[{session_id}] Error writing to WAV file: {wav_error}")

        # Pass directly to transcription service - it handles buffering
        try:
            from app.services.enhanced_transcription_service import get_enhanced_transcription_service
            transcription_service = get_enhanced_transcription_service()

            timestamp = (datetime.utcnow() - tech_stream['started_at']).total_seconds()

            # Log that we're sending to transcription service (reduced frequency)
            if not hasattr(self, '_tech_chunk_count'):
                self._tech_chunk_count = {}
            self._tech_chunk_count[session_id] = self._tech_chunk_count.get(session_id, 0) + 1
            if self._tech_chunk_count[session_id] % 50 == 1:
                logger.info(f"[{session_id}] 📞 TECHNICIAN: Sending chunk #{self._tech_chunk_count[session_id]} to transcription service ({len(audio_data)} bytes)")

            result = await transcription_service.process_audio_stream(
                session_id=session_id,
                audio_chunk=audio_data,
                timestamp=timestamp,
                speaker='technician',
                sample_rate=8000  # 8kHz for Twilio audio
            )

            if result and result.get('text', '').strip():
                text = result['text'].strip()
                logger.info(f"[{session_id}] ✅ TECHNICIAN Transcription: '{text}'")

                # Send to WebSocket
                self._send_transcription_to_websockets(session_id, result)

        except Exception as e:
            logger.error(f"[{session_id}] ❌ TECHNICIAN Transcription error: {e}", exc_info=True)

    def _send_transcription_to_websockets(self, session_id: str, result: dict):
        """Send transcription result to connected WebSockets"""
        text = result.get('text', '').strip()
        if not text:
            return

        # Determine speaker role and label
        speaker_role = result.get('speaker_role', '').strip()

        # Ensure speaker_role is valid, default to 'technician' if not
        if speaker_role not in ['agent', 'technician']:
            logger.warning(f"[{session_id}] ⚠️ Invalid speaker_role: '{speaker_role}', defaulting to 'technician'")
            speaker_role = 'technician'

        # Set label based on role
        if speaker_role == 'agent':
            default_label = 'Agent'
        else:
            default_label = 'Technicien'

        # Get speaker label from result, ensure it's not empty
        speaker_label = result.get('speaker_name', '').strip()
        if not speaker_label:
            speaker_label = default_label
            logger.warning(f"[{session_id}] ⚠️ speaker_name was empty, using default: '{speaker_label}'")

        logger.info(f"[{session_id}] 📤 Preparing transcription message: speaker_role='{speaker_role}', speaker_label='{speaker_label}'")

        transcription_message = json.dumps({
            'type': 'transcription',
            'text': text,
            'speaker_label': speaker_label,
            'speaker_role': speaker_role,
            'timestamp': result.get('timestamp'),
            'confidence': result.get('confidence', 0.0),
            'pause_duration_ms': result.get('pause_duration_ms', 0.0)
        })

        # Debug: Log active streams state with full details
        stream_state = self.active_streams.get(session_id, {})
        tech_state = stream_state.get('technician', {})
        agent_state = stream_state.get('agent', {})

        # Debug: Log all keys in the stream state
        logger.info(f"[{session_id}] 🔍 DEBUG active_streams keys: {list(stream_state.keys())}")
        logger.info(f"[{session_id}] 🔍 DEBUG technician keys: {list(tech_state.keys()) if tech_state else 'EMPTY'}")
        logger.info(f"[{session_id}] 🔍 DEBUG agent keys: {list(agent_state.keys()) if agent_state else 'EMPTY'}")

        has_tech_ws = 'transcription_ws' in tech_state and tech_state['transcription_ws'] is not None
        has_agent_ws = 'websocket' in agent_state and agent_state['websocket'] is not None
        logger.info(f"[{session_id}] 📡 WebSocket state: tech_ws={has_tech_ws}, agent_ws={has_agent_ws}, speaker={speaker_role}")

        # Send transcription to the appropriate WebSocket based on speaker
        # Technician speech → technician transcription WebSocket ONLY
        # Agent speech → agent audio WebSocket ONLY
        # This prevents duplicate transcriptions on the frontend

        sent_to_tech = False
        sent_to_agent = False

        if speaker_role == 'technician':
            # Send technician speech to technician transcription WebSocket ONLY
            if has_tech_ws:
                try:
                    self.active_streams[session_id]['technician']['transcription_ws'].send(transcription_message)
                    sent_to_tech = True
                    logger.info(f"[{session_id}] 📤 Sent TECHNICIAN transcription to tech UI: '{text[:50]}...'")
                except Exception as e:
                    logger.error(f"[{session_id}] Error sending to technician WebSocket: {e}")
            else:
                logger.warning(f"[{session_id}] ⚠️ No technician transcription WebSocket available for technician speech!")

        elif speaker_role == 'agent':
            # Send agent speech to agent audio WebSocket ONLY
            if has_agent_ws:
                try:
                    self.active_streams[session_id]['agent']['websocket'].send(transcription_message)
                    sent_to_agent = True
                    logger.info(f"[{session_id}] 📤 Sent AGENT transcription to agent UI: '{text[:50]}...'")
                except Exception as e:
                    logger.error(f"[{session_id}] Error sending to agent WebSocket: {e}")
            else:
                logger.warning(f"[{session_id}] ⚠️ No agent WebSocket available for agent speech!")
        else:
            logger.error(f"[{session_id}] ❌ INVALID speaker_role: '{speaker_role}' - must be 'technician' or 'agent'")

        # Safety check: Ensure message was sent to EXACTLY ONE WebSocket
        total_sends = (1 if sent_to_tech else 0) + (1 if sent_to_agent else 0)
        if total_sends == 0:
            logger.warning(f"[{session_id}] ⚠️ Transcription NOT sent to any WebSocket (speaker={speaker_role})")
        elif total_sends > 1:
            logger.error(f"[{session_id}] ❌ DUPLICATE SEND! Transcription sent to {total_sends} WebSockets (tech={sent_to_tech}, agent={sent_to_agent})")
        else:
            logger.info(f"[{session_id}] ✅ Routing verification: Sent to {'tech' if sent_to_tech else 'agent'} WS only")

    async def _process_agent_audio(self, session_id: str, audio_data: bytes):
        """
        Process incoming agent audio from browser (WebRTC MediaStream).
        Pass chunks directly to transcription service - buffering happens there.
        """
        # Initialize session if not exists (agent stream might start before Twilio stream)
        if session_id not in self.active_streams:
            logger.info(f"[{session_id}] 🆕 Creating active_streams entry for agent (Twilio stream not yet connected)")
            self.active_streams[session_id] = {}

        if 'agent' not in self.active_streams[session_id]:
            logger.info(f"[{session_id}] 🆕 Initializing agent stream tracking")
            self.active_streams[session_id]['agent'] = {
                'started_at': datetime.utcnow(),
                'audio_buffer': [],
                'websocket': None  # Will be set by WebSocket handler
            }

        # Calculate audio level (RMS) for logging
        import struct
        try:
            samples = struct.unpack(f'{len(audio_data)//2}h', audio_data)
            import numpy as np
            audio_level = np.sqrt(np.mean(np.square(samples))) if len(samples) > 0 else 0
            max_amplitude = max(abs(s) for s in samples) if len(samples) > 0 else 0
            logger.info(f"[{session_id}] 🎤 Agent chunk: {len(audio_data)} bytes, RMS={audio_level:.1f}, Max={max_amplitude}")
        except Exception as e:
            logger.warning(f"[{session_id}] Could not calculate audio level: {e}")

        # Pass directly to transcription service - it handles buffering
        try:
            from app.services.enhanced_transcription_service import get_enhanced_transcription_service
            transcription_service = get_enhanced_transcription_service()

            timestamp = (datetime.utcnow() - self.active_streams[session_id]['agent']['started_at']).total_seconds()

            logger.info(f"[{session_id}] 🎤 Calling process_audio_stream with speaker='agent'...")
            result = await transcription_service.process_audio_stream(
                session_id=session_id,
                audio_chunk=audio_data,
                timestamp=timestamp,
                speaker='agent',
                sample_rate=16000  # 16kHz for browser audio
            )

            if result and result.get('text', '').strip():
                text = result['text'].strip()
                logger.info(f"[{session_id}] ✅ Agent transcription SUCCESS: '{text[:100]}'")

                # Send to all connected WebSockets (agent + technician UI)
                self._send_transcription_to_websockets(session_id, result)

        except Exception as e:
            logger.error(f"[{session_id}] ❌ Agent audio processing error: {e}", exc_info=True)

        return audio_data

    async def send_audio_to_stream(self, session_id: str, audio_data: bytes):
        """
        Send audio back to Twilio stream (AI speaking)
        """
        if session_id not in self.active_streams:
            logger.warning(f"[{session_id}] No active stream for sending audio")
            return

        stream_info = self.active_streams[session_id]
        websocket = stream_info['websocket']
        stream_sid = stream_info['stream_sid']

        if not stream_sid:
            logger.warning(f"[{session_id}] Stream not yet started")
            return

        try:
            audio_8k = audioop.ratecv(
                audio_data,
                2,
                self.TWILIO_CHANNELS,
                self.WHISPER_SAMPLE_RATE,
                self.TWILIO_SAMPLE_RATE,
                None
            )[0]
            mulaw_audio = audioop.lin2ulaw(audio_8k, 2)
            payload = base64.b64encode(mulaw_audio).decode('utf-8')

            message = {
                'event': 'media',
                'streamSid': stream_sid,
                'media': {'payload': payload}
            }

            await websocket.send(json.dumps(message))
            logger.debug(f"[{session_id}] Sent {len(audio_8k)} bytes of audio to Twilio stream {stream_sid}")

        except Exception as e:
            logger.error(f"[{session_id}] Failed to send audio: {e}", exc_info=True)
                
    def end_call(self, call_sid: str) -> Dict[str, Any]:
        """
        End an active call

        Args:
            call_sid: Twilio call SID

        Returns:
            Call status information
        """
        try:
            call = self.client.calls(call_sid).update(status='completed')

            logger.info(f"Call ended: {call_sid}")

            return {
                'call_sid': call_sid,
                'status': call.status,
                'duration': call.duration
            }

        except Exception as e:
            logger.error(f"Failed to end call {call_sid}: {e}")
            raise

    def get_call_status(self, call_sid: str) -> Dict[str, Any]:
        """
        Get current status of a call

        Args:
            call_sid: Twilio call SID

        Returns:
            Call status information
        """
        try:
            call = self.client.calls(call_sid).fetch()

            from_number = getattr(call, 'from_formatted', None) or getattr(call, 'from_', None) or call.from_
            to_number = getattr(call, 'to_formatted', None) or getattr(call, 'to_', None) or call.to

            return {
                'call_sid': call.sid,
                'status': call.status,
                'direction': call.direction,
                'duration': int(call.duration) if call.duration else 0,
                'from_number': from_number,
                'to_number': to_number
            }

        except Exception as e:
            logger.error(f"Failed to fetch call status for {call_sid}: {e}")
            raise


# Singleton instance
_twilio_service: Optional[TwilioAudioService] = None


def get_twilio_service() -> TwilioAudioService:
    """Get or create Twilio audio service instance"""
    global _twilio_service

    if _twilio_service is None:
        from app.config.twilio_config import get_twilio_settings

        settings = get_twilio_settings()
        _twilio_service = TwilioAudioService(
            account_sid=settings.account_sid,
            auth_token=settings.auth_token,
            phone_number=settings.phone_number
        )

    return _twilio_service
