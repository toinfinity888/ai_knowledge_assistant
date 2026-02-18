"""
Passkey Credential Model for WebAuthn/Passkeys Authentication

Stores WebAuthn credentials that allow passwordless login using
biometrics, security keys, or platform authenticators.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, LargeBinary, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.models.base import Base


class PasskeyCredential(Base):
    """
    Stores WebAuthn/Passkey credentials for passwordless authentication.

    Each user can have multiple passkeys (e.g., phone, laptop, security key).
    """
    __tablename__ = 'passkey_credentials'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # WebAuthn credential data
    credential_id = Column(LargeBinary, unique=True, nullable=False)  # Raw credential ID bytes
    credential_id_b64 = Column(String(255), unique=True, nullable=False, index=True)  # Base64 for lookup
    public_key = Column(LargeBinary, nullable=False)  # COSE public key bytes
    sign_count = Column(Integer, default=0, nullable=False)  # Replay attack protection

    # User-friendly metadata
    device_name = Column(String(100))  # e.g., "iPhone 15 Pro", "MacBook Pro", "YubiKey 5"

    # AAGUID for authenticator identification (optional)
    aaguid = Column(String(36), nullable=True)  # Authenticator Attestation GUID

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="passkeys")

    def __repr__(self):
        return f"<PasskeyCredential(id={self.id}, user_id={self.user_id}, device='{self.device_name}')>"

    def update_sign_count(self, new_count: int):
        """Update the sign count after successful authentication."""
        self.sign_count = new_count
        self.last_used_at = datetime.utcnow()

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'device_name': self.device_name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
        }
