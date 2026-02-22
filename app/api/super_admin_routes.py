"""
Super Admin API Routes
Platform-level administration endpoints for SUPER_ADMIN users only
"""
from flask import Blueprint, request, jsonify, g

from app.middleware.auth_middleware import (
    require_auth,
    require_super_admin,
    get_request_metadata,
)
from app.services.company_service import get_company_service, CompanyError, CompanyNotFoundError, CompanySlugExistsError
from app.services.audit_service import get_audit_service
from app.database.postgresql_session import get_db_session
from app.logging.logger import logger


super_bp = Blueprint('super', __name__, url_prefix='/api/v1/super')


# ==================== Company Management ====================

@super_bp.route('/companies', methods=['POST'])
@require_auth
@require_super_admin
def create_company():
    """
    Create a new company.

    Request body:
    {
        "slug": "acme-corp",
        "name": "ACME Corporation",
        "plan": "pro",  // optional, default: "free"
        "settings": {   // optional
            "max_agents": 20,
            "features": ["realtime", "knowledge_base"]
        }
    }

    Response:
    {
        "company": {...},
        "message": "Company created successfully"
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    slug = data.get('slug', '').strip()
    name = data.get('name', '').strip()
    plan = data.get('plan', 'free')
    settings = data.get('settings')

    if not slug:
        return jsonify({'error': 'slug is required'}), 400
    if not name:
        return jsonify({'error': 'name is required'}), 400

    context = g.tenant_context
    metadata = get_request_metadata()

    try:
        with get_db_session() as db:
            company_service = get_company_service()
            company = company_service.create_company(
                slug=slug,
                name=name,
                db=db,
                plan=plan,
                settings=settings,
                created_by_user_id=context.user_id,
                created_by_email=context.email,
                ip_address=metadata['ip_address'],
            )
            db.commit()

            return jsonify({
                'company': company.to_dict(),
                'message': 'Company created successfully'
            }), 201

    except CompanySlugExistsError as e:
        return jsonify({'error': str(e)}), 409
    except CompanyError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating company: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@super_bp.route('/companies', methods=['GET'])
@require_auth
@require_super_admin
def list_companies():
    """
    List all companies with pagination.

    Query params:
    - include_inactive: bool (default: false)
    - limit: int (default: 100)
    - offset: int (default: 0)

    Response:
    {
        "companies": [...],
        "total": 42,
        "limit": 100,
        "offset": 0
    }
    """
    include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
    limit = min(int(request.args.get('limit', 100)), 500)
    offset = int(request.args.get('offset', 0))

    try:
        with get_db_session() as db:
            company_service = get_company_service()
            companies = company_service.list_companies(
                db=db,
                include_inactive=include_inactive,
                limit=limit,
                offset=offset,
            )

            from app.models.company import Company
            total = db.query(Company).count()

            return jsonify({
                'companies': [c.to_dict() for c in companies],
                'total': total,
                'limit': limit,
                'offset': offset,
            })

    except Exception as e:
        logger.error(f"Error listing companies: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@super_bp.route('/companies/<int:company_id>', methods=['GET'])
@require_auth
@require_super_admin
def get_company(company_id: int):
    """
    Get company details with statistics.

    Response:
    {
        "company": {...},
        "stats": {...}
    }
    """
    try:
        with get_db_session() as db:
            company_service = get_company_service()
            company = company_service.get_company(company_id, db)

            if not company:
                return jsonify({'error': 'Company not found'}), 404

            stats = company_service.get_company_stats(company_id, db)

            return jsonify({
                'company': company.to_dict(),
                'stats': stats,
            })

    except Exception as e:
        logger.error(f"Error getting company {company_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@super_bp.route('/companies/<int:company_id>', methods=['PATCH'])
@require_auth
@require_super_admin
def update_company(company_id: int):
    """
    Update company details.

    Request body (all fields optional):
    {
        "name": "New Name",
        "plan": "enterprise",
        "settings": {"max_agents": 50},
        "is_active": true
    }

    Response:
    {
        "company": {...},
        "message": "Company updated successfully"
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    context = g.tenant_context
    metadata = get_request_metadata()

    # Filter allowed fields
    allowed_fields = ['name', 'plan', 'settings', 'is_active']
    updates = {k: v for k, v in data.items() if k in allowed_fields}

    if not updates:
        return jsonify({'error': 'No valid fields to update'}), 400

    try:
        with get_db_session() as db:
            company_service = get_company_service()
            company = company_service.update_company(
                company_id=company_id,
                db=db,
                updates=updates,
                updated_by_user_id=context.user_id,
                updated_by_email=context.email,
                ip_address=metadata['ip_address'],
            )
            db.commit()

            return jsonify({
                'company': company.to_dict(),
                'message': 'Company updated successfully'
            })

    except CompanyNotFoundError:
        return jsonify({'error': 'Company not found'}), 404
    except CompanyError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating company {company_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@super_bp.route('/companies/<int:company_id>', methods=['DELETE'])
@require_auth
@require_super_admin
def delete_company(company_id: int):
    """
    Deactivate or permanently delete a company.

    Query params:
    - hard_delete: bool (default: false) - If true, performs GDPR cascade delete

    Response (soft delete):
    {
        "message": "Company deactivated",
        "company_id": 123
    }

    Response (hard delete):
    {
        "message": "Company and all data permanently deleted",
        "deletion_summary": {
            "users": 5,
            "call_sessions": 100,
            ...
        }
    }
    """
    hard_delete = request.args.get('hard_delete', 'false').lower() == 'true'

    context = g.tenant_context
    metadata = get_request_metadata()

    try:
        with get_db_session() as db:
            company_service = get_company_service()

            if hard_delete:
                # GDPR-compliant permanent deletion
                summary = company_service.delete_company_gdpr(
                    company_id=company_id,
                    db=db,
                    deleted_by_user_id=context.user_id,
                    deleted_by_email=context.email,
                    ip_address=metadata['ip_address'],
                )
                db.commit()

                return jsonify({
                    'message': 'Company and all data permanently deleted',
                    'deletion_summary': summary,
                })
            else:
                # Soft delete (deactivate)
                company_service.deactivate_company(
                    company_id=company_id,
                    db=db,
                    deactivated_by_user_id=context.user_id,
                    deactivated_by_email=context.email,
                    ip_address=metadata['ip_address'],
                )
                db.commit()

                return jsonify({
                    'message': 'Company deactivated',
                    'company_id': company_id,
                })

    except CompanyNotFoundError:
        return jsonify({'error': 'Company not found'}), 404
    except CompanyError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error deleting company {company_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500


# ==================== Analytics ====================

@super_bp.route('/analytics', methods=['GET'])
@require_auth
@require_super_admin
def global_analytics():
    """
    Get platform-wide analytics and statistics.

    Response:
    {
        "companies": {"total": 10, "active": 8, "by_plan": {...}},
        "users": {"total": 100, "active": 90, "by_role": {...}},
        "sessions": {"total": 1000, "last_24h": 50},
        "activity": {"users_last_24h": 25},
        "generated_at": "2025-01-29T12:00:00Z"
    }
    """
    try:
        with get_db_session() as db:
            company_service = get_company_service()
            analytics = company_service.get_global_analytics(db)

            return jsonify(analytics)

    except Exception as e:
        logger.error(f"Error getting global analytics: {e}")
        return jsonify({'error': 'Internal server error'}), 500


# ==================== Audit Logs ====================

@super_bp.route('/audit-logs', methods=['GET'])
@require_auth
@require_super_admin
def global_audit_logs():
    """
    Get global audit logs with filtering.

    Query params:
    - limit: int (default: 100)
    - offset: int (default: 0)
    - action_type: string (optional, e.g., "user.create")
    - company_id: int (optional, filter by company)
    - actor_user_id: int (optional, filter by actor)

    Response:
    {
        "audit_logs": [...],
        "total": 500,
        "limit": 100,
        "offset": 0
    }
    """
    limit = min(int(request.args.get('limit', 100)), 500)
    offset = int(request.args.get('offset', 0))
    action_type = request.args.get('action_type')
    company_id = request.args.get('company_id', type=int)
    actor_user_id = request.args.get('actor_user_id', type=int)

    try:
        with get_db_session() as db:
            audit_service = get_audit_service()
            logs = audit_service.get_global_audit_logs(
                db=db,
                limit=limit,
                offset=offset,
                action_type=action_type,
                company_id=company_id,
                actor_user_id=actor_user_id,
            )
            total = audit_service.count_global_logs(db, company_id=company_id)

            return jsonify({
                'audit_logs': [log.to_dict() for log in logs],
                'total': total,
                'limit': limit,
                'offset': offset,
            })

    except Exception as e:
        logger.error(f"Error getting global audit logs: {e}")
        return jsonify({'error': 'Internal server error'}), 500


# ==================== System Status ====================

@super_bp.route('/system/status', methods=['GET'])
@require_auth
@require_super_admin
def system_status():
    """
    Get system status including API key configuration.

    Response:
    {
        "deepgram": {"configured": true},
        "openai": {"configured": true},
        "twilio": {"configured": true},
        "groq": {"configured": true}
    }
    """
    import os

    return jsonify({
        'deepgram': {
            'configured': bool(os.environ.get('DEEPGRAM_API_KEY'))
        },
        'openai': {
            'configured': bool(os.environ.get('OPENAI_API_KEY') or os.environ.get('AZURE_OPENAI_API_KEY'))
        },
        'twilio': {
            'configured': bool(
                os.environ.get('TWILIO_ACCOUNT_SID') and
                os.environ.get('TWILIO_AUTH_TOKEN')
            )
        },
        'groq': {
            'configured': bool(os.environ.get('GROQ_API_KEY'))
        }
    })
