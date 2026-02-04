"""
Company Management API Routes

Handles company settings and user management.
Most routes require admin role.
"""
from flask import Blueprint, request, jsonify

from app.services.auth_service import get_auth_service
from app.middleware.auth_middleware import require_auth, require_admin
from app.middleware.tenant_context import get_current_tenant
from app.models.user import User, UserRole
from app.models.company import Company
from app.database.postgresql_session import get_db_session
from app.logging.logger import logger

company_bp = Blueprint('company', __name__, url_prefix='/api/company')


# ==================== Company Settings ====================

@company_bp.route('/settings', methods=['GET'])
@require_auth
def get_company_settings():
    """
    Get current company settings.

    Response:
    {
        "company": {
            "id": 1,
            "slug": "acme",
            "name": "Acme Corp",
            "plan": "pro",
            "is_active": true,
            "settings": {...}
        }
    }
    """
    tenant = get_current_tenant()

    with get_db_session() as db:
        company = db.query(Company).filter(
            Company.id == tenant.company_id
        ).first()

        if not company:
            return jsonify({'error': 'Company not found'}), 404

        return jsonify({
            'company': company.to_dict()
        })


@company_bp.route('/settings', methods=['PATCH'])
@require_auth
@require_admin
def update_company_settings():
    """
    Update company settings (admin only).

    Request body:
    {
        "name": "New Company Name",
        "settings": {
            "key": "value"
        }
    }

    Response:
    {
        "company": {...},
        "message": "Settings updated"
    }
    """
    tenant = get_current_tenant()
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    with get_db_session() as db:
        company = db.query(Company).filter(
            Company.id == tenant.company_id
        ).first()

        if not company:
            return jsonify({'error': 'Company not found'}), 404

        # Update allowed fields
        if 'name' in data:
            company.name = data['name']

        if 'settings' in data:
            # Merge new settings with existing
            current_settings = company.settings or {}
            current_settings.update(data['settings'])
            company.settings = current_settings

        db.commit()
        db.refresh(company)

        logger.info(f"Company settings updated: {company.slug} by {tenant.email}")

        return jsonify({
            'company': company.to_dict(),
            'message': 'Settings updated'
        })


# ==================== User Management ====================

@company_bp.route('/users', methods=['GET'])
@require_auth
@require_admin
def list_users():
    """
    List all users in the company (admin only).

    Query params:
    - include_inactive: Include inactive users (default: false)

    Response:
    {
        "users": [
            {
                "id": 1,
                "email": "...",
                "full_name": "...",
                "role": "agent",
                "is_active": true
            },
            ...
        ],
        "total": 5
    }
    """
    tenant = get_current_tenant()
    include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'

    with get_db_session() as db:
        query = db.query(User).filter(User.company_id == tenant.company_id)

        if not include_inactive:
            query = query.filter(User.is_active == True)

        users = query.order_by(User.created_at.desc()).all()

        return jsonify({
            'users': [u.to_dict() for u in users],
            'total': len(users)
        })


@company_bp.route('/users', methods=['POST'])
@require_auth
@require_admin
def create_user():
    """
    Create a new user in the company (admin only).

    Request body:
    {
        "email": "user@example.com",
        "password": "securepassword",
        "full_name": "John Doe",
        "role": "agent"
    }

    Response:
    {
        "user": {...},
        "message": "User created"
    }
    """
    tenant = get_current_tenant()
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    required_fields = ['email', 'password', 'full_name']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400

    # Validate role
    role_str = data.get('role', 'agent')
    try:
        role = UserRole(role_str)
    except ValueError:
        return jsonify({
            'error': f'Invalid role: {role_str}. Valid roles: {[r.value for r in UserRole]}'
        }), 400

    auth_service = get_auth_service()

    with get_db_session() as db:
        try:
            user = auth_service.create_user(
                email=data['email'],
                password=data['password'],
                full_name=data['full_name'],
                company_id=tenant.company_id,
                role=role,
                db=db
            )

            logger.info(f"User created: {user.email} by {tenant.email}")

            return jsonify({
                'user': user.to_dict(),
                'message': 'User created'
            }), 201

        except ValueError as e:
            return jsonify({'error': str(e)}), 400


@company_bp.route('/users/<int:user_id>', methods=['GET'])
@require_auth
@require_admin
def get_user(user_id: int):
    """
    Get a specific user (admin only).

    Response:
    {
        "user": {...}
    }
    """
    tenant = get_current_tenant()

    with get_db_session() as db:
        user = db.query(User).filter(
            User.id == user_id,
            User.company_id == tenant.company_id
        ).first()

        if not user:
            return jsonify({'error': 'User not found'}), 404

        return jsonify({
            'user': user.to_dict()
        })


@company_bp.route('/users/<int:user_id>', methods=['PATCH'])
@require_auth
@require_admin
def update_user(user_id: int):
    """
    Update a user (admin only).

    Request body:
    {
        "full_name": "New Name",
        "role": "admin",
        "is_active": true
    }

    Response:
    {
        "user": {...},
        "message": "User updated"
    }
    """
    tenant = get_current_tenant()
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    with get_db_session() as db:
        user = db.query(User).filter(
            User.id == user_id,
            User.company_id == tenant.company_id
        ).first()

        if not user:
            return jsonify({'error': 'User not found'}), 404

        # Prevent admin from deactivating themselves
        if user.id == tenant.user_id and data.get('is_active') == False:
            return jsonify({'error': 'Cannot deactivate your own account'}), 400

        # Prevent removing last admin
        if user.id == tenant.user_id and data.get('role') and data['role'] != 'admin':
            admin_count = db.query(User).filter(
                User.company_id == tenant.company_id,
                User.role == UserRole.ADMIN,
                User.is_active == True
            ).count()

            if admin_count <= 1:
                return jsonify({'error': 'Cannot remove the last admin'}), 400

        # Update fields
        if 'full_name' in data:
            user.full_name = data['full_name']

        if 'role' in data:
            try:
                user.role = UserRole(data['role'])
            except ValueError:
                return jsonify({
                    'error': f'Invalid role: {data["role"]}. Valid roles: {[r.value for r in UserRole]}'
                }), 400

        if 'is_active' in data:
            user.is_active = data['is_active']

        db.commit()
        db.refresh(user)

        logger.info(f"User updated: {user.email} by {tenant.email}")

        return jsonify({
            'user': user.to_dict(),
            'message': 'User updated'
        })


@company_bp.route('/users/<int:user_id>', methods=['DELETE'])
@require_auth
@require_admin
def delete_user(user_id: int):
    """
    Delete a user (admin only).

    This permanently deletes the user. Use PATCH to deactivate instead.

    Response:
    {
        "message": "User deleted"
    }
    """
    tenant = get_current_tenant()

    with get_db_session() as db:
        user = db.query(User).filter(
            User.id == user_id,
            User.company_id == tenant.company_id
        ).first()

        if not user:
            return jsonify({'error': 'User not found'}), 404

        # Prevent admin from deleting themselves
        if user.id == tenant.user_id:
            return jsonify({'error': 'Cannot delete your own account'}), 400

        # Prevent deleting last admin
        if user.role == UserRole.ADMIN:
            admin_count = db.query(User).filter(
                User.company_id == tenant.company_id,
                User.role == UserRole.ADMIN,
                User.is_active == True
            ).count()

            if admin_count <= 1:
                return jsonify({'error': 'Cannot delete the last admin'}), 400

        email = user.email
        db.delete(user)
        db.commit()

        logger.info(f"User deleted: {email} by {tenant.email}")

        return jsonify({
            'message': 'User deleted'
        })


@company_bp.route('/users/<int:user_id>/reset-password', methods=['POST'])
@require_auth
@require_admin
def reset_user_password(user_id: int):
    """
    Reset a user's password (admin only).

    Request body:
    {
        "new_password": "newsecurepassword"
    }

    Response:
    {
        "message": "Password reset successfully"
    }
    """
    tenant = get_current_tenant()
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    new_password = data.get('new_password')
    if not new_password:
        return jsonify({'error': 'new_password is required'}), 400

    with get_db_session() as db:
        user = db.query(User).filter(
            User.id == user_id,
            User.company_id == tenant.company_id
        ).first()

        if not user:
            return jsonify({'error': 'User not found'}), 404

        auth_service = get_auth_service()

        try:
            auth_service.update_password(user_id, new_password, db)
        except ValueError as e:
            return jsonify({'error': str(e)}), 400

        logger.info(f"Password reset for {user.email} by {tenant.email}")

        return jsonify({
            'message': 'Password reset successfully'
        })


# ==================== Statistics ====================

@company_bp.route('/stats', methods=['GET'])
@require_auth
def get_company_stats():
    """
    Get company statistics.

    Response:
    {
        "users": {
            "total": 10,
            "active": 8,
            "by_role": {
                "admin": 2,
                "agent": 6,
                "viewer": 2
            }
        },
        "sessions": {
            "total": 100,
            "active": 3
        }
    }
    """
    from app.models.call_session import CallSession, CallStatus

    tenant = get_current_tenant()

    with get_db_session() as db:
        # User stats
        total_users = db.query(User).filter(
            User.company_id == tenant.company_id
        ).count()

        active_users = db.query(User).filter(
            User.company_id == tenant.company_id,
            User.is_active == True
        ).count()

        users_by_role = {}
        for role in UserRole:
            count = db.query(User).filter(
                User.company_id == tenant.company_id,
                User.role == role,
                User.is_active == True
            ).count()
            users_by_role[role.value] = count

        # Session stats
        total_sessions = db.query(CallSession).filter(
            CallSession.company_id == tenant.company_id
        ).count()

        active_sessions = db.query(CallSession).filter(
            CallSession.company_id == tenant.company_id,
            CallSession.status == CallStatus.ACTIVE
        ).count()

        return jsonify({
            'users': {
                'total': total_users,
                'active': active_users,
                'by_role': users_by_role
            },
            'sessions': {
                'total': total_sessions,
                'active': active_sessions
            }
        })
