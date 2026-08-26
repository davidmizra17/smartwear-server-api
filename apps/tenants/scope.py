from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class TenantScope:
    """Caller is bound to a tenant and sees that tenant's rows."""

    tenant_id: object


@dataclass(frozen=True)
class OwnerScope:
    """
    Independent customer: no tenant, sees only the rows they created.
    """

    user_id: object


@dataclass(frozen=True)
class DenyAll:
    """
    Default scope. Covers tenantless privileged accounts (superusers and
    tenantless Masters) and any context that never resolved a user at all —
    Celery tasks, management commands, unauthenticated requests. Privileged
    views opt into cross-tenant reads explicitly via `Model.unscoped`.
    """


_current_scope: ContextVar = ContextVar("current_scope", default=DenyAll())


def get_current_scope():
    return _current_scope.get()


def set_current_scope(scope):
    return _current_scope.set(scope)


def reset_current_scope(token):
    _current_scope.reset(token)


def scope_for_user(user):
    """
    Resolve a user to exactly one access scope. This is the only place that
    maps identity to visibility.

    Tenant is checked *before* role on purpose: a Master may have a tenant, and
    when they do they stay tenant-scoped, which is the behaviour that existed
    before independent customers. Only a genuinely tenantless privileged
    account falls through to DenyAll.
    """
    if getattr(user, "tenant_id", None) is not None:
        return TenantScope(user.tenant_id)
    if user.is_superuser or user.role == "Master":
        return DenyAll()
    return OwnerScope(user.pk)
