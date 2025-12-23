"""
Real-time Transcription Service
Processes incoming transcription streams and triggers agent pipeline
"""
import asyncio
from typing import Dict, Any, Optional, Callable
from datetime import datetime
import logging

from app.services.call_session_manager import CallSessionManager
from app.agents.agent_orchestrator import AgentOrchestrator


logger = logging.getLogger(__name__)


class RealtimeTranscriptionService:
    """
    Handles real-time transcription processing and suggestion generation

    Flow:
    1. Receive transcription segment from ACD
    2. Store in database
    3. Trigger agent pipeline
    4. Emit suggestions to UI via callback
    """

    def __init__(
        self,
        session_manager: CallSessionManager,
        orchestrator: AgentOrchestrator,
        on_suggestions_ready: Optional[Callable] = None,
    ):
        self.session_manager = session_manager
        self.orchestrator = orchestrator
        self.on_suggestions_ready = on_suggestions_ready  # Callback for UI updates

        # Track processing state
        self._processing_locks: Dict[str, asyncio.Lock] = {}
        self._last_processing_time: Dict[str, float] = {}

        # Configuration
        self.min_processing_interval = 2.0  # Min seconds between processing for same session
        self.process_only_customer = True  # Only process customer speech by default

    async def process_transcription_segment(
        self,
        session_id: str,
        speaker: str,
        text: str,
        start_time: float,
        end_time: float,
        confidence: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process a new transcription segment

        Args:
            session_id: Call session identifier
            speaker: 'customer' or 'agent'
            text: Transcribed text
            start_time: Segment start time (seconds from call start)
            end_time: Segment end time
            confidence: Transcription confidence
            metadata: Additional metadata
            language: Language code (e.g., 'en', 'fr', 'es')

        Returns:
            Processing result with suggestions and status
        """
        try:
            # Store transcription in database
            segment = self.session_manager.add_transcription(
                session_id=session_id,
                speaker=speaker,
                text=text,
                start_time=start_time,
                end_time=end_time,
                confidence=confidence,
            )

            logger.info(f"Stored transcription for session {session_id}: {speaker} - {text[:50]}...")

            # Decide whether to process
            should_process = self._should_process(session_id, speaker, text)

            if not should_process:
                return {
                    "status": "skipped",
                    "reason": "Processing throttled or not customer speech",
                    "segment_id": segment.id,
                }

            # Get or create lock for this session
            if session_id not in self._processing_locks:
                self._processing_locks[session_id] = asyncio.Lock()

            # Process with agent pipeline (non-blocking)
            async with self._processing_locks[session_id]:
                result = await self._process_with_agents(session_id, text, speaker, language=language)

                # Update last processing time
                self._last_processing_time[session_id] = datetime.utcnow().timestamp()

                # Emit suggestions to UI if callback is set
                if self.on_suggestions_ready and result.get("suggestions"):
                    await self._emit_suggestions(session_id, result)

                return {
                    "status": "processed",
                    "segment_id": segment.id,
                    "suggestions_count": len(result.get("suggestions", [])),
                    "questions_count": len(result.get("clarifying_questions", [])),
                    "processing_time_ms": result.get("total_time_ms", 0),
                }

        except Exception as e:
            logger.error(f"Error processing transcription for session {session_id}: {e}")
            return {
                "status": "error",
                "error": str(e),
            }

    async def _process_with_agents(
        self,
        session_id: str,
        transcription: str,
        speaker: str,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run the agent orchestration pipeline"""
        logger.info(f"Processing with agents: session={session_id}, speaker={speaker}, language={language}")

        result = await self.orchestrator.process_transcription_update(
            session_id=session_id,
            new_transcription=transcription,
            speaker=speaker,
            language=language,
        )

        logger.info(
            f"Agent processing complete: {len(result.get('suggestions', []))} suggestions, "
            f"{len(result.get('clarifying_questions', []))} questions"
        )

        return result

    async def _emit_suggestions(self, session_id: str, result: Dict[str, Any]) -> None:
        """Emit suggestions to UI via callback"""
        if not self.on_suggestions_ready:
            return

        try:
            payload = {
                "session_id": session_id,
                "suggestions": result.get("suggestions", []),
                "clarifying_questions": result.get("clarifying_questions", []),
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Call the callback (could be WebSocket send, SSE send, etc.)
            await self.on_suggestions_ready(payload)

            logger.info(f"Emitted {len(payload['suggestions'])} suggestions to UI for session {session_id}")

        except Exception as e:
            logger.error(f"Error emitting suggestions: {e}")

    def _should_process(self, session_id: str, speaker: str, text: str) -> bool:
        """
        Decide whether to process this transcription segment

        Criteria:
        1. Speaker is customer (if process_only_customer is True)
        2. Enough time has passed since last processing (throttling)
        3. Text is not empty or too short
        """
        # Check speaker
        if self.process_only_customer and speaker != "customer":
            return False

        # Check text length
        if not text or len(text.strip()) < 5:
            return False

        # Check throttling
        last_time = self._last_processing_time.get(session_id, 0)
        current_time = datetime.utcnow().timestamp()

        if (current_time - last_time) < self.min_processing_interval:
            logger.debug(f"Throttling processing for session {session_id}")
            return False

        return True

    async def handle_call_start(
        self,
        call_id: str,
        agent_id: str,
        agent_name: Optional[str] = None,
        customer_id: Optional[str] = None,
        customer_phone: Optional[str] = None,
        customer_name: Optional[str] = None,
        acd_metadata: Optional[Dict[str, Any]] = None,
        crm_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Handle call start event from ACD

        Args:
            call_id: External ACD call ID
            agent_id: Support agent ID
            agent_name: Support agent name
            customer_id: Customer ID from CRM
            customer_phone: Customer phone number
            customer_name: Customer name
            acd_metadata: ACD system metadata
            crm_metadata: CRM system metadata

        Returns:
            Session info
        """
        try:
            session = self.session_manager.create_session(
                call_id=call_id,
                agent_id=agent_id,
                agent_name=agent_name,
                customer_id=customer_id,
                customer_phone=customer_phone,
                customer_name=customer_name,
                acd_metadata=acd_metadata,
                crm_metadata=crm_metadata,
            )

            logger.info(f"Created call session: {session.session_id} for call {call_id}")

            return {
                "status": "success",
                "session_id": session.session_id,
                "call_id": call_id,
            }

        except Exception as e:
            logger.error(f"Error creating call session: {e}")
            return {
                "status": "error",
                "error": str(e),
            }

    async def handle_call_end(
        self,
        session_id: str,
        status: str = "completed",
    ) -> Dict[str, Any]:
        """
        Handle call end event

        Args:
            session_id: Session identifier
            status: End status (completed/transferred/dropped)

        Returns:
            End status
        """
        try:
            self.session_manager.end_session(session_id, status)

            # Clean up locks
            if session_id in self._processing_locks:
                del self._processing_locks[session_id]
            if session_id in self._last_processing_time:
                del self._last_processing_time[session_id]

            logger.info(f"Ended call session: {session_id} with status {status}")

            return {
                "status": "success",
                "session_id": session_id,
            }

        except Exception as e:
            logger.error(f"Error ending call session: {e}")
            return {
                "status": "error",
                "error": str(e),
            }

    async def get_session_suggestions(self, session_id: str, limit: int = 10) -> Dict[str, Any]:
        """
        Get all suggestions and transcriptions for a session

        Args:
            session_id: Session identifier
            limit: Max number of suggestions to return

        Returns:
            Dict with suggestions list and transcriptions list
        """
        try:
            from app.models.call_session import CallSession, Suggestion, TranscriptionSegment
            from app.database.postgresql_session import get_db_session

            with get_db_session() as db:
                session = db.query(CallSession).filter(
                    CallSession.session_id == session_id
                ).first()

                if not session:
                    return {"status": "error", "error": "Session not found"}

                # Get suggestions
                suggestions = (
                    db.query(Suggestion)
                    .filter(Suggestion.session_id == session.id)
                    .order_by(Suggestion.created_at.desc())
                    .limit(limit)
                    .all()
                )

                # Get transcriptions
                transcriptions = (
                    db.query(TranscriptionSegment)
                    .filter(TranscriptionSegment.session_id == session.id)
                    .order_by(TranscriptionSegment.start_time.desc())
                    .limit(limit * 2)  # Get more transcriptions than suggestions
                    .all()
                )

                return {
                    "status": "success",
                    "suggestions": [
                        {
                            "id": s.id,
                            "type": s.suggestion_type,
                            "title": s.title,
                            "content": s.content,
                            "confidence": s.confidence_score,
                            "shown": s.shown_to_agent,
                            "clicked": s.agent_clicked,
                        }
                        for s in suggestions
                    ],
                    "transcriptions": [
                        {
                            "id": t.id,
                            "text": t.text,
                            "speaker": t.speaker,
                            "speaker_label": "Technicien" if t.speaker == "technician" else "Agent",
                            "start_time": t.start_time,
                            "end_time": t.end_time,
                            "confidence": t.confidence,  # TranscriptionSegment uses 'confidence', not 'confidence_score'
                            "timestamp": t.timestamp.isoformat() if t.timestamp else None,
                        }
                        for t in transcriptions
                    ],
                }

        except Exception as e:
            logger.error(f"Error getting suggestions: {e}")
            return {"status": "error", "error": str(e)}


# Singleton instance
_transcription_service = None


def get_transcription_service(
    session_manager: Optional[CallSessionManager] = None,
    orchestrator: Optional[AgentOrchestrator] = None,
    on_suggestions_ready: Optional[Callable] = None,
) -> RealtimeTranscriptionService:
    """Get or create singleton transcription service"""
    global _transcription_service

    if _transcription_service is None and session_manager and orchestrator:
        _transcription_service = RealtimeTranscriptionService(
            session_manager=session_manager,
            orchestrator=orchestrator,
            on_suggestions_ready=on_suggestions_ready,
        )

    return _transcription_service
