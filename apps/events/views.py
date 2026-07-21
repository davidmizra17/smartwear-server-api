from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.events.filters import EventFilter
from apps.events.models import Event
from apps.events.serializers import EventSerializer
from apps.tenants.middleware import get_current_tenant


class EventViewSet(viewsets.ModelViewSet):
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = EventFilter
    ordering_fields = ["event_date", "created_at", "status"]

    def get_queryset(self):
        return Event.objects.select_related("product", "created_by").all()

    def perform_create(self, serializer):
        serializer.save(client=get_current_tenant(), created_by=self.request.user)
