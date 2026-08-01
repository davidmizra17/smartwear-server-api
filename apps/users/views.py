from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.users.models import User
from apps.users.permissions import IsMasterOrSuperuser
from apps.users.serializers import (
    TenantTokenObtainPairSerializer,
    UserManagementSerializer,
    UserSerializer,
)


@extend_schema(tags=["v1"])
class TenantTokenObtainPairView(TokenObtainPairView):
    serializer_class = TenantTokenObtainPairSerializer


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["v1"], responses=UserSerializer)
    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(tags=["users"]),
    create=extend_schema(tags=["users"]),
    retrieve=extend_schema(tags=["users"]),
    update=extend_schema(tags=["users"]),
    partial_update=extend_schema(tags=["users"]),
    destroy=extend_schema(tags=["users"]),
)
class UserViewSet(viewsets.ModelViewSet):
    serializer_class = UserManagementSerializer
    permission_classes = [IsMasterOrSuperuser]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return User.objects.select_related("tenant").order_by("date_joined")
        if not user.tenant_id:
            return User.objects.none()
        return User.objects.select_related("tenant").filter(tenant=user.tenant).order_by("date_joined")
