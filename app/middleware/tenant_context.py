"""
Tenant Context Management using contextvars

Provides thread-safe and async-safe storage of the current tenant context
throughout request processing.
"""
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Optional


@dataclass
class TenantContext:
    """
    Holds the current authenticated user and company context.
    This is stored in a contextvar and available throughout the request lifecycle.
    """
    user_id: int
    email: str
    company_id: Optional[int]  # None for SUPER_ADMIN users
    company_slug: Optional[str]
    role: str
    is_super_admin: bool = False

    def is_admin(self) -> bool:
        """Check if the current user is a company admin or super admin"""
        return self.role == 'admin' or self.is_super_admin

    def is_company_admin(self) -> bool:
        """Check if the current user is a company admin (not super admin)"""
        return self.role == 'admin' and not self.is_super_admin

    def has_role(self, *roles: str) -> bool:
        """Check if the current user has any of the specified roles"""
        return self.role in roles

    def can_access_company(self, company_id: int) -> bool:
        """Check if user can access the specified company"""
        if self.is_super_admin:
            return True
        return self.company_id == company_id


# Context variable for storing tenant context
# This is thread-safe and async-safe
_tenant_context: ContextVar[Optional[TenantContext]] = ContextVar(
    "tenant_context",
    default=None
)


def set_tenant_context(context: TenantContext) -> None:
    """
    Set the tenant context for the current request/task.

    Args:
        context: TenantContext with user and company info
    """
    _tenant_context.set(context)


def get_current_tenant() -> Optional[TenantContext]:
    """
    Get the current tenant context.

    Returns:
        TenantContext if authenticated, None otherwise
    """
    return _tenant_context.get()


def get_current_tenant_required() -> TenantContext:
    """
    Get the current tenant context, raising an error if not set.

    Returns:
        TenantContext

    Raises:
        RuntimeError: If no tenant context is set
    """
    context = _tenant_context.get()
    if context is None:
        raise RuntimeError("No tenant context set - authentication required")
    return context


def clear_tenant_context() -> None:
    """
    Clear the tenant context (e.g., at end of request).
    """
    _tenant_context.set(None)


def get_current_company_id() -> Optional[int]:
    """
    Convenience function to get just the company_id.

    Returns:
        Company ID if authenticated, None otherwise
    """
    context = _tenant_context.get()
    return context.company_id if context else None


def get_current_user_id() -> Optional[int]:
    """
    Convenience function to get just the user_id.

    Returns:
        User ID if authenticated, None otherwise
    """
    context = _tenant_context.get()
    return context.user_id if context else None
