"""
Authentication Middleware for Flask Routes

Provides decorators for protecting routes with JWT authentication
and role-based access control.
"""
from functools import wraps
from typing import Callable, List, Optional

from flask import request, jsonify, g

from app.services.auth_service import get_auth_service
from app.middleware.tenant_context import TenantContext, set_tenant_context, clear_tenant_context
from app.logging.logger import logger


def get_token_from_request() -> Optional[str]:
    """
    Extract JWT token from the request.

    Checks in order:
    1. Authorization header (Bearer token)
    2. Query parameter 'token' (for WebSocket connections)

    Returns:
        Token string or None
    """
    # Check Authorization header first
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header[7:]

    # Check query parameter (useful for WebSocket)
    token = request.args.get('token')
    if token:
        return token

    return None


def require_auth(f: Callable) -> Callable:
    """
    Decorator that requires valid JWT authentication.

    Sets up the tenant context with user and company information
    from the JWT token.

    Usage:
        @app.route('/api/protected')
        @require_auth
        def protected_route():
            tenant = get_current_tenant()
            return jsonify({"company_id": tenant.company_id})
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = get_token_from_request()

        if not token:
            return jsonify({
                'error': 'Authentication required',
                'message': 'Missing authentication token'
            }), 401

        auth_service = get_auth_service()
        payload = auth_service.verify_access_token(token)

        if not payload:
            return jsonify({
                'error': 'Invalid token',
                'message': 'Token is invalid or expired'
            }), 401

        # Create and set tenant context
        context = TenantContext(
            user_id=int(payload['sub']),
            email=payload['email'],
            company_id=payload.get('company_id'),  # None for SUPER_ADMIN
            company_slug=payload.get('company_slug'),
            role=payload['role'],
            is_super_admin=payload.get('is_super_admin', False),
        )
        set_tenant_context(context)

        # Also store in Flask's g for easy access
        g.tenant_context = context

        try:
            return f(*args, **kwargs)
        finally:
            # Clear context after request
            clear_tenant_context()

    return decorated_function


def require_role(*allowed_roles: str) -> Callable:
    """
    Decorator that requires the user to have one of the specified roles.

    Must be used after @require_auth.

    Usage:
        @app.route('/api/admin-only')
        @require_auth
        @require_role('admin')
        def admin_route():
            return jsonify({"message": "Admin access granted"})

        @app.route('/api/agent-or-admin')
        @require_auth
        @require_role('admin', 'agent')
        def mixed_route():
            return jsonify({"message": "Access granted"})
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get tenant context from g (set by @require_auth)
            context = getattr(g, 'tenant_context', None)

            if not context:
                return jsonify({
                    'error': 'Authentication required',
                    'message': 'Must be used with @require_auth decorator'
                }), 401

            # SUPER_ADMIN has access to all role-protected routes
            if not context.is_super_admin and context.role not in allowed_roles:
                logger.warning(
                    f"Access denied: user {context.user_id} with role '{context.role}' "
                    f"attempted to access route requiring roles: {allowed_roles}"
                )
                return jsonify({
                    'error': 'Forbidden',
                    'message': f'Access denied. Required roles: {", ".join(allowed_roles)}'
                }), 403

            return f(*args, **kwargs)

        return decorated_function

    return decorator


def require_admin(f: Callable) -> Callable:
    """
    Shortcut decorator for admin-only routes.

    Equivalent to @require_role('admin').

    Usage:
        @app.route('/api/admin-only')
        @require_auth
        @require_admin
        def admin_route():
            return jsonify({"message": "Admin access granted"})
    """
    return require_role('admin')(f)


def optional_auth(f: Callable) -> Callable:
    """
    Decorator that optionally authenticates the user.

    Sets up tenant context if a valid token is provided,
    but allows the request to proceed without authentication.

    Useful for endpoints that behave differently for authenticated
    vs unauthenticated users.

    Usage:
        @app.route('/api/public')
        @optional_auth
        def public_route():
            tenant = get_current_tenant()
            if tenant:
                return jsonify({"message": f"Hello, {tenant.email}"})
            return jsonify({"message": "Hello, guest"})
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = get_token_from_request()

        if token:
            auth_service = get_auth_service()
            payload = auth_service.verify_access_token(token)

            if payload:
                context = TenantContext(
                    user_id=int(payload['sub']),
                    email=payload['email'],
                    company_id=payload.get('company_id'),  # None for SUPER_ADMIN
                    company_slug=payload.get('company_slug'),
                    role=payload['role'],
                    is_super_admin=payload.get('is_super_admin', False),
                )
                set_tenant_context(context)
                g.tenant_context = context

        try:
            return f(*args, **kwargs)
        finally:
            clear_tenant_context()

    return decorated_function


def verify_company_access(company_id: int) -> bool:
    """
    Verify that the current user has access to the specified company.
    SUPER_ADMIN users have access to all companies.

    Args:
        company_id: Company ID to check access for

    Returns:
        True if user has access, False otherwise
    """
    context = getattr(g, 'tenant_context', None)
    if not context:
        return False
    # SUPER_ADMIN has access to all companies
    if context.is_super_admin:
        return True
    return context.company_id == company_id


def verify_session_ownership(session_company_id: int) -> bool:
    """
    Verify that the current user's company owns the session.

    Args:
        session_company_id: Company ID of the session

    Returns:
        True if the session belongs to user's company, False otherwise
    """
    return verify_company_access(session_company_id)


def require_super_admin(f: Callable) -> Callable:
    """
    Decorator that requires SUPER_ADMIN role.

    Must be used after @require_auth.

    Usage:
        @app.route('/api/v1/super/companies')
        @require_auth
        @require_super_admin
        def list_companies():
            return jsonify({"companies": [...]})
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        context = getattr(g, 'tenant_context', None)

        if not context:
            return jsonify({
                'error': 'Authentication required',
                'message': 'Must be used with @require_auth decorator'
            }), 401

        if not context.is_super_admin:
            logger.warning(
                f"Super admin access denied: user {context.user_id} with role '{context.role}' "
                f"attempted to access super admin route"
            )
            return jsonify({
                'error': 'Forbidden',
                'message': 'Super admin access required'
            }), 403

        return f(*args, **kwargs)

    return decorated_function


def require_company_admin(f: Callable) -> Callable:
    """
    Decorator that requires ADMIN role within a company or SUPER_ADMIN.

    Must be used after @require_auth.

    Usage:
        @app.route('/api/v1/admin/users')
        @require_auth
        @require_company_admin
        def list_users():
            return jsonify({"users": [...]})
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        context = getattr(g, 'tenant_context', None)

        if not context:
            return jsonify({
                'error': 'Authentication required',
                'message': 'Must be used with @require_auth decorator'
            }), 401

        # SUPER_ADMIN always has access
        if context.is_super_admin:
            return f(*args, **kwargs)

        # Company admin has access
        if context.role == 'admin':
            return f(*args, **kwargs)

        logger.warning(
            f"Company admin access denied: user {context.user_id} with role '{context.role}' "
            f"attempted to access admin route"
        )
        return jsonify({
            'error': 'Forbidden',
            'message': 'Admin access required'
        }), 403

    return decorated_function


def get_request_metadata() -> dict:
    """
    Get request metadata for audit logging.

    Returns:
        Dict with ip_address and user_agent
    """
    return {
        'ip_address': request.remote_addr,
        'user_agent': request.headers.get('User-Agent', '')[:500],
    }
