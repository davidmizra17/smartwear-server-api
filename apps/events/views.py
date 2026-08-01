from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from apps.events.filters import EventFilter
from apps.events.models import Event
from apps.events.permissions import IsEventOwnerOrSuperuser
from apps.events.serializers import EventSerializer


@extend_schema_view(
    list=extend_schema(tags=["events"]),
    create=extend_schema(tags=["events"]),
    retrieve=extend_schema(tags=["events"]),
    update=extend_schema(tags=["events"]),
    partial_update=extend_schema(tags=["events"]),
    destroy=extend_schema(tags=["events"]),
)
class EventViewSet(viewsets.ModelViewSet):
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated, IsEventOwnerOrSuperuser]
    filterset_class = EventFilter
    ordering_fields = ["event_date", "created_at", "status"]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Event.unscoped.select_related("product", "created_by").all()
        return Event.objects.select_related("product", "created_by").all()

    def perform_create(self, serializer):
        if not self.request.user.tenant_id:
            raise PermissionDenied("User is not associated with a tenant.")
        serializer.save(client=self.request.user.tenant, created_by=self.request.user)
