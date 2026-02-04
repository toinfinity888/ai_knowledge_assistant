"""
Authentication Configuration
JWT and security settings
"""
import os
from pydantic_settings import BaseSettings


class AuthSettings(BaseSettings):
    """Authentication and JWT settings"""

    # JWT Configuration
    jwt_secret_key: str = os.getenv('JWT_SECRET_KEY', 'change-this-secret-key-in-production')
    jwt_algorithm: str = 'HS256'

    # Token TTLs (in seconds)
    access_token_ttl: int = int(os.getenv('JWT_ACCESS_TOKEN_TTL', 1800))  # 30 minutes
    refresh_token_ttl: int = int(os.getenv('JWT_REFRESH_TOKEN_TTL', 2592000))  # 30 days

    # Refresh token limits
    max_refresh_tokens_per_user: int = 5  # Max active refresh tokens per user
    expired_token_cleanup_days: int = 7   # Delete expired tokens older than this

    # Password requirements
    min_password_length: int = 8

    class Config:
        env_prefix = ''


# Singleton instance
_auth_settings = None


def get_auth_settings() -> AuthSettings:
    """Get singleton instance of auth settings"""
    global _auth_settings
    if _auth_settings is None:
        _auth_settings = AuthSettings()
    return _auth_settings
