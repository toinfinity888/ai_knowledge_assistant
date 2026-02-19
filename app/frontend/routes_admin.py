"""
Admin Panel Routes

Web-based admin interface with role-based access control.
"""
import os
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, flash

from app.database.postgresql_session import get_db_session
from app.models.user import User, UserRole
from app.models.company import Company
from app.models.invitation import Invitation
from app.models.audit_log import AuditLog, ActionType, TargetType
from app.services.company_service import get_company_service
from app.services.invitation_service import get_invitation_service
from app.services.audit_service import get_audit_service
from app.services.auth_service import get_auth_service
from app.services.domain_schema_service import get_domain_schema_service
from app.logging.logger import logger


template_dir = os.path.join(os.path.dirname(__file__), 'templates')
admin_panel_bp = Blueprint("admin_panel", __name__, template_folder=template_dir, url_prefix='/admin')


# ==================== Auth Decorators ====================

def login_required(f):
    """Require user to be logged in."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('front.login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Require user to be ADMIN or SUPER_ADMIN."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('front.login'))

        role = session.get('role', '')
        if role not in ['admin', 'super_admin']:
            return render_template(
                'admin/dashboard.html',
                active_page='dashboard',
                error='Access denied. Admin privileges required.',
                stats={}
            )
        return f(*args, **kwargs)
    return decorated_function


def super_admin_required(f):
    """Require user to be SUPER_ADMIN."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('front.login'))

        role = session.get('role', '')
        if role != 'super_admin':
            return render_template(
                'admin/dashboard.html',
                active_page='dashboard',
                error='Access denied. Super admin privileges required.',
                stats={}
            )
        return f(*args, **kwargs)
    return decorated_function


# ==================== Dashboard ====================

@admin_panel_bp.route('/')
@login_required
def dashboard():
    """Admin dashboard with role-based stats."""
    role = session.get('role', 'viewer')
    company_id = session.get('company_id')
    is_super = role == 'super_admin'
    is_admin = role in ['super_admin', 'admin']

    stats = {}
    company = None
    recent_logs = []

    try:
        with get_db_session() as db:
            if is_super:
                # SUPER_ADMIN: Global stats
                company_service = get_company_service()
                analytics = company_service.get_global_analytics(db)

                stats = {
                    'companies_total': analytics.get('companies', {}).get('total', 0),
                    'companies_active': analytics.get('companies', {}).get('active', 0),
                    'users_total': analytics.get('users', {}).get('total', 0),
                    'sessions_total': analytics.get('sessions', {}).get('total', 0),
                    'by_plan': analytics.get('companies', {}).get('by_plan', {}),
                    'by_role': analytics.get('users', {}).get('by_role', {}),
                }

                # Recent global audit logs
                audit_service = get_audit_service()
                recent_logs = audit_service.get_global_audit_logs(db, limit=5)

            elif is_admin and company_id:
                # ADMIN: Company-scoped stats
                company = db.query(Company).filter(Company.id == company_id).first()

                users_query = db.query(User).filter(User.company_id == company_id)
                users_total = users_query.count()
                users_active = users_query.filter(User.is_active == True).count()

                # Count by role
                by_role = {}
                for r in [UserRole.ADMIN, UserRole.AGENT, UserRole.VIEWER]:
                    count = db.query(User).filter(
                        User.company_id == company_id,
                        User.role == r
                    ).count()
                    if count > 0:
                        by_role[r.value] = count

                # Pending invitations
                invitations_pending = db.query(Invitation).filter(
                    Invitation.company_id == company_id,
                    Invitation.is_accepted == False,
                ).count()

                stats = {
                    'users_total': users_total,
                    'users_active': users_active,
                    'invitations_pending': invitations_pending,
                    'sessions_total': 0,  # TODO: Implement sessions count
                    'by_role': by_role,
                }

                # Recent company audit logs
                audit_service = get_audit_service()
                recent_logs = audit_service.get_company_audit_logs(company_id, db, limit=5)

            else:
                # AGENT/VIEWER: Personal stats
                stats = {
                    'my_sessions': 0,  # TODO: Implement
                    'sessions_today': 0,  # TODO: Implement
                }

    except Exception as e:
        logger.error(f"Error loading dashboard stats: {e}")

    return render_template(
        'admin/dashboard.html',
        active_page='dashboard',
        stats=stats,
        company=company,
        recent_logs=recent_logs
    )


# ==================== Companies (SUPER_ADMIN only) ====================

@admin_panel_bp.route('/companies')
@super_admin_required
def companies():
    """List all companies."""
    limit = min(int(request.args.get('limit', 50)), 100)
    offset = int(request.args.get('offset', 0))

    companies_list = []
    total = 0

    try:
        with get_db_session() as db:
            company_service = get_company_service()
            companies_list = company_service.list_companies(
                db=db,
                include_inactive=True,
                limit=limit,
                offset=offset
            )

            # Get user counts for each company
            for company in companies_list:
                company.user_count = db.query(User).filter(User.company_id == company.id).count()

            total = db.query(Company).count()

    except Exception as e:
        logger.error(f"Error listing companies: {e}")

    return render_template(
        'admin/companies.html',
        active_page='companies',
        companies=companies_list,
        total=total,
        limit=limit,
        offset=offset
    )


@admin_panel_bp.route('/companies/create', methods=['POST'])
@super_admin_required
def create_company():
    """Create a new company."""
    name = request.form.get('name', '').strip()
    slug = request.form.get('slug', '').strip().lower()
    plan = request.form.get('plan', 'pro')

    if not name or not slug:
        return redirect(url_for('admin_panel.companies') + '?error=Name+and+slug+required')

    try:
        with get_db_session() as db:
            company_service = get_company_service()
            company = company_service.create_company(
                slug=slug,
                name=name,
                db=db,
                plan=plan,
                created_by_user_id=session.get('user_id'),
                created_by_email=session.get('user_email'),
                ip_address=request.remote_addr
            )
            db.commit()
            logger.info(f"Company created via admin panel: {company.slug}")

    except Exception as e:
        logger.error(f"Error creating company: {e}")
        return redirect(url_for('admin_panel.companies') + f'?error={str(e)}')

    return redirect(url_for('admin_panel.companies') + '?success=Company+created+successfully')


@admin_panel_bp.route('/companies/update', methods=['POST'])
@super_admin_required
def update_company():
    """Update company details."""
    company_id = request.form.get('company_id', type=int)
    name = request.form.get('name', '').strip()
    plan = request.form.get('plan', '')
    is_active = request.form.get('is_active') == 'true'

    if not company_id:
        return redirect(url_for('admin_panel.companies') + '?error=Invalid+company')

    try:
        with get_db_session() as db:
            company_service = get_company_service()
            updates = {}
            if name:
                updates['name'] = name
            if plan:
                updates['plan'] = plan
            updates['is_active'] = is_active

            company_service.update_company(
                company_id=company_id,
                db=db,
                updates=updates,
                updated_by_user_id=session.get('user_id'),
                updated_by_email=session.get('user_email'),
                ip_address=request.remote_addr
            )
            db.commit()

    except Exception as e:
        logger.error(f"Error updating company: {e}")
        return redirect(url_for('admin_panel.companies') + f'?error={str(e)}')

    return redirect(url_for('admin_panel.companies') + '?success=Company+updated')


@admin_panel_bp.route('/companies/deactivate', methods=['POST'])
@super_admin_required
def deactivate_company():
    """Deactivate a company."""
    company_id = request.form.get('company_id', type=int)

    if not company_id:
        return redirect(url_for('admin_panel.companies') + '?error=Invalid+company')

    try:
        with get_db_session() as db:
            company_service = get_company_service()
            company_service.deactivate_company(
                company_id=company_id,
                db=db,
                deactivated_by_user_id=session.get('user_id'),
                deactivated_by_email=session.get('user_email'),
                ip_address=request.remote_addr
            )
            db.commit()

    except Exception as e:
        logger.error(f"Error deactivating company: {e}")
        return redirect(url_for('admin_panel.companies') + f'?error={str(e)}')

    return redirect(url_for('admin_panel.companies') + '?success=Company+deactivated')


@admin_panel_bp.route('/companies/activate', methods=['POST'])
@super_admin_required
def activate_company():
    """Activate a company."""
    company_id = request.form.get('company_id', type=int)

    if not company_id:
        return redirect(url_for('admin_panel.companies') + '?error=Invalid+company')

    try:
        with get_db_session() as db:
            company_service = get_company_service()
            company_service.update_company(
                company_id=company_id,
                db=db,
                updates={'is_active': True},
                updated_by_user_id=session.get('user_id'),
                updated_by_email=session.get('user_email'),
                ip_address=request.remote_addr
            )
            db.commit()

    except Exception as e:
        logger.error(f"Error activating company: {e}")
        return redirect(url_for('admin_panel.companies') + f'?error={str(e)}')

    return redirect(url_for('admin_panel.companies') + '?success=Company+activated')


# ==================== Users ====================

@admin_panel_bp.route('/users')
@admin_required
def users():
    """List users (company-scoped for ADMIN, all for SUPER_ADMIN)."""
    role = session.get('role', '')
    is_super = role == 'super_admin'
    company_id = session.get('company_id')

    limit = min(int(request.args.get('limit', 50)), 100)
    offset = int(request.args.get('offset', 0))

    # SUPER_ADMIN can filter by company
    selected_company_id = None
    if is_super:
        selected_company_id = request.args.get('company_id', type=int)

    users_list = []
    companies_list = []
    total = 0

    try:
        with get_db_session() as db:
            query = db.query(User)

            if is_super:
                # Get all companies for filter dropdown
                companies_list = db.query(Company).filter(Company.is_active == True).all()

                if selected_company_id:
                    query = query.filter(User.company_id == selected_company_id)
            else:
                # ADMIN: only own company
                query = query.filter(User.company_id == company_id)

            total = query.count()
            users_list = query.order_by(User.created_at.desc()).offset(offset).limit(limit).all()

    except Exception as e:
        logger.error(f"Error listing users: {e}")

    return render_template(
        'admin/users.html',
        active_page='users',
        users=users_list,
        companies=companies_list,
        selected_company_id=selected_company_id,
        total=total,
        limit=limit,
        offset=offset
    )


@admin_panel_bp.route('/users/update', methods=['POST'])
@admin_required
def update_user():
    """Update user role and status."""
    user_id = request.form.get('user_id', type=int)
    new_role = request.form.get('role', '')
    is_active = request.form.get('is_active') == 'true'

    current_role = session.get('role', '')
    current_user_id = session.get('user_id')
    company_id = session.get('company_id')

    if not user_id:
        return redirect(url_for('admin_panel.users') + '?error=Invalid+user')

    # Prevent self-modification
    if user_id == current_user_id:
        return redirect(url_for('admin_panel.users') + '?error=Cannot+modify+your+own+account')

    try:
        with get_db_session() as db:
            user = db.query(User).filter(User.id == user_id).first()

            if not user:
                return redirect(url_for('admin_panel.users') + '?error=User+not+found')

            # ADMIN can only modify users in their company
            if current_role != 'super_admin' and user.company_id != company_id:
                return redirect(url_for('admin_panel.users') + '?error=Access+denied')

            # Validate role change
            if new_role:
                try:
                    role_enum = UserRole(new_role)

                    # Non-super_admin cannot assign super_admin role
                    if current_role != 'super_admin' and role_enum == UserRole.SUPER_ADMIN:
                        return redirect(url_for('admin_panel.users') + '?error=Cannot+assign+super_admin+role')

                    # ADMIN cannot assign ADMIN role
                    if current_role == 'admin' and role_enum == UserRole.ADMIN:
                        return redirect(url_for('admin_panel.users') + '?error=Cannot+assign+admin+role')

                    user.role = role_enum
                except ValueError:
                    return redirect(url_for('admin_panel.users') + '?error=Invalid+role')

            user.is_active = is_active
            db.commit()

            # Log the action
            audit_service = get_audit_service()
            audit_service.log_action(
                action_type='user.update',
                actor_user_id=current_user_id,
                actor_email=session.get('user_email'),
                target_type='user',
                target_id=user_id,
                company_id=user.company_id,
                db=db,
                description=f"Updated user {user.email}: role={new_role}, active={is_active}",
                ip_address=request.remote_addr
            )
            db.commit()

    except Exception as e:
        logger.error(f"Error updating user: {e}")
        return redirect(url_for('admin_panel.users') + f'?error={str(e)}')

    return redirect(url_for('admin_panel.users') + '?success=User+updated')


@admin_panel_bp.route('/users/deactivate', methods=['POST'])
@admin_required
def deactivate_user():
    """Deactivate a user."""
    user_id = request.form.get('user_id', type=int)
    current_role = session.get('role', '')
    company_id = session.get('company_id')

    if not user_id:
        return redirect(url_for('admin_panel.users') + '?error=Invalid+user')

    if user_id == session.get('user_id'):
        return redirect(url_for('admin_panel.users') + '?error=Cannot+deactivate+yourself')

    try:
        with get_db_session() as db:
            user = db.query(User).filter(User.id == user_id).first()

            if not user:
                return redirect(url_for('admin_panel.users') + '?error=User+not+found')

            if current_role != 'super_admin' and user.company_id != company_id:
                return redirect(url_for('admin_panel.users') + '?error=Access+denied')

            user.is_active = False
            db.commit()

    except Exception as e:
        logger.error(f"Error deactivating user: {e}")
        return redirect(url_for('admin_panel.users') + f'?error={str(e)}')

    return redirect(url_for('admin_panel.users') + '?success=User+deactivated')


@admin_panel_bp.route('/users/activate', methods=['POST'])
@admin_required
def activate_user():
    """Activate a user."""
    user_id = request.form.get('user_id', type=int)
    current_role = session.get('role', '')
    company_id = session.get('company_id')

    if not user_id:
        return redirect(url_for('admin_panel.users') + '?error=Invalid+user')

    try:
        with get_db_session() as db:
            user = db.query(User).filter(User.id == user_id).first()

            if not user:
                return redirect(url_for('admin_panel.users') + '?error=User+not+found')

            if current_role != 'super_admin' and user.company_id != company_id:
                return redirect(url_for('admin_panel.users') + '?error=Access+denied')

            user.is_active = True
            db.commit()

    except Exception as e:
        logger.error(f"Error activating user: {e}")
        return redirect(url_for('admin_panel.users') + f'?error={str(e)}')

    return redirect(url_for('admin_panel.users') + '?success=User+activated')


# ==================== Invitations ====================

@admin_panel_bp.route('/invitations')
@admin_required
def invitations():
    """List invitations."""
    role = session.get('role', '')
    is_super = role == 'super_admin'
    company_id = session.get('company_id')

    limit = min(int(request.args.get('limit', 50)), 100)
    offset = int(request.args.get('offset', 0))

    invitations_list = []
    companies_list = []
    total = 0
    created_invitation = None

    try:
        with get_db_session() as db:
            query = db.query(Invitation)

            if is_super:
                # Get all companies for create modal
                companies_list = db.query(Company).filter(Company.is_active == True).all()
            else:
                # ADMIN: only own company
                query = query.filter(Invitation.company_id == company_id)

            total = query.count()
            invitations_list = query.order_by(Invitation.created_at.desc()).offset(offset).limit(limit).all()

            # Check for recently created invitation
            created_token = request.args.get('created_token')
            if created_token:
                created_invitation = db.query(Invitation).filter(
                    Invitation.token == created_token
                ).first()

    except Exception as e:
        logger.error(f"Error listing invitations: {e}")

    return render_template(
        'admin/invitations.html',
        active_page='invitations',
        invitations=invitations_list,
        companies=companies_list,
        created_invitation=created_invitation,
        total=total,
        limit=limit,
        offset=offset
    )


@admin_panel_bp.route('/invitations/create', methods=['POST'])
@admin_required
def create_invitation():
    """Create a new invitation."""
    email = request.form.get('email', '').strip().lower()
    role_str = request.form.get('role', '').strip()
    expires_days = int(request.form.get('expires_days', 7))

    current_role = session.get('role', '')
    is_super = current_role == 'super_admin'
    company_id = session.get('company_id')

    if not email or not role_str:
        return redirect(url_for('admin_panel.invitations') + '?error=Email+and+role+required')

    # Determine company_id
    if is_super:
        target_company_id = request.form.get('company_id', type=int)
        if not target_company_id:
            return redirect(url_for('admin_panel.invitations') + '?error=Company+required')
    else:
        target_company_id = company_id

    try:
        role = UserRole(role_str)

        # ADMIN cannot invite ADMIN or higher
        if current_role == 'admin' and role in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
            return redirect(url_for('admin_panel.invitations') + '?error=Cannot+invite+admin+users')

        with get_db_session() as db:
            invitation_service = get_invitation_service()
            invitation, token = invitation_service.create_invitation(
                email=email,
                role=role,
                company_id=target_company_id,
                created_by_user_id=session.get('user_id'),
                db=db,
                expires_days=expires_days,
                ip_address=request.remote_addr
            )
            db.commit()

            logger.info(f"Invitation created via admin panel: {email}")

            # Redirect with created token to show the link
            return redirect(url_for('admin_panel.invitations') + f'?success=Invitation+created&created_token={token}')

    except ValueError as e:
        return redirect(url_for('admin_panel.invitations') + f'?error={str(e)}')
    except Exception as e:
        logger.error(f"Error creating invitation: {e}")
        return redirect(url_for('admin_panel.invitations') + f'?error={str(e)}')


@admin_panel_bp.route('/invitations/revoke', methods=['POST'])
@admin_required
def revoke_invitation():
    """Revoke an invitation."""
    invitation_id = request.form.get('invitation_id', type=int)
    current_role = session.get('role', '')
    company_id = session.get('company_id')

    if not invitation_id:
        return redirect(url_for('admin_panel.invitations') + '?error=Invalid+invitation')

    try:
        with get_db_session() as db:
            invitation = db.query(Invitation).filter(Invitation.id == invitation_id).first()

            if not invitation:
                return redirect(url_for('admin_panel.invitations') + '?error=Invitation+not+found')

            # ADMIN can only revoke invitations for their company
            if current_role != 'super_admin' and invitation.company_id != company_id:
                return redirect(url_for('admin_panel.invitations') + '?error=Access+denied')

            invitation_service = get_invitation_service()
            invitation_service.revoke_invitation(
                invitation_id=invitation_id,
                company_id=invitation.company_id,
                revoked_by_user_id=session.get('user_id'),
                db=db,
                ip_address=request.remote_addr
            )
            db.commit()

    except Exception as e:
        logger.error(f"Error revoking invitation: {e}")
        return redirect(url_for('admin_panel.invitations') + f'?error={str(e)}')

    return redirect(url_for('admin_panel.invitations') + '?success=Invitation+revoked')


# ==================== Audit Logs ====================

@admin_panel_bp.route('/audit-logs')
@admin_required
def audit_logs():
    """View audit logs."""
    role = session.get('role', '')
    is_super = role == 'super_admin'
    company_id = session.get('company_id')

    limit = min(int(request.args.get('limit', 50)), 100)
    offset = int(request.args.get('offset', 0))
    selected_action = request.args.get('action_type', '')
    selected_company_id = request.args.get('company_id', type=int) if is_super else None

    logs = []
    companies_list = []
    total = 0

    try:
        with get_db_session() as db:
            audit_service = get_audit_service()

            if is_super:
                # Get all companies for filter
                companies_list = db.query(Company).all()

                logs = audit_service.get_global_audit_logs(
                    db=db,
                    limit=limit,
                    offset=offset,
                    action_type=selected_action if selected_action else None,
                    company_id=selected_company_id
                )
                total = audit_service.count_global_logs(db, company_id=selected_company_id)
            else:
                logs = audit_service.get_company_audit_logs(
                    company_id=company_id,
                    db=db,
                    limit=limit,
                    offset=offset,
                    action_type=selected_action if selected_action else None
                )
                total = audit_service.count_company_logs(company_id, db)

    except Exception as e:
        logger.error(f"Error loading audit logs: {e}")

    return render_template(
        'admin/audit_logs.html',
        active_page='audit_logs',
        logs=logs,
        companies=companies_list,
        selected_action=selected_action,
        selected_company_id=selected_company_id,
        total=total,
        limit=limit,
        offset=offset
    )


# ==================== AI Decision Logs ====================

@admin_panel_bp.route('/ai-decision-logs')
@admin_required
def ai_decision_logs():
    """View AI decision logs (agent_actions from gatekeeper)."""
    from sqlalchemy.orm import joinedload
    from app.models.call_session import AgentAction, CallSession

    role = session.get('role', '')
    is_super = role == 'super_admin'
    company_id = session.get('company_id')

    limit = min(int(request.args.get('limit', 50)), 100)
    offset = int(request.args.get('offset', 0))
    selected_agent = request.args.get('agent', '')
    selected_status = request.args.get('status', '')

    actions = []
    total = 0

    try:
        with get_db_session() as db:
            # Base query with join to CallSession for company filtering
            # Use joinedload to eagerly load session for session_id string
            query = db.query(AgentAction).join(CallSession).options(
                joinedload(AgentAction.session)
            )

            # Filter by company (non-super_admin sees only their company)
            if not is_super:
                query = query.filter(CallSession.company_id == company_id)

            # Apply filters
            if selected_agent:
                query = query.filter(AgentAction.agent_name == selected_agent)
            if selected_status:
                query = query.filter(AgentAction.status == selected_status)

            # Get total count (need separate query without joinedload for count)
            count_query = db.query(AgentAction).join(CallSession)
            if not is_super:
                count_query = count_query.filter(CallSession.company_id == company_id)
            if selected_agent:
                count_query = count_query.filter(AgentAction.agent_name == selected_agent)
            if selected_status:
                count_query = count_query.filter(AgentAction.status == selected_status)
            total = count_query.count()

            # Get paginated results ordered by timestamp desc
            actions = query.order_by(AgentAction.timestamp.desc()).offset(offset).limit(limit).all()

            # Eagerly access all needed attributes to avoid detached instance errors
            for action in actions:
                _ = action.id, action.agent_name, action.action_type
                _ = action.input_data, action.output_data, action.status
                _ = action.confidence, action.processing_time_ms, action.timestamp
                # Access session.session_id (the string UUID)
                if action.session:
                    _ = action.session.session_id

    except Exception as e:
        logger.error(f"Error loading AI decision logs: {e}")

    return render_template(
        'admin/ai_decision_logs.html',
        active_page='ai_decision_logs',
        actions=actions,
        selected_agent=selected_agent,
        selected_status=selected_status,
        total=total,
        limit=limit,
        offset=offset
    )


# ==================== LLM Prompts ====================

@admin_panel_bp.route('/prompts')
@admin_required
def prompts():
    """View and edit LLM prompts."""
    from app.services.prompt_service import get_prompt_service

    company_id = session.get('company_id')

    # Super admin can view/edit prompts for any company (default to first company)
    # For now, super_admin uses company_id 1 if they don't have one
    if not company_id:
        company_id = 1

    prompt_service = get_prompt_service()
    prompts_list = prompt_service.get_all_prompts(company_id)

    return render_template(
        'admin/prompts.html',
        active_page='prompts',
        prompts=prompts_list,
    )


@admin_panel_bp.route('/prompts/save', methods=['POST'])
@admin_required
def save_prompt():
    """Save a custom prompt."""
    from flask import jsonify
    from app.services.prompt_service import get_prompt_service
    from app.models.prompt_template import DEFAULT_PROMPTS

    company_id = session.get('company_id')
    user_id = session.get('user_id')

    if not company_id:
        company_id = 1

    try:
        data = request.get_json()
        prompt_key = data.get('prompt_key')
        language = data.get('language', 'en')
        system_prompt = data.get('system_prompt', '').strip()

        if not prompt_key or not system_prompt:
            return jsonify({'success': False, 'error': 'Missing required fields'})

        # Get name from defaults
        name = prompt_key.replace('_', ' ').title()
        description = None
        if prompt_key in DEFAULT_PROMPTS and language in DEFAULT_PROMPTS[prompt_key]:
            name = DEFAULT_PROMPTS[prompt_key][language].get('name', name)
            description = DEFAULT_PROMPTS[prompt_key][language].get('description')

        prompt_service = get_prompt_service()
        prompt_service.save_prompt(
            company_id=company_id,
            prompt_key=prompt_key,
            language=language,
            name=name,
            system_prompt=system_prompt,
            description=description,
            user_id=user_id,
        )

        # Audit log
        audit_service = get_audit_service()
        with get_db_session() as db:
            audit_service.log_action(
                action_type=ActionType.SETTINGS_UPDATE,
                target_type=TargetType.SETTINGS,
                target_id=None,
                actor_user_id=user_id,
                actor_email=session.get('user_email', 'unknown'),
                company_id=company_id,
                details={'prompt_key': prompt_key, 'language': language},
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', '')[:500],
                db=db,
            )

        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"Error saving prompt: {e}")
        return jsonify({'success': False, 'error': str(e)})


@admin_panel_bp.route('/prompts/reset', methods=['POST'])
@admin_required
def reset_prompt():
    """Reset a prompt to default."""
    from flask import jsonify
    from app.services.prompt_service import get_prompt_service

    company_id = session.get('company_id')
    user_id = session.get('user_id')

    if not company_id:
        company_id = 1

    try:
        data = request.get_json()
        prompt_key = data.get('prompt_key')
        language = data.get('language', 'en')

        if not prompt_key:
            return jsonify({'success': False, 'error': 'Missing prompt_key'})

        prompt_service = get_prompt_service()
        prompt_service.reset_to_default(
            company_id=company_id,
            prompt_key=prompt_key,
            language=language,
        )

        # Audit log
        audit_service = get_audit_service()
        with get_db_session() as db:
            audit_service.log_action(
                action_type=ActionType.SETTINGS_UPDATE,
                target_type=TargetType.SETTINGS,
                target_id=None,
                actor_user_id=user_id,
                actor_email=session.get('user_email', 'unknown'),
                company_id=company_id,
                details={'prompt_key': prompt_key, 'language': language, 'action': 'reset_to_default'},
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', '')[:500],
                db=db,
            )

        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"Error resetting prompt: {e}")
        return jsonify({'success': False, 'error': str(e)})


# ==================== Settings ====================

@admin_panel_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """Account settings page with sidebar layout."""
    error = None
    success = None
    user_data = None
    company_name = session.get('company_name', 'Platform')
    company_plan = 'Standard'
    user_role = session.get('role', 'agent')

    # Check for query string messages
    if request.args.get('success'):
        success = request.args.get('success').replace('+', ' ')
    if request.args.get('error'):
        error = request.args.get('error').replace('+', ' ')

    auth_service = get_auth_service()

    try:
        with get_db_session() as db:
            user = db.query(User).filter(User.id == session.get('user_id')).first()

            if not user:
                session.clear()
                return redirect(url_for('front.login'))

            # Get company details
            if user.company:
                company_name = user.company.name
                company_plan = user.company.plan or 'Standard'

            if request.method == 'POST':
                action = request.form.get('action')

                if action == 'update_profile':
                    # Update personal information
                    full_name = request.form.get('full_name', '').strip()

                    if not full_name:
                        error = 'Full name is required'
                    else:
                        user.full_name = full_name
                        db.commit()
                        session['user_name'] = full_name
                        success = 'Profile updated successfully'

                elif action == 'change_password':
                    # Change password
                    current_password = request.form.get('current_password', '')
                    new_password = request.form.get('new_password', '')
                    confirm_password = request.form.get('confirm_password', '')

                    if not current_password or not new_password or not confirm_password:
                        error = 'All password fields are required'
                    elif new_password != confirm_password:
                        error = 'New passwords do not match'
                    elif len(new_password) < 8:
                        error = 'Password must be at least 8 characters'
                    elif not auth_service.verify_password(current_password, user.password_hash):
                        error = 'Current password is incorrect'
                    else:
                        user.password_hash = auth_service.hash_password(new_password)
                        db.commit()
                        success = 'Password changed successfully'

            # Create a simple user dict for template
            user_data = {
                'full_name': user.full_name,
                'email': user.email
            }

    except Exception as e:
        logger.error(f"Error in settings page: {e}")
        error = 'An error occurred. Please try again.'

    return render_template(
        'admin/settings.html',
        active_page='settings',
        user=user_data,
        company_name=company_name,
        company_plan=company_plan,
        user_role=user_role,
        error=error,
        success=success
    )


# ==================== Domain Schemas ====================

@admin_panel_bp.route('/domain-schemas')
@admin_required
def domain_schemas():
    """List domain schemas for the company."""
    role = session.get('role', '')
    is_super = role == 'super_admin'
    company_id = session.get('company_id')

    schemas_list = []
    selected_company_id = None

    if is_super:
        selected_company_id = request.args.get('company_id', type=int)

    try:
        with get_db_session() as db:
            schema_service = get_domain_schema_service()
            target_company_id = selected_company_id if is_super and selected_company_id else company_id

            if target_company_id:
                schemas_list = schema_service.get_schemas_for_company(
                    target_company_id, db, active_only=False
                )

    except Exception as e:
        logger.error(f"Error listing domain schemas: {e}")

    return render_template(
        'admin/domain_schemas.html',
        active_page='domain_schemas',
        schemas=schemas_list,
        selected_company_id=selected_company_id,
    )


@admin_panel_bp.route('/domain-schemas/create', methods=['POST'])
@admin_required
def create_domain_schema():
    """Create a new domain schema."""
    name = request.form.get('name', '').strip()
    slug = request.form.get('slug', '').strip().lower().replace(' ', '_')
    description = request.form.get('description', '').strip()
    company_id = session.get('company_id')

    if not name or not slug:
        return redirect(url_for('admin_panel.domain_schemas') + '?error=Name+and+slug+required')

    try:
        with get_db_session() as db:
            schema_service = get_domain_schema_service()
            new_schema = schema_service.create_schema(
                company_id=company_id,
                name=name,
                slug=slug,
                description=description or None,
                db=db,
            )

            # Audit log
            audit_service = get_audit_service()
            audit_service.log_action(
                action_type=ActionType.DOMAIN_SCHEMA_CREATE,
                target_type=TargetType.DOMAIN_SCHEMA,
                target_id=new_schema.id if new_schema else None,
                actor_user_id=session.get('user_id'),
                actor_email=session.get('user_email', 'unknown'),
                company_id=company_id,
                details={"name": name, "slug": slug},
                ip_address=request.remote_addr,
                db=db,
            )
            db.commit()

    except Exception as e:
        logger.error(f"Error creating domain schema: {e}")
        return redirect(url_for('admin_panel.domain_schemas') + f'?error={str(e)}')

    return redirect(url_for('admin_panel.domain_schemas') + '?success=Schema+created')


@admin_panel_bp.route('/domain-schemas/update', methods=['POST'])
@admin_required
def update_domain_schema():
    """Update a domain schema."""
    schema_id = request.form.get('schema_id', type=int)
    company_id = session.get('company_id')

    if not schema_id:
        return redirect(url_for('admin_panel.domain_schemas') + '?error=Invalid+schema')

    updates = {}
    for key in ('name', 'slug', 'description'):
        val = request.form.get(key, '').strip()
        if val:
            updates[key] = val
    if 'is_active' in request.form:
        updates['is_active'] = request.form.get('is_active') == 'true'

    try:
        with get_db_session() as db:
            schema_service = get_domain_schema_service()
            schema_service.update_schema(schema_id, company_id, updates, db)

            # Audit log
            audit_service = get_audit_service()
            audit_service.log_action(
                action_type=ActionType.DOMAIN_SCHEMA_UPDATE,
                target_type=TargetType.DOMAIN_SCHEMA,
                target_id=schema_id,
                actor_user_id=session.get('user_id'),
                actor_email=session.get('user_email', 'unknown'),
                company_id=company_id,
                details={"updates": updates},
                ip_address=request.remote_addr,
                db=db,
            )
            db.commit()

    except Exception as e:
        logger.error(f"Error updating domain schema: {e}")
        return redirect(url_for('admin_panel.domain_schemas') + f'?error={str(e)}')

    return redirect(url_for('admin_panel.domain_schemas') + '?success=Schema+updated')


@admin_panel_bp.route('/domain-schemas/delete', methods=['POST'])
@admin_required
def delete_domain_schema():
    """Delete a domain schema."""
    schema_id = request.form.get('schema_id', type=int)
    company_id = session.get('company_id')

    if not schema_id:
        return redirect(url_for('admin_panel.domain_schemas') + '?error=Invalid+schema')

    try:
        with get_db_session() as db:
            schema_service = get_domain_schema_service()
            schema_service.delete_schema(schema_id, company_id, db)

            # Audit log
            audit_service = get_audit_service()
            audit_service.log_action(
                action_type=ActionType.DOMAIN_SCHEMA_DELETE,
                target_type=TargetType.DOMAIN_SCHEMA,
                target_id=schema_id,
                actor_user_id=session.get('user_id'),
                actor_email=session.get('user_email', 'unknown'),
                company_id=company_id,
                details={},
                ip_address=request.remote_addr,
                db=db,
            )
            db.commit()

    except Exception as e:
        logger.error(f"Error deleting domain schema: {e}")
        return redirect(url_for('admin_panel.domain_schemas') + f'?error={str(e)}')

    return redirect(url_for('admin_panel.domain_schemas') + '?success=Schema+deleted')


@admin_panel_bp.route('/domain-schemas/fields/create', methods=['POST'])
@admin_required
def create_schema_field():
    """Add a field to a domain schema."""
    schema_id = request.form.get('schema_id', type=int)
    name = request.form.get('name', '').strip()
    slug = request.form.get('slug', '').strip().lower().replace(' ', '_')
    description = request.form.get('description', '').strip()
    field_type = request.form.get('field_type', 'text')
    is_required = request.form.get('is_required') == 'true'
    options_raw = request.form.get('options', '').strip()

    if not schema_id or not name or not slug:
        return redirect(url_for('admin_panel.domain_schemas') + '?error=Missing+required+fields')

    options = [o.strip() for o in options_raw.split(',') if o.strip()] if options_raw else []

    try:
        with get_db_session() as db:
            schema_service = get_domain_schema_service()
            new_field = schema_service.add_field(
                schema_id=schema_id,
                name=name,
                slug=slug,
                description=description or None,
                field_type=field_type,
                is_required=is_required,
                options=options,
                db=db,
            )

            # Audit log
            audit_service = get_audit_service()
            audit_service.log_action(
                action_type=ActionType.DOMAIN_SCHEMA_FIELD_CREATE,
                target_type=TargetType.DOMAIN_SCHEMA_FIELD,
                target_id=new_field.id if new_field else None,
                actor_user_id=session.get('user_id'),
                actor_email=session.get('user_email', 'unknown'),
                company_id=session.get('company_id'),
                details={"schema_id": schema_id, "name": name, "slug": slug, "is_required": is_required},
                ip_address=request.remote_addr,
                db=db,
            )
            db.commit()

    except Exception as e:
        logger.error(f"Error creating schema field: {e}")
        return redirect(url_for('admin_panel.domain_schemas') + f'?error={str(e)}')

    return redirect(url_for('admin_panel.domain_schemas') + '?success=Field+added')


@admin_panel_bp.route('/domain-schemas/fields/update', methods=['POST'])
@admin_required
def update_schema_field():
    """Update a schema field."""
    field_id = request.form.get('field_id', type=int)

    if not field_id:
        return redirect(url_for('admin_panel.domain_schemas') + '?error=Invalid+field')

    updates = {}
    for key in ('name', 'slug', 'description', 'field_type'):
        val = request.form.get(key, '').strip()
        if val:
            updates[key] = val
    if 'is_required' in request.form:
        updates['is_required'] = request.form.get('is_required') == 'true'
    options_raw = request.form.get('options', '').strip()
    if options_raw:
        updates['options'] = [o.strip() for o in options_raw.split(',') if o.strip()]

    try:
        with get_db_session() as db:
            schema_service = get_domain_schema_service()
            schema_service.update_field(field_id, updates, db)

            # Audit log
            audit_service = get_audit_service()
            audit_service.log_action(
                action_type=ActionType.DOMAIN_SCHEMA_FIELD_UPDATE,
                target_type=TargetType.DOMAIN_SCHEMA_FIELD,
                target_id=field_id,
                actor_user_id=session.get('user_id'),
                actor_email=session.get('user_email', 'unknown'),
                company_id=session.get('company_id'),
                details={"updates": updates},
                ip_address=request.remote_addr,
                db=db,
            )
            db.commit()

    except Exception as e:
        logger.error(f"Error updating schema field: {e}")
        return redirect(url_for('admin_panel.domain_schemas') + f'?error={str(e)}')

    return redirect(url_for('admin_panel.domain_schemas') + '?success=Field+updated')


@admin_panel_bp.route('/domain-schemas/fields/delete', methods=['POST'])
@admin_required
def delete_schema_field():
    """Delete a schema field."""
    field_id = request.form.get('field_id', type=int)

    if not field_id:
        return redirect(url_for('admin_panel.domain_schemas') + '?error=Invalid+field')

    try:
        with get_db_session() as db:
            schema_service = get_domain_schema_service()
            schema_service.delete_field(field_id, db)

            # Audit log
            audit_service = get_audit_service()
            audit_service.log_action(
                action_type=ActionType.DOMAIN_SCHEMA_FIELD_DELETE,
                target_type=TargetType.DOMAIN_SCHEMA_FIELD,
                target_id=field_id,
                actor_user_id=session.get('user_id'),
                actor_email=session.get('user_email', 'unknown'),
                company_id=session.get('company_id'),
                details={},
                ip_address=request.remote_addr,
                db=db,
            )
            db.commit()

    except Exception as e:
        logger.error(f"Error deleting schema field: {e}")
        return redirect(url_for('admin_panel.domain_schemas') + f'?error={str(e)}')

    return redirect(url_for('admin_panel.domain_schemas') + '?success=Field+deleted')


@admin_panel_bp.route('/domain-schemas/seed-defaults', methods=['POST'])
@admin_required
def seed_default_schemas():
    """Populate default domain schemas for the company."""
    company_id = session.get('company_id')

    try:
        with get_db_session() as db:
            schema_service = get_domain_schema_service()
            schemas = schema_service.seed_default_schemas(company_id, db)
            db.commit()

    except Exception as e:
        logger.error(f"Error seeding default schemas: {e}")
        return redirect(url_for('admin_panel.domain_schemas') + f'?error={str(e)}')

    return redirect(url_for('admin_panel.domain_schemas') + f'?success=Seeded+{len(schemas)}+default+schemas')


# ==================== Documents (Knowledge Base) ====================

@admin_panel_bp.route('/documents')
@admin_required
def documents():
    """List documents in the knowledge base."""
    from app.services.document_service import get_document_service
    from app.models.document import DocumentStatus

    role = session.get('role', '')
    is_super = role == 'super_admin'
    company_id = session.get('company_id')

    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    status_filter = request.args.get('status', '')

    # SUPER_ADMIN can filter by company
    selected_company_id = None
    companies_list = []
    if is_super:
        selected_company_id = request.args.get('company_id', type=int)
        try:
            with get_db_session() as db:
                companies_list = db.query(Company).filter(Company.is_active == True).all()
        except Exception as e:
            logger.error(f"Error loading companies: {e}")

    documents_list = []
    total = 0
    pages = 0

    # Parse status filter
    status = None
    if status_filter:
        try:
            status = DocumentStatus(status_filter)
        except ValueError:
            pass

    try:
        document_service = get_document_service()
        target_company_id = selected_company_id if is_super and selected_company_id else company_id

        if target_company_id:
            documents_list, total = document_service.get_documents(
                company_id=target_company_id,
                page=page,
                per_page=per_page,
                status=status,
            )
            pages = (total + per_page - 1) // per_page

    except Exception as e:
        logger.error(f"Error listing documents: {e}")

    return render_template(
        'admin/documents.html',
        active_page='documents',
        documents=documents_list,
        companies=companies_list,
        selected_company_id=selected_company_id,
        status_filter=status_filter,
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )
