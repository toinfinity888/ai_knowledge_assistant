"""
Microphone-based Demo for Real-time Support Assistant
Captures audio from microphone, transcribes it, and displays AI suggestions
"""
import asyncio
import queue
import threading
import time
from datetime import datetime
import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel
import tempfile
import os
from scipy.io.wavfile import write as write_wav

from app.services.call_session_manager import get_call_session_manager
from app.services.realtime_transcription_service import get_transcription_service
from app.init_realtime_system import initialize_realtime_system


class MicrophoneDemo:
    """
    Real-time microphone demo for support assistant MVP
    """

    def __init__(
        self,
        whisper_model: str = "small",
        sample_rate: int = 16000,
        segment_duration: float = 3.0,
        device: str = "cpu"
    ):
        """
        Initialize microphone demo

        Args:
            whisper_model: Whisper model size (tiny/base/small/medium/large)
            sample_rate: Audio sample rate
            segment_duration: Seconds of audio per transcription
            device: Whisper device (cpu/cuda/mps)
        """
        self.sample_rate = sample_rate
        self.segment_duration = segment_duration
        self.audio_queue = queue.Queue()
        self.is_recording = False
        self.current_session_id = None
        self.call_start_time = None

        # Initialize Whisper model
        print(f"Loading Whisper model '{whisper_model}'...")
        self.whisper_model = WhisperModel(whisper_model, device=device)
        print("✓ Whisper model loaded")

        # Initialize real-time system
        print("\nInitializing real-time support assistant...")
        self.components = initialize_realtime_system()
        self.transcription_service = self.components["transcription_service"]
        self.session_manager = self.components["session_manager"]
        print("✓ System ready")

    def audio_callback(self, indata, frames, time_info, status):
        """Callback for audio recording"""
        if status:
            print(f"Audio status: {status}")
        if self.is_recording:
            self.audio_queue.put(indata.copy())

    def save_audio_segment(self, audio_data):
        """Save audio segment to temporary file"""
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")

        # Normalize to int16
        if audio_data.dtype == np.float32 or audio_data.dtype == np.float64:
            audio_int16 = np.int16(audio_data / np.max(np.abs(audio_data)) * 32767)
        else:
            audio_int16 = audio_data

        write_wav(tmp_file.name, self.sample_rate, audio_int16)
        return tmp_file.name

    def transcribe_segment(self, wav_path):
        """Transcribe audio segment using Whisper"""
        try:
            segments, info = self.whisper_model.transcribe(
                wav_path,
                beam_size=1,
                vad_filter=True,
                language="fr"  # Change to "fr" for French, "ru" for Russian, etc.
            )

            text = " ".join([s.text.strip() for s in segments if s.text.strip()])
            return text

        except Exception as e:
            print(f"❌ Transcription error: {e}")
            return ""

        finally:
            if os.path.exists(wav_path):
                os.remove(wav_path)

    async def process_audio_loop(self):
        """Background loop to process audio segments"""
        print("\n🎤 Audio processing started...")

        while self.is_recording:
            try:
                # Collect audio for segment_duration seconds
                segment = []
                target_frames = int(self.segment_duration * self.sample_rate)

                while len(segment) < target_frames and self.is_recording:
                    try:
                        data = self.audio_queue.get(timeout=0.1)
                        segment.append(data)
                    except queue.Empty:
                        continue

                if not segment:
                    continue

                # Concatenate audio data
                audio_data = np.concatenate(segment, axis=0)

                # Save to temp file
                wav_path = self.save_audio_segment(audio_data)

                # Transcribe
                text = self.transcribe_segment(wav_path)

                if text:
                    # Calculate timing
                    elapsed_time = time.time() - self.call_start_time
                    start_time = elapsed_time - self.segment_duration
                    end_time = elapsed_time

                    print(f"\n📝 Transcribed: '{text}'")

                    # Send to real-time service
                    result = await self.transcription_service.process_transcription_segment(
                        session_id=self.current_session_id,
                        speaker="customer",  # Assume customer for demo
                        text=text,
                        start_time=start_time,
                        end_time=end_time,
                        confidence=0.9,
                    )

                    # Display results
                    if result["status"] == "processed":
                        print(f"  ✓ Processing: {result['status']}")
                        if result.get('suggestions_count', 0) > 0:
                            print(f"  💡 Generated {result['suggestions_count']} suggestions")
                        if result.get('questions_count', 0) > 0:
                            print(f"  ❓ Generated {result['questions_count']} clarifying questions")

                    # Get and display suggestions
                    suggestions_result = await self.transcription_service.get_session_suggestions(
                        self.current_session_id,
                        limit=5
                    )

                    if suggestions_result.get("suggestions"):
                        self.display_suggestions(suggestions_result["suggestions"])

            except Exception as e:
                print(f"❌ Error in audio processing: {e}")
                import traceback
                traceback.print_exc()

    def display_suggestions(self, suggestions):
        """Display suggestions to console (in real UI, this would update the screen)"""
        print("\n" + "="*80)
        print("💡 SUGGESTIONS FOR SUPPORT AGENT")
        print("="*80)

        for i, suggestion in enumerate(suggestions[:3], 1):  # Show top 3
            print(f"\n[{i}] {suggestion['type'].upper()}")
            print(f"Title: {suggestion['title']}")
            print(f"Content: {suggestion['content'][:200]}...")
            if suggestion.get('confidence'):
                print(f"Confidence: {suggestion['confidence']:.2f}")

        print("="*80 + "\n")

    async def start_call(
        self,
        customer_name: str = "Demo Customer",
        customer_phone: str = "+1234567890",
        agent_name: str = "Demo Agent"
    ):
        """Start a demo call session"""
        print("\n" + "="*80)
        print("🚀 STARTING DEMO CALL SESSION")
        print("="*80)

        # Create call session
        call_id = f"demo-{int(time.time())}"

        result = await self.transcription_service.handle_call_start(
            call_id=call_id,
            agent_id="demo-agent-1",
            agent_name=agent_name,
            customer_id="demo-customer-1",
            customer_phone=customer_phone,
            customer_name=customer_name,
            acd_metadata={"type": "demo", "source": "microphone"},
            crm_metadata={"demo": True},
        )

        self.current_session_id = result["session_id"]
        self.call_start_time = time.time()

        print(f"\n✓ Call started")
        print(f"  Session ID: {self.current_session_id}")
        print(f"  Call ID: {call_id}")
        print(f"  Customer: {customer_name}")
        print(f"  Agent: {agent_name}")
        print("="*80 + "\n")

    async def end_call(self):
        """End the demo call session"""
        if self.current_session_id:
            print("\n" + "="*80)
            print("🛑 ENDING CALL SESSION")
            print("="*80)

            await self.transcription_service.handle_call_end(
                session_id=self.current_session_id,
                status="completed"
            )

            # Display call summary
            context = self.session_manager.get_conversation_context(
                self.current_session_id,
                last_n_segments=100
            )

            print("\n📋 CALL TRANSCRIPT:")
            print("-"*80)
            print(context)
            print("-"*80)

            print("\n✓ Call ended successfully")
            print("="*80 + "\n")

            self.current_session_id = None

    async def run_demo(self):
        """Run the complete demo"""
        print("\n" + "="*80)
        print("🎤 MICROPHONE DEMO - REAL-TIME SUPPORT ASSISTANT")
        print("="*80)
        print("\nThis demo will:")
        print("  1. Capture audio from your microphone")
        print("  2. Transcribe it in real-time using Whisper")
        print("  3. Analyze the conversation with AI agents")
        print("  4. Generate suggestions for the support agent")
        print("\nSpeak clearly into your microphone.")
        print("Describe a technical problem (e.g., 'I have error 401 when logging in')")
        print("\nPress Ctrl+C to stop the demo")
        print("="*80 + "\n")

        input("Press Enter to start the demo...")

        try:
            # Start call session
            await self.start_call()

            # Start recording
            self.is_recording = True

            # Start audio processing in background
            processing_task = asyncio.create_task(self.process_audio_loop())

            # Start audio stream
            with sd.InputStream(
                channels=1,
                samplerate=self.sample_rate,
                callback=self.audio_callback
            ):
                print("\n🎤 RECORDING... Speak now!")
                print("(Press Ctrl+C to stop)\n")

                # Keep running until interrupted
                await processing_task

        except KeyboardInterrupt:
            print("\n\n⏸️  Recording stopped by user")

        finally:
            self.is_recording = False

            # End call
            if self.current_session_id:
                await self.end_call()

            print("\n✅ Demo completed!")


def main():
    """Main entry point for microphone demo"""
    demo = MicrophoneDemo(
        whisper_model="base",  # Use "tiny" for faster, "small"/"medium" for better accuracy
        segment_duration=3.0,   # Transcribe every 3 seconds
    )

    # Run async demo
    asyncio.run(demo.run_demo())


if __name__ == "__main__":
    main()
