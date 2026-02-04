"""
Invitation Service for Token-Based User Onboarding
Handles creation, validation, and acceptance of invitations
"""
import secrets
from typing import Optional, List, Tuple
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.invitation import Invitation
from app.models.user import User, UserRole
from app.models.company import Company
from app.services.auth_service import get_auth_service
from app.services.audit_service import get_audit_service
from app.models.audit_log import ActionType, TargetType


class InvitationError(Exception):
    """Base exception for invitation errors"""
    pass


class InvitationNotFoundError(InvitationError):
    """Invitation not found"""
    pass


class InvitationExpiredError(InvitationError):
    """Invitation has expired"""
    pass


class InvitationAlreadyAcceptedError(InvitationError):
    """Invitation has already been accepted"""
    pass


class InvitationLimitExceededError(InvitationError):
    """Company has reached its agent limit"""
    pass


class InvalidRoleError(InvitationError):
    """Invalid role for invitation"""
    pass


class InvitationService:
    """
    Service for managing user invitations.
    Handles the invite-based onboarding flow.
    """

    def __init__(self, token_length: int = 32, default_expires_days: int = 7):
        self.token_length = token_length
        self.default_expires_days = default_expires_days
        self.auth_service = get_auth_service()

    def _generate_token(self) -> str:
        """Generate a secure random token"""
        return secrets.token_urlsafe(self.token_length)

    def _check_role_hierarchy(
        self,
        creator_role: UserRole,
        invited_role: UserRole,
        creator_is_super_admin: bool
    ) -> bool:
        """
        Validate that creator can invite users with the specified role.

        Rules:
        - SUPER_ADMIN can invite anyone (including other SUPER_ADMINs and ADMINs)
        - ADMIN can only invite AGENT or VIEWER within their company
        - AGENT and VIEWER cannot invite anyone
        """
        if creator_is_super_admin:
            return True

        if creator_role == UserRole.ADMIN:
            return invited_role in (UserRole.AGENT, UserRole.VIEWER)

        return False

    def _check_company_limits(
        self,
        company_id: int,
        db: Session
    ) -> Tuple[int, int]:
        """
        Check if company has reached its agent limit.

        Returns:
            Tuple of (current_agent_count, max_agents)
        """
        company = db.query(Company).filter(Company.id == company_id).first()
        if not company:
            return 0, 0

        max_agents = company.settings.get('max_agents', 10) if company.settings else 10

        # Count current active users (excluding VIEWER role for agent count)
        current_count = db.query(User).filter(
            and_(
                User.company_id == company_id,
                User.is_active == True,
                User.role.in_([UserRole.ADMIN, UserRole.AGENT])
            )
        ).count()

        # Also count pending invitations for ADMIN or AGENT roles
        pending_count = db.query(Invitation).filter(
            and_(
                Invitation.company_id == company_id,
                Invitation.is_accepted == False,
                Invitation.expires_at > datetime.now(timezone.utc),
                Invitation.role.in_([UserRole.ADMIN, UserRole.AGENT])
            )
        ).count()

        return current_count + pending_count, max_agents

    def create_invitation(
        self,
        email: str,
        role: UserRole,
        created_by_user_id: int,
        db: Session,
        company_id: Optional[int] = None,
        expires_days: Optional[int] = None,
        ip_address: Optional[str] = None,
    ) -> Tuple[Invitation, str]:
        """
        Create a new invitation.

        Args:
            email: Email address to invite
            role: Role to assign when accepted
            created_by_user_id: ID of user creating the invitation
            db: Database session
            company_id: Company to invite to (required for non-SUPER_ADMIN roles)
            expires_days: Days until invitation expires (default: 7)
            ip_address: IP address for audit logging

        Returns:
            Tuple of (Invitation, raw_token)

        Raises:
            InvalidRoleError: If creator cannot invite this role
            InvitationLimitExceededError: If company has reached agent limit
        """
        # Get creator to check permissions
        creator = db.query(User).filter(User.id == created_by_user_id).first()
        if not creator:
            raise InvalidRoleError("Creator not found")

        # Validate role hierarchy
        if not self._check_role_hierarchy(creator.role, role, creator.is_super_admin()):
            raise InvalidRoleError(
                f"User with role '{creator.role.value}' cannot invite users with role '{role.value}'"
            )

        # Validate company_id requirement
        if role != UserRole.SUPER_ADMIN and company_id is None:
            raise InvalidRoleError("company_id is required for non-SUPER_ADMIN invitations")

        # Check company limits for ADMIN/AGENT invitations
        if company_id and role in (UserRole.ADMIN, UserRole.AGENT):
            current, max_allowed = self._check_company_limits(company_id, db)
            if current >= max_allowed:
                raise InvitationLimitExceededError(
                    f"Company has reached its agent limit ({max_allowed})"
                )

        # Check for existing pending invitation
        existing = db.query(Invitation).filter(
            and_(
                Invitation.email == email.lower(),
                Invitation.company_id == company_id,
                Invitation.is_accepted == False,
                Invitation.expires_at > datetime.now(timezone.utc)
            )
        ).first()

        if existing:
            # Revoke existing invitation and create new one
            existing.expires_at = datetime.now(timezone.utc)

        # Check if user already exists
        existing_user = db.query(User).filter(User.email == email.lower()).first()
        if existing_user:
            if existing_user.company_id == company_id:
                raise InvalidRoleError("User already exists in this company")

        # Generate token and create invitation
        token = self._generate_token()
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days or self.default_expires_days)

        invitation = Invitation(
            email=email.lower(),
            company_id=company_id,
            role=role,
            token=token,
            expires_at=expires_at,
            created_by_user_id=created_by_user_id,
        )
        db.add(invitation)
        db.flush()

        # Audit log
        audit_service = get_audit_service()
        audit_service.log_action(
            action_type=ActionType.INVITATION_CREATE,
            target_type=TargetType.INVITATION,
            target_id=invitation.id,
            actor_user_id=created_by_user_id,
            actor_email=creator.email,
            company_id=company_id,
            details={"invited_email": email, "role": role.value},
            ip_address=ip_address,
            db=db,
        )

        return invitation, token

    def accept_invitation(
        self,
        token: str,
        password: str,
        full_name: str,
        db: Session,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[User, str, str]:
        """
        Accept an invitation and create a user account.

        Args:
            token: Invitation token
            password: Password for new account
            full_name: Full name for new user
            db: Database session
            ip_address: IP address for audit logging
            user_agent: User agent for token creation

        Returns:
            Tuple of (User, access_token, refresh_token)

        Raises:
            InvitationNotFoundError: If invitation not found
            InvitationExpiredError: If invitation has expired
            InvitationAlreadyAcceptedError: If invitation already used
        """
        invitation = db.query(Invitation).filter(Invitation.token == token).first()

        if not invitation:
            raise InvitationNotFoundError("Invitation not found")

        if invitation.is_accepted:
            raise InvitationAlreadyAcceptedError("Invitation has already been accepted")

        if invitation.is_expired():
            raise InvitationExpiredError("Invitation has expired")

        # Create user
        user = User(
            email=invitation.email,
            full_name=full_name,
            password_hash=self.auth_service.hash_password(password),
            role=invitation.role,
            company_id=invitation.company_id,
            is_active=True,
        )
        db.add(user)
        db.flush()

        # Mark invitation as accepted
        invitation.mark_accepted()

        # Create tokens
        access_token = self.auth_service.create_access_token(user)
        refresh_token, _ = self.auth_service.create_refresh_token(
            user, db, device_info=user_agent, ip_address=ip_address
        )

        # Audit log
        audit_service = get_audit_service()
        audit_service.log_action(
            action_type=ActionType.INVITATION_ACCEPT,
            target_type=TargetType.USER,
            target_id=user.id,
            actor_user_id=user.id,
            actor_email=user.email,
            company_id=invitation.company_id,
            details={"invitation_id": invitation.id},
            ip_address=ip_address,
            db=db,
        )

        return user, access_token, refresh_token

    def get_invitation_by_token(self, token: str, db: Session) -> Optional[Invitation]:
        """Get invitation by token"""
        return db.query(Invitation).filter(Invitation.token == token).first()

    def get_pending_invitations(
        self,
        company_id: int,
        db: Session,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Invitation]:
        """Get pending (non-expired, non-accepted) invitations for a company"""
        return db.query(Invitation).filter(
            and_(
                Invitation.company_id == company_id,
                Invitation.is_accepted == False,
                Invitation.expires_at > datetime.now(timezone.utc)
            )
        ).order_by(Invitation.created_at.desc()).offset(offset).limit(limit).all()

    def revoke_invitation(
        self,
        invitation_id: int,
        company_id: int,
        revoked_by_user_id: int,
        db: Session,
        ip_address: Optional[str] = None,
    ) -> bool:
        """
        Revoke a pending invitation.

        Args:
            invitation_id: ID of invitation to revoke
            company_id: Company ID for authorization check
            revoked_by_user_id: ID of user revoking the invitation
            db: Database session
            ip_address: IP address for audit logging

        Returns:
            True if revoked, False if not found or already used
        """
        invitation = db.query(Invitation).filter(
            and_(
                Invitation.id == invitation_id,
                Invitation.company_id == company_id,
                Invitation.is_accepted == False
            )
        ).first()

        if not invitation:
            return False

        # Set expiration to now (effectively revoking it)
        invitation.expires_at = datetime.now(timezone.utc)

        # Get revoker for audit
        revoker = db.query(User).filter(User.id == revoked_by_user_id).first()

        # Audit log
        audit_service = get_audit_service()
        audit_service.log_action(
            action_type=ActionType.INVITATION_REVOKE,
            target_type=TargetType.INVITATION,
            target_id=invitation_id,
            actor_user_id=revoked_by_user_id,
            actor_email=revoker.email if revoker else "unknown",
            company_id=company_id,
            details={"invited_email": invitation.email},
            ip_address=ip_address,
            db=db,
        )

        return True


# Singleton instance
_invitation_service: Optional[InvitationService] = None


def get_invitation_service() -> InvitationService:
    """Get the singleton InvitationService instance"""
    global _invitation_service
    if _invitation_service is None:
        _invitation_service = InvitationService()
    return _invitation_service
