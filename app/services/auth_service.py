"""
Authentication Service
Handles JWT tokens, password hashing, and user authentication
"""
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.user import User, UserRole
from app.models.refresh_token import RefreshToken
from app.models.company import Company
from app.config.auth_config import get_auth_settings
from app.database.postgresql_session import get_db_session
from app.logging.logger import logger


class AuthService:
    """
    Handles authentication operations including:
    - Password hashing with Argon2id
    - JWT access token creation and verification
    - Refresh token management
    - User authentication
    """

    def __init__(self):
        self.settings = get_auth_settings()
        self.password_hasher = PasswordHasher(
            time_cost=2,       # Number of iterations
            memory_cost=65536, # 64 MB memory
            parallelism=1,     # Number of parallel threads
        )

    # ==================== Password Hashing ====================

    def hash_password(self, password: str) -> str:
        """
        Hash a password using Argon2id algorithm (OWASP recommended)

        Args:
            password: Plain text password

        Returns:
            Argon2id hash string
        """
        return self.password_hasher.hash(password)

    def verify_password(self, password: str, password_hash: str) -> bool:
        """
        Verify a password against its hash

        Args:
            password: Plain text password to verify
            password_hash: Stored Argon2id hash

        Returns:
            True if password matches, False otherwise
        """
        try:
            self.password_hasher.verify(password_hash, password)
            return True
        except (VerifyMismatchError, InvalidHashError):
            return False

    # ==================== Access Tokens (JWT) ====================

    def create_access_token(self, user: User) -> str:
        """
        Create a JWT access token for a user

        Args:
            user: User object

        Returns:
            JWT token string
        """
        now = datetime.utcnow()
        expires = now + timedelta(seconds=self.settings.access_token_ttl)

        payload = {
            'sub': str(user.id),
            'email': user.email,
            'company_id': user.company_id,  # None for SUPER_ADMIN
            'company_slug': user.company.slug if user.company else None,
            'role': user.role.value,
            'is_super_admin': user.is_super_admin(),
            'iat': now,
            'exp': expires,
            'type': 'access',
        }

        return jwt.encode(
            payload,
            self.settings.jwt_secret_key,
            algorithm=self.settings.jwt_algorithm
        )

    def verify_access_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify and decode a JWT access token

        Args:
            token: JWT token string

        Returns:
            Decoded payload dict or None if invalid
        """
        try:
            payload = jwt.decode(
                token,
                self.settings.jwt_secret_key,
                algorithms=[self.settings.jwt_algorithm]
            )

            # Verify it's an access token
            if payload.get('type') != 'access':
                logger.warning("Token type mismatch - expected 'access'")
                return None

            return payload

        except jwt.ExpiredSignatureError:
            logger.debug("Access token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid access token: {e}")
            return None

    # ==================== Refresh Tokens ====================

    def _hash_refresh_token(self, token: str) -> str:
        """Hash refresh token for storage using SHA-256"""
        return hashlib.sha256(token.encode()).hexdigest()

    def create_refresh_token(
        self,
        user: User,
        db: Session,
        device_info: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Tuple[str, RefreshToken]:
        """
        Create a new refresh token for a user

        Args:
            user: User object
            db: Database session
            device_info: User-Agent or device identifier
            ip_address: Client IP address

        Returns:
            Tuple of (raw_token_string, RefreshToken_record)
        """
        # Enforce max tokens per user
        self._limit_user_tokens(user.id, db)

        # Generate secure random token
        raw_token = secrets.token_urlsafe(64)
        token_hash = self._hash_refresh_token(raw_token)

        expires_at = datetime.utcnow() + timedelta(seconds=self.settings.refresh_token_ttl)

        refresh_token = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            device_info=device_info,
            ip_address=ip_address,
            expires_at=expires_at,
        )

        db.add(refresh_token)
        db.commit()
        db.refresh(refresh_token)

        return raw_token, refresh_token

    def verify_refresh_token(self, token: str, db: Session) -> Optional[RefreshToken]:
        """
        Verify a refresh token and return the token record

        Args:
            token: Raw refresh token string
            db: Database session

        Returns:
            RefreshToken record if valid, None otherwise
        """
        token_hash = self._hash_refresh_token(token)

        refresh_token = db.query(RefreshToken).filter(
            RefreshToken.token_hash == token_hash
        ).first()

        if not refresh_token:
            logger.debug("Refresh token not found")
            return None

        if not refresh_token.is_valid():
            logger.debug("Refresh token invalid (revoked or expired)")
            return None

        # Update last used timestamp
        refresh_token.update_last_used()
        db.commit()

        return refresh_token

    def refresh_access_token(
        self,
        refresh_token_str: str,
        db: Session
    ) -> Optional[Tuple[str, User]]:
        """
        Create a new access token using a refresh token

        Args:
            refresh_token_str: Raw refresh token string
            db: Database session

        Returns:
            Tuple of (new_access_token, User) or None if invalid
        """
        refresh_token = self.verify_refresh_token(refresh_token_str, db)

        if not refresh_token:
            return None

        user = db.query(User).filter(
            User.id == refresh_token.user_id,
            User.is_active == True
        ).first()

        if not user:
            logger.warning(f"User {refresh_token.user_id} not found or inactive")
            return None

        access_token = self.create_access_token(user)
        return access_token, user

    def refresh_access_token_with_rotation(
        self,
        refresh_token_str: str,
        db: Session,
        device_info: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Optional[Tuple[str, str, User]]:
        """
        Refresh access token with token rotation (NIS2 compliance).
        Issues a new refresh token and invalidates the old one.

        Args:
            refresh_token_str: Raw refresh token string
            db: Database session
            device_info: Device info for new token
            ip_address: IP address for new token

        Returns:
            Tuple of (new_access_token, new_refresh_token, User) or None if invalid
        """
        refresh_token = self.verify_refresh_token(refresh_token_str, db)

        if not refresh_token:
            return None

        user = db.query(User).filter(
            User.id == refresh_token.user_id,
            User.is_active == True
        ).first()

        if not user:
            logger.warning(f"User {refresh_token.user_id} not found or inactive")
            return None

        # Check if company is still active (for non-SUPER_ADMIN users)
        if user.company_id and user.company and not user.company.is_active:
            logger.warning(f"Company {user.company_id} is inactive")
            return None

        # Revoke old refresh token
        refresh_token.revoke()

        # Create new tokens
        access_token = self.create_access_token(user)
        new_refresh_token, _ = self.create_refresh_token(
            user, db, device_info=device_info, ip_address=ip_address
        )

        return access_token, new_refresh_token, user

    def revoke_refresh_token(self, token: str, db: Session) -> bool:
        """
        Revoke a refresh token (logout)

        Args:
            token: Raw refresh token string
            db: Database session

        Returns:
            True if revoked, False if not found
        """
        token_hash = self._hash_refresh_token(token)

        refresh_token = db.query(RefreshToken).filter(
            RefreshToken.token_hash == token_hash
        ).first()

        if refresh_token:
            refresh_token.revoke()
            db.commit()
            return True

        return False

    def revoke_all_user_tokens(self, user_id: int, db: Session) -> int:
        """
        Revoke all refresh tokens for a user (logout everywhere)

        Args:
            user_id: User ID
            db: Database session

        Returns:
            Number of tokens revoked
        """
        result = db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id,
            RefreshToken.is_revoked == False
        ).update({'is_revoked': True})

        db.commit()
        return result

    # ==================== Token Cleanup ====================

    def _limit_user_tokens(self, user_id: int, db: Session, max_tokens: int = None):
        """
        Keep only the most recent N tokens per user

        Args:
            user_id: User ID
            db: Database session
            max_tokens: Maximum number of tokens to keep (default from settings)
        """
        max_tokens = max_tokens or self.settings.max_refresh_tokens_per_user

        # Get all active tokens for user, ordered by created_at desc
        tokens = db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id,
            RefreshToken.is_revoked == False
        ).order_by(RefreshToken.created_at.desc()).all()

        # If at or above limit, revoke oldest tokens
        if len(tokens) >= max_tokens:
            tokens_to_revoke = tokens[max_tokens - 1:]  # Keep only max_tokens - 1 (room for new one)
            for token in tokens_to_revoke:
                token.revoke()
            db.commit()

    def cleanup_expired_tokens(self, db: Session) -> int:
        """
        Delete expired and revoked tokens older than cleanup threshold

        Args:
            db: Database session

        Returns:
            Number of tokens deleted
        """
        cutoff = datetime.utcnow() - timedelta(days=self.settings.expired_token_cleanup_days)

        result = db.query(RefreshToken).filter(
            or_(
                RefreshToken.expires_at < datetime.utcnow(),
                RefreshToken.is_revoked == True
            ),
            RefreshToken.created_at < cutoff
        ).delete()

        db.commit()
        logger.info(f"Cleaned up {result} expired/revoked refresh tokens")
        return result

    # ==================== User Authentication ====================

    def authenticate(self, email: str, password: str, db: Session) -> Optional[User]:
        """
        Authenticate a user by email and password

        Args:
            email: User email
            password: Plain text password
            db: Database session

        Returns:
            User object if authenticated, None otherwise
        """
        user = db.query(User).filter(
            User.email == email.lower().strip(),
            User.is_active == True
        ).first()

        if not user:
            logger.debug(f"User not found: {email}")
            return None

        if not self.verify_password(password, user.password_hash):
            logger.debug(f"Invalid password for user: {email}")
            return None

        # Update last login timestamp
        user.last_login = datetime.utcnow()
        db.commit()

        return user

    def get_user_by_id(self, user_id: int, db: Session) -> Optional[User]:
        """Get a user by ID"""
        return db.query(User).filter(
            User.id == user_id,
            User.is_active == True
        ).first()

    # ==================== User Management ====================

    def create_user(
        self,
        email: str,
        password: str,
        full_name: str,
        role: UserRole,
        db: Session,
        company_id: Optional[int] = None,
    ) -> User:
        """
        Create a new user

        Args:
            email: User email (must be unique)
            password: Plain text password
            full_name: User's full name
            role: User role
            db: Database session
            company_id: Company ID (required for non-SUPER_ADMIN users)

        Returns:
            Created User object

        Raises:
            ValueError: If email already exists or validation fails
        """
        # Check if email already exists
        existing = db.query(User).filter(User.email == email.lower().strip()).first()
        if existing:
            raise ValueError(f"Email already registered: {email}")

        # Validate company_id requirement
        if role != UserRole.SUPER_ADMIN and company_id is None:
            raise ValueError("company_id is required for non-SUPER_ADMIN users")

        if role == UserRole.SUPER_ADMIN and company_id is not None:
            raise ValueError("SUPER_ADMIN users cannot belong to a company")

        # Validate password
        if len(password) < self.settings.min_password_length:
            raise ValueError(f"Password must be at least {self.settings.min_password_length} characters")

        user = User(
            email=email.lower().strip(),
            password_hash=self.hash_password(password),
            full_name=full_name,
            company_id=company_id,
            role=role,
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        return user

    def update_password(self, user_id: int, new_password: str, db: Session) -> bool:
        """
        Update a user's password

        Args:
            user_id: User ID
            new_password: New plain text password
            db: Database session

        Returns:
            True if updated, False if user not found
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return False

        if len(new_password) < self.settings.min_password_length:
            raise ValueError(f"Password must be at least {self.settings.min_password_length} characters")

        user.password_hash = self.hash_password(new_password)
        db.commit()

        # Revoke all existing refresh tokens (security measure)
        self.revoke_all_user_tokens(user_id, db)

        return True


# Singleton instance
_auth_service = None


def get_auth_service() -> AuthService:
    """Get singleton instance of AuthService"""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service
