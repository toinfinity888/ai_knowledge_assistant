"""
Refresh Token Model for JWT Authentication
Stores refresh tokens for secure token rotation
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.models.base import Base


class RefreshToken(Base):
    """
    Stores refresh tokens for JWT authentication.
    Allows token revocation and device tracking.
    """
    __tablename__ = 'refresh_tokens'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # User relationship
    user_id = Column(
        Integer,
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # Token data - store hash, not the actual token
    token_hash = Column(String(255), unique=True, nullable=False, index=True)

    # Device/session info for security
    device_info = Column(String(500), nullable=True)  # User-Agent or device identifier
    ip_address = Column(String(45), nullable=True)    # IPv4 or IPv6

    # Token lifecycle
    expires_at = Column(DateTime, nullable=False)
    is_revoked = Column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="refresh_tokens")

    def __repr__(self):
        return f"<RefreshToken(user_id={self.user_id}, revoked={self.is_revoked}, expires={self.expires_at})>"

    def is_valid(self) -> bool:
        """Check if token is valid (not revoked and not expired)"""
        if self.is_revoked:
            return False
        if datetime.utcnow() > self.expires_at:
            return False
        return True

    def revoke(self) -> None:
        """Revoke this refresh token"""
        self.is_revoked = True

    def update_last_used(self) -> None:
        """Update the last used timestamp"""
        self.last_used_at = datetime.utcnow()
