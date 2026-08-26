from django.db import models

from apps.tenants.scope import OwnerScope, TenantScope, get_current_scope


class TenantScopedManager(models.Manager):
    """
    Scopes rows to the caller's access scope (apps.tenants.scope).

    Deny is the *structure*, not a case: anything that is not an explicitly
    handled scope returns .none(). A new scope kind, or a context that never
    resolved a user, therefore fails closed by default.

    `owner_path` is the ORM lookup from this model to the user who created the
    row, used to scope independent customers. Models that leave it unset deny
    OwnerScope outright rather than guessing at a field.
    """

    def __init__(self, owner_path=None):
        super().__init__()
        self.owner_path = owner_path

    def get_queryset(self):
        qs = super().get_queryset()
        scope = get_current_scope()
        if isinstance(scope, TenantScope):
            return qs.filter(client_id=scope.tenant_id)
        if isinstance(scope, OwnerScope) and self.owner_path:
            # client_id__isnull pins the result to the tenantless space, so a
            # wrong or tampered owner value still cannot cross a tenant edge.
            return qs.filter(client_id__isnull=True, **{self.owner_path: scope.user_id})
        return qs.none()
