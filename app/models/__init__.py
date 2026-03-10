"""
SQLAlchemy Models for AI Knowledge Assistant

This module exports all database models for the application.
All models share a common Base for consistent schema management.
"""

# Shared base - import this for metadata operations
from app.models.base import Base

# Multi-tenancy models
from app.models.company import Company
from app.models.user import User, UserRole
from app.models.refresh_token import RefreshToken
from app.models.invitation import Invitation
from app.models.audit_log import AuditLog, ActionType, TargetType
from app.models.passkey import PasskeyCredential
from app.models.integration_config import (
    IntegrationConfig,
    IntegrationType,
    IntegrationProvider,
    IntegrationStatus,
)

# Call session models
from app.models.call_session import (
    CallSession,
    TranscriptionSegment,
    AgentAction,
    Suggestion,
    CallStatus,
)

# Domain schema registry
from app.models.domain_schema import DomainSchema, DomainSchemaField

# Document management
from app.models.document import Document, DocumentStatus

# Query logging
from app.models.query_logs import QueryLogs

# Analytics models
from app.models.session_feedback import SessionFeedback
from app.models.field_edit_log import FieldEditLog
from app.models.analytics_summary import AnalyticsDailySummary

# System configuration
from app.models.system_limits import SystemLimits

# Data models (dataclasses, not ORM)
from app.models.query import Query
from app.models.text_chunk import TextChunk
from app.models.text_chunk_for_mvp import TextChunkForMvp
from app.models.embedded import EmbeddedChunk, EmbeddedQuery
from app.models.response_status import ResponseStatus

__all__ = [
    # Base
    'Base',
    # Multi-tenancy
    'Company',
    'User',
    'UserRole',
    'RefreshToken',
    'Invitation',
    'AuditLog',
    'ActionType',
    'TargetType',
    'PasskeyCredential',
    # Integration configs
    'IntegrationConfig',
    'IntegrationType',
    'IntegrationProvider',
    'IntegrationStatus',
    # Call sessions
    'CallSession',
    'TranscriptionSegment',
    'AgentAction',
    'Suggestion',
    'CallStatus',
    # Domain schema registry
    'DomainSchema',
    'DomainSchemaField',
    # Document management
    'Document',
    'DocumentStatus',
    # Query logs
    'QueryLogs',
    # Analytics
    'SessionFeedback',
    'FieldEditLog',
    'AnalyticsDailySummary',
    # System configuration
    'SystemLimits',
    # Data models
    'Query',
    'TextChunk',
    'TextChunkForMvp',
    'EmbeddedChunk',
    'EmbeddedQuery',
    'ResponseStatus',
]
