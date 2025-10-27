"""
Call Session Models for ACD/CRM Integration
Tracks ongoing customer support conversations and their state
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, JSON, Text, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship, declarative_base
from enum import Enum

Base = declarative_base()


class CallStatus(str, Enum):
    """Call session status"""
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    TRANSFERRED = "transferred"
    DROPPED = "dropped"


class CallSession(Base):
    """
    Represents an active or completed call session between customer and support agent
    """
    __tablename__ = 'call_sessions'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Call identifiers
    call_id = Column(String, unique=True, nullable=False, index=True)  # External ACD call ID
    session_id = Column(String, unique=True, nullable=False, index=True)  # Internal session ID

    # Participants
    customer_id = Column(String, nullable=True, index=True)  # CRM customer ID
    customer_phone = Column(String, nullable=True)
    customer_name = Column(String, nullable=True)
    agent_id = Column(String, nullable=False, index=True)  # Support agent ID
    agent_name = Column(String, nullable=True)

    # Call metadata
    status = Column(String, default=CallStatus.ACTIVE, nullable=False)
    start_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    end_time = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    # Integration data
    acd_metadata = Column(JSON, default=dict)  # ACD system specific data
    crm_metadata = Column(JSON, default=dict)  # CRM system specific data

    # Conversation context
    conversation_summary = Column(Text, nullable=True)  # AI-generated summary
    detected_intent = Column(String, nullable=True)  # Primary customer intent
    detected_entities = Column(JSON, default=list)  # Extracted entities (product names, issue types, etc.)
    sentiment_score = Column(Float, nullable=True)  # Overall sentiment (-1 to 1)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    transcriptions = relationship("TranscriptionSegment", back_populates="session", cascade="all, delete-orphan")
    agent_actions = relationship("AgentAction", back_populates="session", cascade="all, delete-orphan")
    suggestions = relationship("Suggestion", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<CallSession(call_id='{self.call_id}', status='{self.status}', agent='{self.agent_name}')>"


class TranscriptionSegment(Base):
    """
    Individual transcribed segments from the call
    Stores who spoke, what they said, and when
    """
    __tablename__ = 'transcription_segments'

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey('call_sessions.id'), nullable=False, index=True)

    # Segment data
    speaker = Column(String, nullable=False)  # 'customer' or 'agent'
    text = Column(Text, nullable=False)
    confidence = Column(Float, nullable=True)  # Transcription confidence (0-1)

    # Timing
    start_time = Column(Float, nullable=False)  # Seconds from call start
    end_time = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Analysis
    sentiment = Column(String, nullable=True)  # positive/neutral/negative
    detected_keywords = Column(JSON, default=list)  # Important keywords/phrases

    # Relationships
    session = relationship("CallSession", back_populates="transcriptions")

    def __repr__(self):
        return f"<TranscriptionSegment(speaker='{self.speaker}', text='{self.text[:50]}...')>"


class AgentAction(Base):
    """
    Logs all AI agent actions and decisions during the call
    Useful for debugging and improving agent performance
    """
    __tablename__ = 'agent_actions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey('call_sessions.id'), nullable=False, index=True)

    # Agent info
    agent_name = Column(String, nullable=False)  # context_agent, query_agent, clarification_agent
    action_type = Column(String, nullable=False)  # analyze, formulate_query, request_clarification

    # Input/Output
    input_data = Column(JSON, nullable=False)  # What the agent received
    output_data = Column(JSON, nullable=False)  # What the agent produced

    # Results
    status = Column(String, nullable=False)  # success, need_more_info, error, pending
    confidence = Column(Float, nullable=True)
    message = Column(Text, nullable=True)

    # Performance
    processing_time_ms = Column(Integer, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    session = relationship("CallSession", back_populates="agent_actions")

    def __repr__(self):
        return f"<AgentAction(agent='{self.agent_name}', action='{self.action_type}', status='{self.status}')>"


class Suggestion(Base):
    """
    AI-generated suggestions displayed to the support agent
    These are the final outputs shown on the agent's screen
    """
    __tablename__ = 'suggestions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey('call_sessions.id'), nullable=False, index=True)

    # Suggestion content
    suggestion_type = Column(String, nullable=False)  # knowledge_base, solution, clarification_question
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)

    # Source information
    source_chunks = Column(JSON, default=list)  # Referenced knowledge base chunks
    query_used = Column(Text, nullable=True)  # The query that generated this suggestion

    # Relevance
    confidence_score = Column(Float, nullable=True)  # How confident is the AI (0-1)
    relevance_score = Column(Float, nullable=True)  # How relevant to current context (0-1)

    # Agent interaction
    shown_to_agent = Column(Boolean, default=False)  # Was it displayed?
    agent_clicked = Column(Boolean, default=False)  # Did agent click/expand it?
    agent_feedback = Column(String, nullable=True)  # helpful/not_helpful/irrelevant

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    shown_at = Column(DateTime, nullable=True)
    clicked_at = Column(DateTime, nullable=True)

    # Relationships
    session = relationship("CallSession", back_populates="suggestions")

    def __repr__(self):
        return f"<Suggestion(type='{self.suggestion_type}', title='{self.title[:30]}...', score={self.confidence_score})>"
