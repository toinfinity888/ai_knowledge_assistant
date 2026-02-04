"""
Company Service for Platform Administration
Handles company CRUD operations and GDPR-compliant data deletion
"""
import re
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.models.company import Company
from app.models.user import User, UserRole
from app.models.invitation import Invitation
from app.models.refresh_token import RefreshToken
from app.models.call_session import CallSession, TranscriptionSegment, Suggestion, AgentAction
from app.models.query_logs import QueryLogs
from app.models.audit_log import AuditLog, ActionType, TargetType
from app.services.audit_service import get_audit_service


class CompanyError(Exception):
    """Base exception for company errors"""
    pass


class CompanyNotFoundError(CompanyError):
    """Company not found"""
    pass


class CompanySlugExistsError(CompanyError):
    """Company slug already exists"""
    pass


class CompanyHasActiveUsersError(CompanyError):
    """Company has active users and cannot be deleted"""
    pass


class CompanyService:
    """
    Service for managing companies.
    Handles CRUD operations and platform-level analytics.
    """

    def _validate_slug(self, slug: str) -> str:
        """Validate and normalize company slug"""
        # Convert to lowercase and replace spaces with hyphens
        normalized = slug.lower().strip()
        normalized = re.sub(r'\s+', '-', normalized)
        # Remove invalid characters
        normalized = re.sub(r'[^a-z0-9-]', '', normalized)
        # Remove consecutive hyphens
        normalized = re.sub(r'-+', '-', normalized)
        # Remove leading/trailing hyphens
        normalized = normalized.strip('-')

        if len(normalized) < 2:
            raise CompanyError("Slug must be at least 2 characters")
        if len(normalized) > 100:
            raise CompanyError("Slug must be at most 100 characters")

        return normalized

    def create_company(
        self,
        slug: str,
        name: str,
        db: Session,
        plan: str = "free",
        settings: Optional[Dict[str, Any]] = None,
        created_by_user_id: Optional[int] = None,
        created_by_email: str = "system",
        ip_address: Optional[str] = None,
    ) -> Company:
        """
        Create a new company.

        Args:
            slug: Unique company identifier (URL-safe)
            name: Company display name
            db: Database session
            plan: Subscription plan (free, basic, pro, enterprise)
            settings: Company settings (max_agents, features, etc.)
            created_by_user_id: SUPER_ADMIN creating the company
            created_by_email: Email for audit logging
            ip_address: IP address for audit logging

        Returns:
            Created Company

        Raises:
            CompanySlugExistsError: If slug already exists
        """
        normalized_slug = self._validate_slug(slug)

        # Check for existing slug
        existing = db.query(Company).filter(Company.slug == normalized_slug).first()
        if existing:
            raise CompanySlugExistsError(f"Company with slug '{normalized_slug}' already exists")

        # Set default settings
        default_settings = {
            "max_agents": 10,
            "max_storage_mb": 1000,
            "features": ["realtime", "knowledge_base"],
        }
        if settings:
            default_settings.update(settings)

        company = Company(
            slug=normalized_slug,
            name=name,
            plan=plan,
            settings=default_settings,
            is_active=True,
        )
        db.add(company)
        db.flush()

        # Audit log
        audit_service = get_audit_service()
        audit_service.log_action(
            action_type=ActionType.COMPANY_CREATE,
            target_type=TargetType.COMPANY,
            target_id=company.id,
            actor_user_id=created_by_user_id,
            actor_email=created_by_email,
            company_id=company.id,
            details={"slug": normalized_slug, "name": name, "plan": plan},
            ip_address=ip_address,
            db=db,
        )

        return company

    def get_company(self, company_id: int, db: Session) -> Optional[Company]:
        """Get company by ID"""
        return db.query(Company).filter(Company.id == company_id).first()

    def get_company_by_slug(self, slug: str, db: Session) -> Optional[Company]:
        """Get company by slug"""
        return db.query(Company).filter(Company.slug == slug).first()

    def list_companies(
        self,
        db: Session,
        include_inactive: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Company]:
        """List all companies (SUPER_ADMIN only)"""
        query = db.query(Company)
        if not include_inactive:
            query = query.filter(Company.is_active == True)
        return query.order_by(Company.created_at.desc()).offset(offset).limit(limit).all()

    def update_company(
        self,
        company_id: int,
        db: Session,
        updates: Dict[str, Any],
        updated_by_user_id: Optional[int] = None,
        updated_by_email: str = "system",
        ip_address: Optional[str] = None,
    ) -> Company:
        """
        Update company details.

        Args:
            company_id: Company to update
            db: Database session
            updates: Dict of fields to update (name, plan, settings, is_active)
            updated_by_user_id: User performing the update
            updated_by_email: Email for audit logging
            ip_address: IP address for audit logging

        Returns:
            Updated Company
        """
        company = db.query(Company).filter(Company.id == company_id).first()
        if not company:
            raise CompanyNotFoundError(f"Company {company_id} not found")

        old_values = {}
        allowed_fields = ['name', 'plan', 'settings', 'is_active']

        for field, value in updates.items():
            if field in allowed_fields and hasattr(company, field):
                old_values[field] = getattr(company, field)
                setattr(company, field, value)

        db.flush()

        # Audit log
        audit_service = get_audit_service()
        audit_service.log_action(
            action_type=ActionType.COMPANY_UPDATE,
            target_type=TargetType.COMPANY,
            target_id=company_id,
            actor_user_id=updated_by_user_id,
            actor_email=updated_by_email,
            company_id=company_id,
            details={"old_values": old_values, "new_values": updates},
            ip_address=ip_address,
            db=db,
        )

        return company

    def deactivate_company(
        self,
        company_id: int,
        db: Session,
        deactivated_by_user_id: Optional[int] = None,
        deactivated_by_email: str = "system",
        ip_address: Optional[str] = None,
    ) -> Company:
        """
        Soft-delete a company by deactivating it.
        Users will no longer be able to log in.
        """
        company = db.query(Company).filter(Company.id == company_id).first()
        if not company:
            raise CompanyNotFoundError(f"Company {company_id} not found")

        company.is_active = False
        db.flush()

        # Audit log
        audit_service = get_audit_service()
        audit_service.log_action(
            action_type=ActionType.COMPANY_DEACTIVATE,
            target_type=TargetType.COMPANY,
            target_id=company_id,
            actor_user_id=deactivated_by_user_id,
            actor_email=deactivated_by_email,
            company_id=company_id,
            details={"company_name": company.name},
            ip_address=ip_address,
            db=db,
        )

        return company

    def delete_company_gdpr(
        self,
        company_id: int,
        db: Session,
        deleted_by_user_id: Optional[int] = None,
        deleted_by_email: str = "system",
        ip_address: Optional[str] = None,
    ) -> Dict[str, int]:
        """
        GDPR-compliant company deletion.
        Cascades deletion to all related data.

        Args:
            company_id: Company to delete
            db: Database session
            deleted_by_user_id: SUPER_ADMIN performing the deletion
            deleted_by_email: Email for audit logging
            ip_address: IP address for audit logging

        Returns:
            Dict with counts of deleted records by type
        """
        company = db.query(Company).filter(Company.id == company_id).first()
        if not company:
            raise CompanyNotFoundError(f"Company {company_id} not found")

        deletion_summary = {
            "company_name": company.name,
            "company_slug": company.slug,
        }

        # Get user IDs for this company (needed for cascading)
        user_ids = [u.id for u in db.query(User.id).filter(User.company_id == company_id).all()]

        # Get call session IDs
        session_ids = [s.id for s in db.query(CallSession.id).filter(CallSession.company_id == company_id).all()]

        # Delete in order (respecting foreign keys):

        # 1. Delete suggestions (depends on call_sessions)
        deletion_summary["suggestions"] = db.query(Suggestion).filter(
            Suggestion.session_id.in_(session_ids)
        ).delete(synchronize_session=False) if session_ids else 0

        # 2. Delete agent_actions (depends on call_sessions)
        deletion_summary["agent_actions"] = db.query(AgentAction).filter(
            AgentAction.session_id.in_(session_ids)
        ).delete(synchronize_session=False) if session_ids else 0

        # 3. Delete transcription_segments (depends on call_sessions)
        deletion_summary["transcription_segments"] = db.query(TranscriptionSegment).filter(
            TranscriptionSegment.session_id.in_(session_ids)
        ).delete(synchronize_session=False) if session_ids else 0

        # 4. Delete call_sessions
        deletion_summary["call_sessions"] = db.query(CallSession).filter(
            CallSession.company_id == company_id
        ).delete(synchronize_session=False)

        # 5. Delete refresh_tokens (depends on users)
        deletion_summary["refresh_tokens"] = db.query(RefreshToken).filter(
            RefreshToken.user_id.in_(user_ids)
        ).delete(synchronize_session=False) if user_ids else 0

        # 6. Delete invitations
        deletion_summary["invitations"] = db.query(Invitation).filter(
            Invitation.company_id == company_id
        ).delete(synchronize_session=False)

        # 7. Delete query_logs
        deletion_summary["query_logs"] = db.query(QueryLogs).filter(
            QueryLogs.company_id == company_id
        ).delete(synchronize_session=False)

        # 8. Anonymize audit_logs (keep for compliance, but remove PII)
        # We keep audit logs but set actor_email to anonymized value
        deletion_summary["audit_logs_anonymized"] = db.query(AuditLog).filter(
            AuditLog.company_id == company_id
        ).update({
            AuditLog.actor_email: f"deleted_user@company_{company_id}",
            AuditLog.ip_address: None,
            AuditLog.user_agent: None,
        }, synchronize_session=False)

        # 9. Delete users
        deletion_summary["users"] = db.query(User).filter(
            User.company_id == company_id
        ).delete(synchronize_session=False)

        # 10. Delete company
        db.delete(company)

        # Create final audit log (will be kept with anonymized actor)
        audit_service = get_audit_service()
        audit_service.log_action(
            action_type=ActionType.COMPANY_DELETE,
            target_type=TargetType.COMPANY,
            target_id=company_id,
            actor_user_id=deleted_by_user_id,
            actor_email=deleted_by_email,
            company_id=None,  # Company no longer exists
            details=deletion_summary,
            ip_address=ip_address,
            db=db,
        )

        return deletion_summary

    def check_agent_limit(self, company_id: int, db: Session) -> Tuple[int, int]:
        """
        Check company's agent limit.

        Returns:
            Tuple of (current_count, max_allowed)
        """
        company = db.query(Company).filter(Company.id == company_id).first()
        if not company:
            return 0, 0

        max_agents = company.settings.get('max_agents', 10) if company.settings else 10

        current_count = db.query(User).filter(
            and_(
                User.company_id == company_id,
                User.is_active == True,
                User.role.in_([UserRole.ADMIN, UserRole.AGENT])
            )
        ).count()

        return current_count, max_agents

    def get_global_analytics(self, db: Session) -> Dict[str, Any]:
        """
        Get platform-wide analytics (SUPER_ADMIN only).

        Returns:
            Dict with platform statistics
        """
        # Company counts
        total_companies = db.query(Company).count()
        active_companies = db.query(Company).filter(Company.is_active == True).count()

        # User counts
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.is_active == True).count()

        # Users by role
        users_by_role = dict(
            db.query(User.role, func.count(User.id))
            .filter(User.is_active == True)
            .group_by(User.role)
            .all()
        )

        # Companies by plan
        companies_by_plan = dict(
            db.query(Company.plan, func.count(Company.id))
            .filter(Company.is_active == True)
            .group_by(Company.plan)
            .all()
        )

        # Call session stats
        total_sessions = db.query(CallSession).count()

        # Recent activity (last 24 hours)
        from datetime import timedelta
        yesterday = datetime.now(timezone.utc) - timedelta(hours=24)

        recent_sessions = db.query(CallSession).filter(
            CallSession.start_time >= yesterday
        ).count()

        recent_users = db.query(User).filter(
            User.last_login >= yesterday
        ).count()

        return {
            "companies": {
                "total": total_companies,
                "active": active_companies,
                "by_plan": {str(k): v for k, v in companies_by_plan.items()},
            },
            "users": {
                "total": total_users,
                "active": active_users,
                "by_role": {str(k.value) if hasattr(k, 'value') else str(k): v for k, v in users_by_role.items()},
            },
            "sessions": {
                "total": total_sessions,
                "last_24h": recent_sessions,
            },
            "activity": {
                "users_last_24h": recent_users,
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_company_stats(self, company_id: int, db: Session) -> Dict[str, Any]:
        """Get statistics for a specific company"""
        company = db.query(Company).filter(Company.id == company_id).first()
        if not company:
            raise CompanyNotFoundError(f"Company {company_id} not found")

        # User counts
        total_users = db.query(User).filter(User.company_id == company_id).count()
        active_users = db.query(User).filter(
            and_(User.company_id == company_id, User.is_active == True)
        ).count()

        # Users by role
        users_by_role = dict(
            db.query(User.role, func.count(User.id))
            .filter(and_(User.company_id == company_id, User.is_active == True))
            .group_by(User.role)
            .all()
        )

        # Session counts
        total_sessions = db.query(CallSession).filter(
            CallSession.company_id == company_id
        ).count()

        # Agent limit check
        current_agents, max_agents = self.check_agent_limit(company_id, db)

        return {
            "company_id": company_id,
            "company_name": company.name,
            "plan": company.plan,
            "users": {
                "total": total_users,
                "active": active_users,
                "by_role": {str(k.value) if hasattr(k, 'value') else str(k): v for k, v in users_by_role.items()},
            },
            "limits": {
                "current_agents": current_agents,
                "max_agents": max_agents,
            },
            "sessions": {
                "total": total_sessions,
            },
        }


# Singleton instance
_company_service: Optional[CompanyService] = None


def get_company_service() -> CompanyService:
    """Get the singleton CompanyService instance"""
    global _company_service
    if _company_service is None:
        _company_service = CompanyService()
    return _company_service
