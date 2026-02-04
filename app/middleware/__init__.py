"""
Middleware for Authentication and Multi-Tenancy
"""
from app.middleware.tenant_context import (
    TenantContext,
    get_current_tenant,
    set_tenant_context,
    clear_tenant_context,
)
from app.middleware.auth_middleware import (
    require_auth,
    require_role,
    require_admin,
    get_token_from_request,
)
from app.middleware.websocket_auth import (
    authenticate_websocket,
    websocket_auth_required,
)

__all__ = [
    # Tenant context
    'TenantContext',
    'get_current_tenant',
    'set_tenant_context',
    'clear_tenant_context',
    # Auth middleware
    'require_auth',
    'require_role',
    'require_admin',
    'get_token_from_request',
    # WebSocket auth
    'authenticate_websocket',
    'websocket_auth_required',
]
