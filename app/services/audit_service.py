"""
Audit Service for NIS2/ANSSI Compliance
Handles logging of all administrative actions
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.audit_log import AuditLog, ActionType, TargetType


class AuditService:
    """
    Service for managing audit logs.
    Provides methods for logging actions and querying audit history.
    """

    def log_action(
        self,
        action_type: str,
        target_type: str,
        db: Session,
        target_id: Optional[int] = None,
        actor_user_id: Optional[int] = None,
        actor_email: str = "system",
        company_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """
        Log an administrative action.

        Args:
            action_type: Type of action (e.g., 'user.create', 'company.delete')
            target_type: Type of target (e.g., 'user', 'company')
            db: Database session
            target_id: ID of the target entity
            actor_user_id: ID of user performing the action
            actor_email: Email of actor (denormalized for persistence)
            company_id: Company scope (None for global actions)
            details: Additional details about the action
            ip_address: IP address of the request
            user_agent: User agent string

        Returns:
            Created AuditLog entry
        """
        audit_log = AuditLog(
            actor_user_id=actor_user_id,
            actor_email=actor_email,
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            company_id=company_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.add(audit_log)
        db.flush()  # Get ID without committing
        return audit_log

    def get_company_audit_logs(
        self,
        company_id: int,
        db: Session,
        limit: int = 100,
        offset: int = 0,
        action_type: Optional[str] = None,
        actor_user_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[AuditLog]:
        """
        Get audit logs for a specific company.

        Args:
            company_id: Company to get logs for
            db: Database session
            limit: Maximum number of logs to return
            offset: Number of logs to skip
            action_type: Filter by action type (optional)
            actor_user_id: Filter by actor (optional)
            start_date: Filter by start date (optional)
            end_date: Filter by end date (optional)

        Returns:
            List of AuditLog entries
        """
        query = db.query(AuditLog).filter(AuditLog.company_id == company_id)

        if action_type:
            query = query.filter(AuditLog.action_type == action_type)
        if actor_user_id:
            query = query.filter(AuditLog.actor_user_id == actor_user_id)
        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)
        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)

        return query.order_by(desc(AuditLog.created_at)).offset(offset).limit(limit).all()

    def get_global_audit_logs(
        self,
        db: Session,
        limit: int = 100,
        offset: int = 0,
        action_type: Optional[str] = None,
        company_id: Optional[int] = None,
        actor_user_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[AuditLog]:
        """
        Get global audit logs (SUPER_ADMIN only).

        Args:
            db: Database session
            limit: Maximum number of logs to return
            offset: Number of logs to skip
            action_type: Filter by action type (optional)
            company_id: Filter by company (optional)
            actor_user_id: Filter by actor (optional)
            start_date: Filter by start date (optional)
            end_date: Filter by end date (optional)

        Returns:
            List of AuditLog entries
        """
        query = db.query(AuditLog)

        if action_type:
            query = query.filter(AuditLog.action_type == action_type)
        if company_id is not None:
            query = query.filter(AuditLog.company_id == company_id)
        if actor_user_id:
            query = query.filter(AuditLog.actor_user_id == actor_user_id)
        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)
        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)

        return query.order_by(desc(AuditLog.created_at)).offset(offset).limit(limit).all()

    def count_company_logs(self, company_id: int, db: Session) -> int:
        """Count total audit logs for a company"""
        return db.query(AuditLog).filter(AuditLog.company_id == company_id).count()

    def count_global_logs(self, db: Session, company_id: Optional[int] = None) -> int:
        """Count total audit logs globally or for a specific company"""
        query = db.query(AuditLog)
        if company_id is not None:
            query = query.filter(AuditLog.company_id == company_id)
        return query.count()


# Singleton instance
_audit_service: Optional[AuditService] = None


def get_audit_service() -> AuditService:
    """Get the singleton AuditService instance"""
    global _audit_service
    if _audit_service is None:
        _audit_service = AuditService()
    return _audit_service
