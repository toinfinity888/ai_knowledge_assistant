"""
Call Session Manager
Manages active call sessions, transcriptions, and conversation state
"""
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List

from app.models.call_session import (
    CallSession,
    TranscriptionSegment,
    AgentAction,
    Suggestion,
    CallStatus
)
from app.database.postgresql_session import get_db_session


class CallSessionManager:
    """
    Manages call sessions lifecycle and provides interface for other components
    """

    def __init__(self):
        self._active_sessions: Dict[str, CallSession] = {}  # In-memory cache for quick access

    def create_session(
        self,
        call_id: str,
        agent_id: str,
        agent_name: Optional[str] = None,
        customer_id: Optional[str] = None,
        customer_phone: Optional[str] = None,
        customer_name: Optional[str] = None,
        acd_metadata: Optional[Dict[str, Any]] = None,
        crm_metadata: Optional[Dict[str, Any]] = None,
    ) -> CallSession:
        """
        Create a new call session when a call starts

        Args:
            call_id: External ACD system call identifier
            agent_id: Support agent identifier
            agent_name: Support agent name
            customer_id: CRM customer identifier
            customer_phone: Customer phone number
            customer_name: Customer name from CRM
            acd_metadata: Additional ACD system data
            crm_metadata: Additional CRM system data

        Returns:
            Created CallSession object
        """
        # Use call_id as session_id to maintain consistency across all components
        # The frontend generates session_id and passes it as call_id
        # We want to use the same ID everywhere for proper lookup
        session_id = call_id

        session = CallSession(
            call_id=call_id,
            session_id=session_id,
            agent_id=agent_id,
            agent_name=agent_name,
            customer_id=customer_id,
            customer_phone=customer_phone,
            customer_name=customer_name,
            status=CallStatus.ACTIVE,
            acd_metadata=acd_metadata or {},
            crm_metadata=crm_metadata or {},
            start_time=datetime.utcnow(),
        )

        with get_db_session() as db:
            db.add(session)
            db.commit()
            db.refresh(session)

        # Cache in memory
        self._active_sessions[session_id] = session

        return session

    def get_session(self, session_id: str) -> Optional[CallSession]:
        """Get session by session_id (checks cache first, then DB)"""
        # Try cache first
        if session_id in self._active_sessions:
            return self._active_sessions[session_id]

        # Query database
        with get_db_session() as db:
            session = db.query(CallSession).filter(
                CallSession.session_id == session_id
            ).first()
            if session and session.status == CallStatus.ACTIVE:
                self._active_sessions[session_id] = session
            return session

    def get_session_by_call_id(self, call_id: str) -> Optional[CallSession]:
        """Get session by external call_id"""
        with get_db_session() as db:
            session = db.query(CallSession).filter(
                CallSession.call_id == call_id
            ).first()
            return session

    def add_transcription(
        self,
        session_id: str,
        speaker: str,
        text: str,
        start_time: float,
        end_time: float,
        confidence: Optional[float] = None,
        sentiment: Optional[str] = None,
        detected_keywords: Optional[List[str]] = None,
    ) -> TranscriptionSegment:
        """
        Add a new transcription segment to the session

        Args:
            session_id: Session identifier
            speaker: 'customer' or 'agent'
            text: Transcribed text
            start_time: Segment start time in seconds from call start
            end_time: Segment end time in seconds from call start
            confidence: Transcription confidence score
            sentiment: Detected sentiment (positive/neutral/negative)
            detected_keywords: List of important keywords

        Returns:
            Created TranscriptionSegment
        """
        with get_db_session() as db:
            session = db.query(CallSession).filter(
                CallSession.session_id == session_id
            ).first()

            if not session:
                raise ValueError(f"Session {session_id} not found")

            segment = TranscriptionSegment(
                session_id=session.id,
                speaker=speaker,
                text=text,
                start_time=start_time,
                end_time=end_time,
                confidence=confidence,
                sentiment=sentiment,
                detected_keywords=detected_keywords or [],
                timestamp=datetime.utcnow(),
            )

            db.add(segment)
            db.commit()
            db.refresh(segment)

            return segment

    def log_agent_action(
        self,
        session_id: str,
        agent_name: str,
        action_type: str,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        status: str,
        confidence: Optional[float] = None,
        message: Optional[str] = None,
        processing_time_ms: Optional[int] = None,
    ) -> AgentAction:
        """
        Log an AI agent action for debugging and analytics

        Args:
            session_id: Session identifier
            agent_name: Name of the agent (e.g., 'context_agent')
            action_type: Type of action performed
            input_data: Agent input context
            output_data: Agent output/response
            status: Action status (success/error/etc)
            confidence: Confidence score
            message: Additional message
            processing_time_ms: Processing time in milliseconds

        Returns:
            Created AgentAction record
        """
        with get_db_session() as db:
            session = db.query(CallSession).filter(
                CallSession.session_id == session_id
            ).first()

            if not session:
                raise ValueError(f"Session {session_id} not found")

            action = AgentAction(
                session_id=session.id,
                agent_name=agent_name,
                action_type=action_type,
                input_data=input_data,
                output_data=output_data,
                status=status,
                confidence=confidence,
                message=message,
                processing_time_ms=processing_time_ms,
                timestamp=datetime.utcnow(),
            )

            db.add(action)
            db.commit()
            db.refresh(action)

            return action

    def add_suggestion(
        self,
        session_id: str,
        suggestion_type: str,
        title: str,
        content: str,
        source_chunks: Optional[List[Dict[str, Any]]] = None,
        query_used: Optional[str] = None,
        confidence_score: Optional[float] = None,
        relevance_score: Optional[float] = None,
    ) -> Suggestion:
        """
        Add a suggestion to be displayed to the support agent

        Args:
            session_id: Session identifier
            suggestion_type: Type of suggestion (knowledge_base/solution/clarification_question)
            title: Suggestion title
            content: Suggestion content
            source_chunks: Knowledge base chunks used
            query_used: Query that generated this suggestion
            confidence_score: AI confidence
            relevance_score: Relevance to current context

        Returns:
            Created Suggestion
        """
        with get_db_session() as db:
            session = db.query(CallSession).filter(
                CallSession.session_id == session_id
            ).first()

            if not session:
                raise ValueError(f"Session {session_id} not found")

            suggestion = Suggestion(
                session_id=session.id,
                suggestion_type=suggestion_type,
                title=title,
                content=content,
                source_chunks=source_chunks or [],
                query_used=query_used,
                confidence_score=confidence_score,
                relevance_score=relevance_score,
                shown_to_agent=False,
                created_at=datetime.utcnow(),
            )

            db.add(suggestion)
            db.commit()
            db.refresh(suggestion)

            return suggestion

    def mark_suggestion_shown(self, suggestion_id: int) -> None:
        """Mark a suggestion as shown to the agent"""
        with get_db_session() as db:
            suggestion = db.query(Suggestion).filter(Suggestion.id == suggestion_id).first()
            if suggestion:
                suggestion.shown_to_agent = True
                suggestion.shown_at = datetime.utcnow()
                db.commit()

    def mark_suggestion_clicked(self, suggestion_id: int) -> None:
        """Mark a suggestion as clicked/expanded by the agent"""
        with get_db_session() as db:
            suggestion = db.query(Suggestion).filter(Suggestion.id == suggestion_id).first()
            if suggestion:
                suggestion.agent_clicked = True
                suggestion.clicked_at = datetime.utcnow()
                db.commit()

    def record_suggestion_feedback(self, suggestion_id: int, feedback: str) -> None:
        """Record agent feedback on suggestion"""
        with get_db_session() as db:
            suggestion = db.query(Suggestion).filter(Suggestion.id == suggestion_id).first()
            if suggestion:
                suggestion.agent_feedback = feedback
                db.commit()

    def get_conversation_context(self, session_id: str, last_n_segments: int = 10) -> str:
        """
        Get recent conversation context as text

        Args:
            session_id: Session identifier
            last_n_segments: Number of recent segments to include

        Returns:
            Formatted conversation text
        """
        with get_db_session() as db:
            session = db.query(CallSession).filter(
                CallSession.session_id == session_id
            ).first()

            if not session:
                return ""

            segments = (
                db.query(TranscriptionSegment)
                .filter(TranscriptionSegment.session_id == session.id)
                .order_by(TranscriptionSegment.timestamp.desc())
                .limit(last_n_segments)
                .all()
            )

            # Reverse to chronological order
            segments = list(reversed(segments))

            context_lines = []
            for seg in segments:
                speaker_label = "Technicien" if seg.speaker == "technician" else "Agent"
                context_lines.append(f"{speaker_label}: {seg.text}")

            return "\n".join(context_lines)

    def update_session_metadata(
        self,
        session_id: str,
        detected_intent: Optional[str] = None,
        detected_entities: Optional[List[str]] = None,
        sentiment_score: Optional[float] = None,
        conversation_summary: Optional[str] = None,
    ) -> None:
        """Update session metadata (intent, entities, sentiment)"""
        with get_db_session() as db:
            session = db.query(CallSession).filter(
                CallSession.session_id == session_id
            ).first()

            if not session:
                return

            if detected_intent is not None:
                session.detected_intent = detected_intent
            if detected_entities is not None:
                session.detected_entities = detected_entities
            if sentiment_score is not None:
                session.sentiment_score = sentiment_score
            if conversation_summary is not None:
                session.conversation_summary = conversation_summary

            db.commit()

    def end_session(self, session_id: str, status: str = CallStatus.COMPLETED) -> None:
        """
        End a call session

        Args:
            session_id: Session identifier
            status: Final status (completed/transferred/dropped)
        """
        with get_db_session() as db:
            session = db.query(CallSession).filter(
                CallSession.session_id == session_id
            ).first()

            if not session:
                return

            session.status = status
            session.end_time = datetime.utcnow()
            session.duration_seconds = int(
                (session.end_time - session.start_time).total_seconds()
            )

            db.commit()

        # Remove from active sessions cache
        if session_id in self._active_sessions:
            del self._active_sessions[session_id]

    def get_active_sessions(self) -> List[CallSession]:
        """Get all currently active call sessions"""
        with get_db_session() as db:
            sessions = db.query(CallSession).filter(
                CallSession.status == CallStatus.ACTIVE
            ).all()
            return sessions


# Singleton instance
_session_manager = None


def get_call_session_manager() -> CallSessionManager:
    """Get singleton instance of CallSessionManager"""
    global _session_manager
    if _session_manager is None:
        _session_manager = CallSessionManager()
    return _session_manager
