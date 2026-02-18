"""
Passkey API Routes for WebAuthn/Passkeys Authentication

Provides endpoints for:
- Passkey registration (for logged-in users)
- Passkey authentication (passwordless login)
- Passkey management (list, delete)
"""
import logging
from flask import Blueprint, request, jsonify

from app.database.postgresql_session import get_db_session
from app.models.user import User
from app.models.passkey import PasskeyCredential
from app.services.passkey_service import get_passkey_service
from app.services.auth_service import get_auth_service
from app.middleware.auth_middleware import require_auth
from app.middleware.tenant_context import get_current_tenant

logger = logging.getLogger(__name__)

passkey_bp = Blueprint('passkey', __name__, url_prefix='/api/auth/passkey')


# =============================================================================
# Registration Endpoints (require authentication)
# =============================================================================

@passkey_bp.route('/register/options', methods=['POST'])
@require_auth
def register_options():
    """
    Get WebAuthn registration options for the current user.

    Returns challenge and options for navigator.credentials.create()
    """
    try:
        tenant = get_current_tenant()
        user_id = tenant.user_id

        with get_db_session() as db:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return jsonify({'error': 'User not found'}), 404

            # Get existing credentials to exclude
            existing_credentials = db.query(PasskeyCredential).filter(
                PasskeyCredential.user_id == user_id
            ).all()

            passkey_service = get_passkey_service()
            options_json, challenge_id = passkey_service.generate_registration_options(
                user=user,
                existing_credentials=existing_credentials,
            )

            return jsonify({
                'options': options_json,
                'challenge_id': challenge_id,
            }), 200

    except Exception as e:
        logger.error(f"Error generating registration options: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@passkey_bp.route('/register/verify', methods=['POST'])
@require_auth
def register_verify():
    """
    Verify WebAuthn registration response and store the credential.

    Expected JSON body:
    {
        "challenge_id": "xxx",
        "credential": { ... WebAuthn credential response ... },
        "device_name": "iPhone 15 Pro"  // optional
    }
    """
    try:
        tenant = get_current_tenant()
        user_id = tenant.user_id

        data = request.get_json()
        challenge_id = data.get('challenge_id')
        credential_response = data.get('credential')
        device_name = data.get('device_name')

        if not challenge_id or not credential_response:
            return jsonify({'error': 'Missing challenge_id or credential'}), 400

        with get_db_session() as db:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return jsonify({'error': 'User not found'}), 404

            passkey_service = get_passkey_service()

            # Verify and create credential
            credential = passkey_service.verify_registration(
                user=user,
                challenge_id=challenge_id,
                credential_response=credential_response,
                device_name=device_name,
            )

            # Save to database
            db.add(credential)
            db.commit()
            db.refresh(credential)

            logger.info(f"Passkey registered for user {user_id}: {credential.device_name}")

            return jsonify({
                'success': True,
                'passkey': credential.to_dict(),
            }), 201

    except ValueError as e:
        logger.warning(f"Registration verification failed: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error verifying registration: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


# =============================================================================
# Authentication Endpoints (public - no auth required)
# =============================================================================

@passkey_bp.route('/login/options', methods=['POST'])
def login_options():
    """
    Get WebAuthn authentication options for passkey login.

    Optional JSON body:
    {
        "email": "user@example.com"  // Optional - for non-discoverable credentials
    }

    If email is provided, returns options with that user's credentials.
    If not provided, allows any discoverable credential (passkey).
    """
    try:
        data = request.get_json() or {}
        email = data.get('email')

        passkey_service = get_passkey_service()
        user_credentials = None

        # If email provided, get user's credentials
        if email:
            with get_db_session() as db:
                user = db.query(User).filter(User.email == email).first()
                if user:
                    user_credentials = db.query(PasskeyCredential).filter(
                        PasskeyCredential.user_id == user.id
                    ).all()

        options_json, challenge_id = passkey_service.generate_authentication_options(
            user_credentials=user_credentials,
        )

        return jsonify({
            'options': options_json,
            'challenge_id': challenge_id,
        }), 200

    except Exception as e:
        logger.error(f"Error generating login options: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@passkey_bp.route('/login/verify', methods=['POST'])
def login_verify():
    """
    Verify WebAuthn authentication response and issue tokens.

    Expected JSON body:
    {
        "challenge_id": "xxx",
        "credential": { ... WebAuthn credential response ... }
    }

    Returns access_token, refresh_token, and user info on success.
    """
    try:
        data = request.get_json()
        challenge_id = data.get('challenge_id')
        credential_response = data.get('credential')

        if not challenge_id or not credential_response:
            return jsonify({'error': 'Missing challenge_id or credential'}), 400

        # Get credential ID from response
        credential_id_b64 = credential_response.get('id')
        if not credential_id_b64:
            return jsonify({'error': 'Missing credential id'}), 400

        with get_db_session() as db:
            # Find the stored credential
            stored_credential = db.query(PasskeyCredential).filter(
                PasskeyCredential.credential_id_b64 == credential_id_b64
            ).first()

            if not stored_credential:
                return jsonify({'error': 'Credential not found'}), 401

            # Get the user
            user = db.query(User).filter(User.id == stored_credential.user_id).first()
            if not user:
                return jsonify({'error': 'User not found'}), 401

            if not user.is_active:
                return jsonify({'error': 'Account is disabled'}), 401

            passkey_service = get_passkey_service()

            # Verify authentication
            new_sign_count = passkey_service.verify_authentication(
                challenge_id=challenge_id,
                credential_response=credential_response,
                stored_credential=stored_credential,
            )

            # Update sign count and last used
            stored_credential.update_sign_count(new_sign_count)
            db.commit()

            # Issue tokens
            auth_service = get_auth_service()
            access_token = auth_service.create_access_token(user)
            refresh_token = auth_service.create_refresh_token(
                user=user,
                db=db,
                device_info=request.headers.get('User-Agent', 'Passkey Login'),
                ip_address=request.remote_addr,
            )

            # Update last login
            from datetime import datetime, timezone
            user.last_login = datetime.now(timezone.utc)
            db.commit()

            logger.info(f"Passkey login successful for user {user.id} ({user.email})")

            return jsonify({
                'access_token': access_token,
                'refresh_token': refresh_token,
                'user': user.to_dict(include_company=True),
            }), 200

    except ValueError as e:
        logger.warning(f"Passkey login failed: {e}")
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        logger.error(f"Error verifying login: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


# =============================================================================
# Management Endpoints (require authentication)
# =============================================================================

@passkey_bp.route('/list', methods=['GET'])
@require_auth
def list_passkeys():
    """
    List all passkeys for the current user.
    """
    try:
        tenant = get_current_tenant()
        user_id = tenant.user_id

        with get_db_session() as db:
            passkeys = db.query(PasskeyCredential).filter(
                PasskeyCredential.user_id == user_id
            ).order_by(PasskeyCredential.created_at.desc()).all()

            return jsonify({
                'passkeys': [p.to_dict() for p in passkeys],
            }), 200

    except Exception as e:
        logger.error(f"Error listing passkeys: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@passkey_bp.route('/<int:passkey_id>', methods=['DELETE'])
@require_auth
def delete_passkey(passkey_id: int):
    """
    Delete a passkey by ID.

    Users can only delete their own passkeys.
    """
    try:
        tenant = get_current_tenant()
        user_id = tenant.user_id

        with get_db_session() as db:
            passkey = db.query(PasskeyCredential).filter(
                PasskeyCredential.id == passkey_id,
                PasskeyCredential.user_id == user_id,
            ).first()

            if not passkey:
                return jsonify({'error': 'Passkey not found'}), 404

            device_name = passkey.device_name
            db.delete(passkey)
            db.commit()

            logger.info(f"Passkey deleted for user {user_id}: {device_name}")

            return jsonify({
                'success': True,
                'message': f'Passkey "{device_name}" deleted',
            }), 200

    except Exception as e:
        logger.error(f"Error deleting passkey: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
