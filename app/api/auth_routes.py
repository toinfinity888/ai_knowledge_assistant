"""
Authentication API Routes

Handles user login, logout, token refresh, and user info.
"""
from flask import Blueprint, request, jsonify, g

from app.services.auth_service import get_auth_service
from app.middleware.auth_middleware import require_auth, get_token_from_request
from app.middleware.tenant_context import get_current_tenant
from app.database.postgresql_session import get_db_session
from app.logging.logger import logger

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Authenticate user and return tokens.

    Request body:
    {
        "email": "user@example.com",
        "password": "password123"
    }

    Response:
    {
        "access_token": "...",
        "refresh_token": "...",
        "token_type": "Bearer",
        "expires_in": 1800,
        "user": {
            "id": 1,
            "email": "...",
            "full_name": "...",
            "role": "agent",
            "company": {...}
        }
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400

    auth_service = get_auth_service()

    with get_db_session() as db:
        user = auth_service.authenticate(email, password, db)

        if not user:
            logger.warning(f"Failed login attempt for: {email}")
            return jsonify({'error': 'Invalid email or password'}), 401

        # Check if company is active (skip for SUPER_ADMIN who has no company)
        if not user.is_super_admin():
            if not user.company or not user.company.is_active:
                logger.warning(f"Login attempt for inactive company: {email}")
                return jsonify({'error': 'Company account is inactive'}), 403

        # Create tokens
        access_token = auth_service.create_access_token(user)

        # Get device info for refresh token
        device_info = request.headers.get('User-Agent', '')[:500]
        ip_address = request.remote_addr

        refresh_token, _ = auth_service.create_refresh_token(
            user, db,
            device_info=device_info,
            ip_address=ip_address
        )

        company_info = user.company.slug if user.company else "PLATFORM"
        logger.info(f"User logged in: {user.email} (company: {company_info})")

        return jsonify({
            'access_token': access_token,
            'refresh_token': refresh_token,
            'token_type': 'Bearer',
            'expires_in': auth_service.settings.access_token_ttl,
            'user': user.to_dict(include_company=True)
        })


@auth_bp.route('/refresh', methods=['POST'])
def refresh():
    """
    Refresh access token using refresh token with token rotation.

    Token rotation (NIS2 compliance): The old refresh token is invalidated
    and a new one is issued. This prevents stolen token reuse.

    Request body:
    {
        "refresh_token": "..."
    }

    Response:
    {
        "access_token": "...",
        "refresh_token": "...",  // NEW refresh token (old one is now invalid)
        "token_type": "Bearer",
        "expires_in": 1800
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    refresh_token = data.get('refresh_token')

    if not refresh_token:
        return jsonify({'error': 'Refresh token required'}), 400

    auth_service = get_auth_service()

    # Get device info for new refresh token
    device_info = request.headers.get('User-Agent', '')[:500]
    ip_address = request.remote_addr

    with get_db_session() as db:
        # Use token rotation for enhanced security
        result = auth_service.refresh_access_token_with_rotation(
            refresh_token, db,
            device_info=device_info,
            ip_address=ip_address
        )

        if not result:
            return jsonify({'error': 'Invalid or expired refresh token'}), 401

        access_token, new_refresh_token, user = result

        return jsonify({
            'access_token': access_token,
            'refresh_token': new_refresh_token,  # New token issued
            'token_type': 'Bearer',
            'expires_in': auth_service.settings.access_token_ttl
        })


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """
    Logout user by revoking refresh token.

    Request body:
    {
        "refresh_token": "..."
    }

    Response:
    {
        "message": "Logged out successfully"
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    refresh_token = data.get('refresh_token')

    if not refresh_token:
        return jsonify({'error': 'Refresh token required'}), 400

    auth_service = get_auth_service()

    with get_db_session() as db:
        revoked = auth_service.revoke_refresh_token(refresh_token, db)

        if revoked:
            logger.info("User logged out successfully")
        else:
            logger.debug("Logout: token not found (may already be revoked)")

        return jsonify({'message': 'Logged out successfully'})


@auth_bp.route('/logout-all', methods=['POST'])
@require_auth
def logout_all():
    """
    Logout user from all devices by revoking all refresh tokens.

    Requires authentication.

    Response:
    {
        "message": "Logged out from all devices",
        "tokens_revoked": 3
    }
    """
    tenant = get_current_tenant()
    auth_service = get_auth_service()

    with get_db_session() as db:
        count = auth_service.revoke_all_user_tokens(tenant.user_id, db)

        logger.info(f"User {tenant.email} logged out from all devices ({count} tokens revoked)")

        return jsonify({
            'message': 'Logged out from all devices',
            'tokens_revoked': count
        })


@auth_bp.route('/me', methods=['GET'])
@require_auth
def get_current_user():
    """
    Get current authenticated user info.

    Requires authentication.

    Response:
    {
        "user": {
            "id": 1,
            "email": "...",
            "full_name": "...",
            "role": "agent",
            "company": {...}
        }
    }
    """
    tenant = get_current_tenant()
    auth_service = get_auth_service()

    with get_db_session() as db:
        user = auth_service.get_user_by_id(tenant.user_id, db)

        if not user:
            return jsonify({'error': 'User not found'}), 404

        return jsonify({
            'user': user.to_dict(include_company=True)
        })


@auth_bp.route('/change-password', methods=['POST'])
@require_auth
def change_password():
    """
    Change current user's password.

    Requires authentication.

    Request body:
    {
        "current_password": "...",
        "new_password": "..."
    }

    Response:
    {
        "message": "Password changed successfully"
    }
    """
    tenant = get_current_tenant()
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    current_password = data.get('current_password')
    new_password = data.get('new_password')

    if not current_password or not new_password:
        return jsonify({'error': 'Current password and new password required'}), 400

    auth_service = get_auth_service()

    with get_db_session() as db:
        # Verify current password
        user = auth_service.authenticate(tenant.email, current_password, db)
        if not user:
            return jsonify({'error': 'Current password is incorrect'}), 400

        # Update password
        try:
            auth_service.update_password(tenant.user_id, new_password, db)
        except ValueError as e:
            return jsonify({'error': str(e)}), 400

        logger.info(f"User {tenant.email} changed password")

        return jsonify({
            'message': 'Password changed successfully. Please log in again.'
        })


@auth_bp.route('/invite/accept', methods=['POST'])
def accept_invitation():
    """
    Accept an invitation and create a user account.

    This is a public endpoint - no authentication required.
    The invitation token serves as proof of authorization.

    Request body:
    {
        "token": "invitation_token_here",
        "password": "secure_password",
        "full_name": "John Doe"
    }

    Response:
    {
        "access_token": "...",
        "refresh_token": "...",
        "token_type": "Bearer",
        "expires_in": 1800,
        "user": {...},
        "message": "Account created successfully"
    }
    """
    from app.services.invitation_service import (
        get_invitation_service,
        InvitationNotFoundError,
        InvitationExpiredError,
        InvitationAlreadyAcceptedError,
        InvitationError,
    )

    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    token = data.get('token', '').strip()
    password = data.get('password', '')
    full_name = data.get('full_name', '').strip()

    if not token:
        return jsonify({'error': 'Invitation token is required'}), 400
    if not password:
        return jsonify({'error': 'Password is required'}), 400
    if not full_name:
        return jsonify({'error': 'Full name is required'}), 400

    # Get request metadata
    device_info = request.headers.get('User-Agent', '')[:500]
    ip_address = request.remote_addr

    try:
        with get_db_session() as db:
            invitation_service = get_invitation_service()
            user, access_token, refresh_token = invitation_service.accept_invitation(
                token=token,
                password=password,
                full_name=full_name,
                db=db,
                ip_address=ip_address,
                user_agent=device_info,
            )
            db.commit()

            auth_service = get_auth_service()

            logger.info(f"User accepted invitation: {user.email}")

            return jsonify({
                'access_token': access_token,
                'refresh_token': refresh_token,
                'token_type': 'Bearer',
                'expires_in': auth_service.settings.access_token_ttl,
                'user': user.to_dict(include_company=True),
                'message': 'Account created successfully'
            }), 201

    except InvitationNotFoundError:
        return jsonify({'error': 'Invalid invitation token'}), 404
    except InvitationExpiredError:
        return jsonify({'error': 'Invitation has expired'}), 410
    except InvitationAlreadyAcceptedError:
        return jsonify({'error': 'Invitation has already been used'}), 409
    except InvitationError as e:
        return jsonify({'error': str(e)}), 400
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error accepting invitation: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@auth_bp.route('/invite/validate', methods=['GET'])
def validate_invitation():
    """
    Validate an invitation token without accepting it.

    Useful for pre-filling the accept invitation form.

    Query params:
    - token: Invitation token

    Response:
    {
        "valid": true,
        "email": "user@example.com",
        "role": "agent",
        "company_name": "ACME Corp",
        "expires_at": "2025-02-05T12:00:00Z"
    }
    """
    from app.services.invitation_service import get_invitation_service

    token = request.args.get('token', '').strip()

    if not token:
        return jsonify({'error': 'Token is required'}), 400

    try:
        with get_db_session() as db:
            invitation_service = get_invitation_service()
            invitation = invitation_service.get_invitation_by_token(token, db)

            if not invitation:
                return jsonify({'valid': False, 'error': 'Invalid token'}), 404

            if invitation.is_accepted:
                return jsonify({'valid': False, 'error': 'Invitation already used'}), 409

            if invitation.is_expired():
                return jsonify({'valid': False, 'error': 'Invitation expired'}), 410

            return jsonify({
                'valid': True,
                'email': invitation.email,
                'role': invitation.role.value,
                'company_name': invitation.company.name if invitation.company else None,
                'expires_at': invitation.expires_at.isoformat(),
            })

    except Exception as e:
        logger.error(f"Error validating invitation: {e}")
        return jsonify({'error': 'Internal server error'}), 500
