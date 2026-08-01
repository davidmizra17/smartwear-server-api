from django.db import models

from apps.tenants.middleware import get_current_tenant


class TenantScopedManager(models.Manager):
    def get_queryset(self):
        qs = super().get_queryset()
        tenant = get_current_tenant()
        if tenant is None:
            return qs.none()
        return qs.filter(client_id=tenant.id)
