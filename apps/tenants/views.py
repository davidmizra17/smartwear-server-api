from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.tenants.models import Tenant
from apps.tenants.serializers import TenantSerializer, TenantListSerializer
from apps.users.permissions import IsMasterOrSuperuser, IsSuperuser


@extend_schema(tags=["Tenants"])
class TenantViewSet(viewsets.ModelViewSet):

    def get_serializer_class(self):
        if self.action == "list":
            return TenantListSerializer
        return TenantSerializer

    def get_permissions(self):
        if self.action == "create":
            return [IsSuperuser()]
        if self.action in ["update", "partial_update", "destroy"]:
            return [IsMasterOrSuperuser()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Tenant.objects.select_related("legal_representative").order_by("name")
        if user.tenant_id:
            return Tenant.objects.select_related("legal_representative").filter(id=user.tenant_id)
        return Tenant.objects.none()
