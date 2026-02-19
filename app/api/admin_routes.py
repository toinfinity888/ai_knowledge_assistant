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


# ==================== Document Management ====================

@admin_bp.route('/documents', methods=['POST'])
@require_auth
@require_company_admin
def upload_document():
    """
    Upload a PDF document to the company knowledge base.

    Request: multipart/form-data with 'file' field containing PDF

    Response:
    {
        "document": {
            "id": 1,
            "filename": "manual.pdf",
            "status": "pending",
            ...
        },
        "message": "Document uploaded. Processing started."
    }
    """
    from app.services.document_service import get_document_service
    from app.models.document import DocumentStatus

    # Check for file in request
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'No file selected'}), 400

    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Only PDF files are supported'}), 400

    # Check file size (max 50MB)
    file_content = file.read()
    max_size = 50 * 1024 * 1024  # 50MB
    if len(file_content) > max_size:
        return jsonify({'error': f'File too large. Maximum size is {max_size // (1024*1024)}MB'}), 400

    context = g.tenant_context

    # Determine company_id
    if context.is_super_admin:
        company_id = request.form.get('company_id', type=int)
        if not company_id:
            return jsonify({'error': 'company_id is required for SUPER_ADMIN'}), 400
    else:
        company_id = context.company_id

    try:
        document_service = get_document_service()

        # Upload document
        document = document_service.upload_document(
            file_content=file_content,
            original_filename=file.filename,
            company_id=company_id,
            user_id=context.user_id,
            mime_type=file.content_type or 'application/pdf',
        )

        # Process document (parse, chunk, embed, store)
        # This could be moved to a background task for large files
        try:
            document = document_service.process_document(document.id)
        except Exception as e:
            logger.error(f"Error processing document {document.id}: {e}")
            # Document is already saved with FAILED status

        return jsonify({
            'document': document.to_dict(),
            'message': 'Document uploaded and processed.' if document.status == DocumentStatus.COMPLETED else 'Document uploaded. Processing failed.',
        }), 201 if document.status == DocumentStatus.COMPLETED else 202

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error uploading document: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@admin_bp.route('/documents', methods=['GET'])
@require_auth
@require_company_admin
def list_documents():
    """
    List documents in the company knowledge base.

    Query params:
    - page: int (default: 1)
    - per_page: int (default: 20, max: 100)
    - status: string (optional: pending, processing, completed, failed)
    - company_id: int (optional, SUPER_ADMIN only)

    Response:
    {
        "documents": [...],
        "total": 50,
        "page": 1,
        "per_page": 20,
        "pages": 3
    }
    """
    from app.services.document_service import get_document_service
    from app.models.document import DocumentStatus

    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    status_str = request.args.get('status')

    # Parse status if provided
    status = None
    if status_str:
        try:
            status = DocumentStatus(status_str)
        except ValueError:
            return jsonify({'error': f'Invalid status. Must be one of: pending, processing, completed, failed'}), 400

    context = g.tenant_context

    # Determine company_id
    if context.is_super_admin:
        company_id = request.args.get('company_id', type=int)
        if not company_id:
            return jsonify({'error': 'company_id is required for SUPER_ADMIN'}), 400
    else:
        company_id = context.company_id

    try:
        document_service = get_document_service()
        documents, total = document_service.get_documents(
            company_id=company_id,
            page=page,
            per_page=per_page,
            status=status,
        )

        pages = (total + per_page - 1) // per_page  # Ceiling division

        return jsonify({
            'documents': [doc.to_dict() for doc in documents],
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': pages,
        })

    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@admin_bp.route('/documents/<int:document_id>', methods=['GET'])
@require_auth
@require_company_admin
def get_document(document_id: int):
    """
    Get details of a specific document.

    Response:
    {
        "document": {...}
    }
    """
    from app.services.document_service import get_document_service

    context = g.tenant_context

    # Determine company_id
    if context.is_super_admin:
        company_id = request.args.get('company_id', type=int)
        if not company_id:
            return jsonify({'error': 'company_id is required for SUPER_ADMIN'}), 400
    else:
        company_id = context.company_id

    try:
        document_service = get_document_service()
        document = document_service.get_document(document_id, company_id)

        if not document:
            return jsonify({'error': 'Document not found'}), 404

        return jsonify({'document': document.to_dict()})

    except Exception as e:
        logger.error(f"Error getting document {document_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@admin_bp.route('/documents/<int:document_id>', methods=['DELETE'])
@require_auth
@require_company_admin
def delete_document(document_id: int):
    """
    Delete a document from the company knowledge base.

    This removes:
    - The document file from disk
    - The document record from the database
    - All associated vectors from Qdrant

    Response:
    {
        "message": "Document deleted",
        "document_id": 123
    }
    """
    from app.services.document_service import get_document_service

    context = g.tenant_context
    metadata = get_request_metadata()

    # Determine company_id
    if context.is_super_admin:
        company_id = request.args.get('company_id', type=int)
        if not company_id:
            return jsonify({'error': 'company_id is required for SUPER_ADMIN'}), 400
    else:
        company_id = context.company_id

    try:
        document_service = get_document_service()
        deleted = document_service.delete_document(document_id, company_id)

        if not deleted:
            return jsonify({'error': 'Document not found'}), 404

        # Log the deletion
        try:
            with get_db_session() as db:
                audit_service = get_audit_service()
                audit_service.log_action(
                    action_type='document_deleted',
                    actor_user_id=context.user_id,
                    company_id=company_id,
                    target_type='document',
                    target_id=document_id,
                    ip_address=metadata['ip_address'],
                    db=db,
                )
                db.commit()
        except Exception as e:
            logger.warning(f"Failed to log document deletion: {e}")

        return jsonify({
            'message': 'Document deleted',
            'document_id': document_id,
        })

    except Exception as e:
        logger.error(f"Error deleting document {document_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@admin_bp.route('/documents/<int:document_id>/reprocess', methods=['POST'])
@require_auth
@require_company_admin
def reprocess_document(document_id: int):
    """
    Reprocess a failed document.

    Response:
    {
        "document": {...},
        "message": "Document reprocessing started"
    }
    """
    from app.services.document_service import get_document_service
    from app.models.document import DocumentStatus

    context = g.tenant_context

    # Determine company_id
    if context.is_super_admin:
        company_id = request.args.get('company_id', type=int)
        if not company_id:
            return jsonify({'error': 'company_id is required for SUPER_ADMIN'}), 400
    else:
        company_id = context.company_id

    try:
        document_service = get_document_service()
        document = document_service.reprocess_document(document_id, company_id)

        return jsonify({
            'document': document.to_dict(),
            'message': 'Document reprocessed successfully' if document.status == DocumentStatus.COMPLETED else 'Document reprocessing failed',
        })

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error reprocessing document {document_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500
