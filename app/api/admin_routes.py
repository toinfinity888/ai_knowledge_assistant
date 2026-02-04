"""
Admin API Routes
Company-scoped administration endpoints for ADMIN and SUPER_ADMIN users
"""
from flask import Blueprint, request, jsonify, g

from app.middleware.auth_middleware import (
    require_auth,
    require_company_admin,
    get_request_metadata,
)
from app.services.invitation_service import (
    get_invitation_service,
    InvitationError,
    InvitationNotFoundError,
    InvitationLimitExceededError,
    InvalidRoleError,
)
from app.services.audit_service import get_audit_service
from app.models.user import UserRole
from app.database.postgresql_session import get_db_session
from app.logging.logger import logger


admin_bp = Blueprint('admin', __name__, url_prefix='/api/v1/admin')


# ==================== Invitation Management ====================

@admin_bp.route('/invitations', methods=['POST'])
@require_auth
@require_company_admin
def create_invitation():
    """
    Create a new user invitation.

    Request body:
    {
        "email": "newuser@example.com",
        "role": "agent",  // "admin", "agent", or "viewer"
        "company_id": 123,  // optional, defaults to current user's company
        "expires_days": 7  // optional, default: 7
    }

    Response:
    {
        "invitation": {...},
        "token": "abc123...",  // Only returned on creation
        "invite_url": "/accept-invite?token=abc123...",
        "message": "Invitation created successfully"
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    email = data.get('email', '').strip().lower()
    role_str = data.get('role', '').strip().lower()
    expires_days = data.get('expires_days', 7)

    if not email:
        return jsonify({'error': 'email is required'}), 400
    if not role_str:
        return jsonify({'error': 'role is required'}), 400

    # Validate role
    try:
        role = UserRole(role_str)
    except ValueError:
        return jsonify({'error': f'Invalid role. Must be one of: admin, agent, viewer'}), 400

    context = g.tenant_context
    metadata = get_request_metadata()

    # Determine company_id
    if context.is_super_admin:
        # SUPER_ADMIN can invite to any company
        company_id = data.get('company_id')
        if role != UserRole.SUPER_ADMIN and not company_id:
            return jsonify({'error': 'company_id is required when inviting non-super_admin users'}), 400
    else:
        # Company admin can only invite to their own company
        company_id = context.company_id
        if data.get('company_id') and data.get('company_id') != company_id:
            return jsonify({'error': 'Cannot invite users to other companies'}), 403

    try:
        with get_db_session() as db:
            invitation_service = get_invitation_service()
            invitation, token = invitation_service.create_invitation(
                email=email,
                role=role,
                company_id=company_id,
                created_by_user_id=context.user_id,
                db=db,
                expires_days=expires_days,
                ip_address=metadata['ip_address'],
            )
            db.commit()

            return jsonify({
                'invitation': invitation.to_dict(include_token=False),
                'token': token,
                'invite_url': f"/accept-invite?token={token}",
                'message': 'Invitation created successfully'
            }), 201

    except InvalidRoleError as e:
        return jsonify({'error': str(e)}), 403
    except InvitationLimitExceededError as e:
        return jsonify({'error': str(e)}), 403
    except InvitationError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating invitation: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@admin_bp.route('/invitations', methods=['GET'])
@require_auth
@require_company_admin
def list_invitations():
    """
    List pending invitations for the current company.

    Query params:
    - limit: int (default: 100)
    - offset: int (default: 0)
    - company_id: int (optional, SUPER_ADMIN only)

    Response:
    {
        "invitations": [...],
        "total": 5
    }
    """
    limit = min(int(request.args.get('limit', 100)), 500)
    offset = int(request.args.get('offset', 0))

    context = g.tenant_context

    # Determine company_id
    if context.is_super_admin:
        company_id = request.args.get('company_id', type=int)
        if not company_id:
            return jsonify({'error': 'company_id is required for SUPER_ADMIN'}), 400
    else:
        company_id = context.company_id

    try:
        with get_db_session() as db:
            invitation_service = get_invitation_service()
            invitations = invitation_service.get_pending_invitations(
                company_id=company_id,
                db=db,
                limit=limit,
                offset=offset,
            )

            return jsonify({
                'invitations': [inv.to_dict() for inv in invitations],
                'total': len(invitations),
            })

    except Exception as e:
        logger.error(f"Error listing invitations: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@admin_bp.route('/invitations/<int:invitation_id>', methods=['DELETE'])
@require_auth
@require_company_admin
def revoke_invitation(invitation_id: int):
    """
    Revoke a pending invitation.

    Response:
    {
        "message": "Invitation revoked",
        "invitation_id": 123
    }
    """
    context = g.tenant_context
    metadata = get_request_metadata()

    # For SUPER_ADMIN, we need company_id from query param
    if context.is_super_admin:
        company_id = request.args.get('company_id', type=int)
        if not company_id:
            return jsonify({'error': 'company_id is required for SUPER_ADMIN'}), 400
    else:
        company_id = context.company_id

    try:
        with get_db_session() as db:
            invitation_service = get_invitation_service()
            revoked = invitation_service.revoke_invitation(
                invitation_id=invitation_id,
                company_id=company_id,
                revoked_by_user_id=context.user_id,
                db=db,
                ip_address=metadata['ip_address'],
            )
            db.commit()

            if not revoked:
                return jsonify({'error': 'Invitation not found or already used'}), 404

            return jsonify({
                'message': 'Invitation revoked',
                'invitation_id': invitation_id,
            })

    except Exception as e:
        logger.error(f"Error revoking invitation {invitation_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500


# ==================== Audit Logs (Company-scoped) ====================

@admin_bp.route('/audit-logs', methods=['GET'])
@require_auth
@require_company_admin
def company_audit_logs():
    """
    Get audit logs for the current company.

    Query params:
    - limit: int (default: 100)
    - offset: int (default: 0)
    - action_type: string (optional)
    - actor_user_id: int (optional)
    - company_id: int (optional, SUPER_ADMIN only)

    Response:
    {
        "audit_logs": [...],
        "total": 100,
        "limit": 100,
        "offset": 0
    }
    """
    limit = min(int(request.args.get('limit', 100)), 500)
    offset = int(request.args.get('offset', 0))
    action_type = request.args.get('action_type')
    actor_user_id = request.args.get('actor_user_id', type=int)

    context = g.tenant_context

    # Determine company_id
    if context.is_super_admin:
        company_id = request.args.get('company_id', type=int)
        if not company_id:
            return jsonify({'error': 'company_id is required for SUPER_ADMIN'}), 400
    else:
        company_id = context.company_id

    try:
        with get_db_session() as db:
            audit_service = get_audit_service()
            logs = audit_service.get_company_audit_logs(
                company_id=company_id,
                db=db,
                limit=limit,
                offset=offset,
                action_type=action_type,
                actor_user_id=actor_user_id,
            )
            total = audit_service.count_company_logs(company_id, db)

            return jsonify({
                'audit_logs': [log.to_dict() for log in logs],
                'total': total,
                'limit': limit,
                'offset': offset,
            })

    except Exception as e:
        logger.error(f"Error getting company audit logs: {e}")
        return jsonify({'error': 'Internal server error'}), 500


# ==================== Document Management (Placeholder) ====================
# These endpoints will be implemented when document upload functionality is added

@admin_bp.route('/documents', methods=['POST'])
@require_auth
@require_company_admin
def upload_document():
    """
    Upload a document to the company knowledge base.

    This is a placeholder endpoint. Full implementation requires:
    - File upload handling
    - PDF/document parsing
    - Vector store indexing with company_id
    """
    return jsonify({
        'error': 'Not implemented',
        'message': 'Document upload functionality coming soon'
    }), 501


@admin_bp.route('/documents', methods=['GET'])
@require_auth
@require_company_admin
def list_documents():
    """
    List documents in the company knowledge base.

    This is a placeholder endpoint.
    """
    return jsonify({
        'error': 'Not implemented',
        'message': 'Document listing functionality coming soon'
    }), 501


@admin_bp.route('/documents/<int:document_id>', methods=['DELETE'])
@require_auth
@require_company_admin
def delete_document(document_id: int):
    """
    Delete a document from the company knowledge base.

    This is a placeholder endpoint.
    """
    return jsonify({
        'error': 'Not implemented',
        'message': 'Document deletion functionality coming soon'
    }), 501
