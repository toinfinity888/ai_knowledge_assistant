"""
Passkey Service for WebAuthn/Passkeys Authentication

Handles WebAuthn registration and authentication flows using py_webauthn.
Provides passwordless login via biometrics, security keys, and platform authenticators.
"""
import os
import secrets
import base64
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

from webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,
    options_to_json,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    UserVerificationRequirement,
    ResidentKeyRequirement,
    PublicKeyCredentialDescriptor,
    AuthenticatorTransport,
)
from webauthn.helpers.cose import COSEAlgorithmIdentifier
from webauthn.helpers import bytes_to_base64url, base64url_to_bytes

from app.models.passkey import PasskeyCredential
from app.models.user import User

logger = logging.getLogger(__name__)


class PasskeyService:
    """
    WebAuthn/Passkey service for passwordless authentication.

    Handles:
    - Registration: Generate options, verify response, store credential
    - Authentication: Generate options, verify response, return user
    """

    def __init__(self):
        # Relying Party configuration from environment
        self.rp_id = os.getenv('WEBAUTHN_RP_ID', 'localhost')
        self.rp_name = os.getenv('WEBAUTHN_RP_NAME', 'AI Knowledge Assistant')
        self.origin = os.getenv('WEBAUTHN_ORIGIN', 'http://localhost:8000')

        # Challenge storage (in-memory for simplicity, use Redis in production)
        # Format: {challenge_id: {'challenge': bytes, 'user_id': int, 'expires': datetime}}
        self._challenges: Dict[str, Dict[str, Any]] = {}

        # Challenge expiration in seconds
        self.challenge_ttl = 300  # 5 minutes

        logger.info(f"PasskeyService initialized: rp_id={self.rp_id}, origin={self.origin}")

    def _cleanup_expired_challenges(self):
        """Remove expired challenges."""
        now = datetime.utcnow()
        expired = [k for k, v in self._challenges.items() if v.get('expires', now) < now]
        for k in expired:
            del self._challenges[k]

    def generate_registration_options(
        self,
        user: User,
        existing_credentials: List[PasskeyCredential],
    ) -> Tuple[str, str]:
        """
        Generate WebAuthn registration options for a user.

        Args:
            user: The user registering a new passkey
            existing_credentials: User's existing passkeys (to exclude)

        Returns:
            Tuple of (options_json, challenge_id)
        """
        self._cleanup_expired_challenges()

        # Build exclude credentials list to prevent re-registration
        exclude_credentials = []
        for cred in existing_credentials:
            exclude_credentials.append(
                PublicKeyCredentialDescriptor(
                    id=cred.credential_id,
                    transports=[
                        AuthenticatorTransport.USB,
                        AuthenticatorTransport.NFC,
                        AuthenticatorTransport.BLE,
                        AuthenticatorTransport.INTERNAL,
                        AuthenticatorTransport.HYBRID,
                    ],
                )
            )

        # Generate registration options
        options = generate_registration_options(
            rp_id=self.rp_id,
            rp_name=self.rp_name,
            user_id=str(user.id).encode('utf-8'),
            user_name=user.email,
            user_display_name=user.full_name or user.email,
            exclude_credentials=exclude_credentials if exclude_credentials else None,
            authenticator_selection=AuthenticatorSelectionCriteria(
                resident_key=ResidentKeyRequirement.PREFERRED,
                user_verification=UserVerificationRequirement.PREFERRED,
            ),
            supported_pub_key_algs=[
                COSEAlgorithmIdentifier.ECDSA_SHA_256,
                COSEAlgorithmIdentifier.RSASSA_PKCS1_v1_5_SHA_256,
            ],
            timeout=60000,  # 60 seconds
        )

        # Store challenge for verification
        challenge_id = secrets.token_urlsafe(32)
        from datetime import timedelta
        self._challenges[f"reg_{challenge_id}"] = {
            'challenge': options.challenge,
            'user_id': user.id,
            'expires': datetime.utcnow() + timedelta(seconds=self.challenge_ttl),
        }

        # Convert to JSON for frontend
        options_json = options_to_json(options)

        logger.info(f"Generated registration options for user {user.id}, challenge_id={challenge_id}")

        return options_json, challenge_id

    def verify_registration(
        self,
        user: User,
        challenge_id: str,
        credential_response: Dict[str, Any],
        device_name: Optional[str] = None,
    ) -> PasskeyCredential:
        """
        Verify WebAuthn registration response and create credential.

        Args:
            user: The user registering the passkey
            challenge_id: The challenge ID from registration options
            credential_response: The credential response from the browser
            device_name: User-friendly name for the device

        Returns:
            Created PasskeyCredential (not yet added to DB)

        Raises:
            ValueError: If verification fails
        """
        self._cleanup_expired_challenges()

        # Retrieve and remove challenge
        challenge_key = f"reg_{challenge_id}"
        challenge_data = self._challenges.pop(challenge_key, None)

        if not challenge_data:
            raise ValueError("Challenge expired or not found")

        if challenge_data['user_id'] != user.id:
            raise ValueError("Challenge does not belong to this user")

        try:
            # Verify the registration response
            verification = verify_registration_response(
                credential=credential_response,
                expected_challenge=challenge_data['challenge'],
                expected_rp_id=self.rp_id,
                expected_origin=self.origin,
                require_user_verification=False,  # Preferred but not required
            )

            # Create the credential object
            credential = PasskeyCredential(
                user_id=user.id,
                credential_id=verification.credential_id,
                credential_id_b64=bytes_to_base64url(verification.credential_id),
                public_key=verification.credential_public_key,
                sign_count=verification.sign_count,
                device_name=device_name or "Unknown Device",
                aaguid=str(verification.aaguid) if verification.aaguid else None,
                created_at=datetime.utcnow(),
            )

            logger.info(f"Registration verified for user {user.id}, credential_id={credential.credential_id_b64[:20]}...")

            return credential

        except Exception as e:
            logger.error(f"Registration verification failed: {e}")
            raise ValueError(f"Registration verification failed: {str(e)}")

    def generate_authentication_options(
        self,
        user_credentials: Optional[List[PasskeyCredential]] = None,
    ) -> Tuple[str, str]:
        """
        Generate WebAuthn authentication options.

        Args:
            user_credentials: Optional list of allowed credentials (for non-discoverable flow)
                             If None, allows any discoverable credential (passkey)

        Returns:
            Tuple of (options_json, challenge_id)
        """
        self._cleanup_expired_challenges()

        # Build allow credentials list
        allow_credentials = None
        if user_credentials:
            allow_credentials = []
            for cred in user_credentials:
                allow_credentials.append(
                    PublicKeyCredentialDescriptor(
                        id=cred.credential_id,
                        transports=[
                            AuthenticatorTransport.USB,
                            AuthenticatorTransport.NFC,
                            AuthenticatorTransport.BLE,
                            AuthenticatorTransport.INTERNAL,
                            AuthenticatorTransport.HYBRID,
                        ],
                    )
                )

        # Generate authentication options
        options = generate_authentication_options(
            rp_id=self.rp_id,
            allow_credentials=allow_credentials,
            user_verification=UserVerificationRequirement.PREFERRED,
            timeout=60000,  # 60 seconds
        )

        # Store challenge for verification
        challenge_id = secrets.token_urlsafe(32)
        from datetime import timedelta
        self._challenges[f"auth_{challenge_id}"] = {
            'challenge': options.challenge,
            'expires': datetime.utcnow() + timedelta(seconds=self.challenge_ttl),
        }

        # Convert to JSON for frontend
        options_json = options_to_json(options)

        logger.info(f"Generated authentication options, challenge_id={challenge_id}")

        return options_json, challenge_id

    def verify_authentication(
        self,
        challenge_id: str,
        credential_response: Dict[str, Any],
        stored_credential: PasskeyCredential,
    ) -> int:
        """
        Verify WebAuthn authentication response.

        Args:
            challenge_id: The challenge ID from authentication options
            credential_response: The credential response from the browser
            stored_credential: The stored credential to verify against

        Returns:
            New sign count (should be stored)

        Raises:
            ValueError: If verification fails
        """
        self._cleanup_expired_challenges()

        # Retrieve and remove challenge
        challenge_key = f"auth_{challenge_id}"
        challenge_data = self._challenges.pop(challenge_key, None)

        if not challenge_data:
            raise ValueError("Challenge expired or not found")

        try:
            # Verify the authentication response
            verification = verify_authentication_response(
                credential=credential_response,
                expected_challenge=challenge_data['challenge'],
                expected_rp_id=self.rp_id,
                expected_origin=self.origin,
                credential_public_key=stored_credential.public_key,
                credential_current_sign_count=stored_credential.sign_count,
                require_user_verification=False,  # Preferred but not required
            )

            logger.info(f"Authentication verified for credential {stored_credential.credential_id_b64[:20]}...")

            return verification.new_sign_count

        except Exception as e:
            logger.error(f"Authentication verification failed: {e}")
            raise ValueError(f"Authentication verification failed: {str(e)}")


# Singleton instance
_passkey_service: Optional[PasskeyService] = None


def get_passkey_service() -> PasskeyService:
    """Get or create the PasskeyService singleton."""
    global _passkey_service
    if _passkey_service is None:
        _passkey_service = PasskeyService()
    return _passkey_service
