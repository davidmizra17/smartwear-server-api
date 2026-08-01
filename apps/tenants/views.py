from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.tenants.models import Tenant
from apps.tenants.serializers import TenantSerializer
from apps.users.permissions import IsMasterOrSuperuser, IsSuperuser


@extend_schema(tags=["Tenants"])
class TenantViewSet(viewsets.ModelViewSet):
    serializer_class = TenantSerializer

    def get_permissions(self):
        if self.action == "create":
            return [IsSuperuser()]
        if self.action in ["update", "partial_update", "destroy"]:
            return [IsMasterOrSuperuser()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Tenant.objects.all().order_by("name")
        if user.tenant_id:
            return Tenant.objects.filter(id=user.tenant_id)
        return Tenant.objects.none()
