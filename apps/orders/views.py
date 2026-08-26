from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.orders.filters import OrderFilter
from apps.orders.models import Order
from apps.orders.serializers import OrderSerializer
from apps.users.permissions import IsMasterOrSuperuser


class OrderViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = OrderSerializer
    filterset_class = OrderFilter
    ordering_fields = ["created_at", "status", "event__event_date"]
    http_method_names = ["get", "patch", "head", "options"]

    def get_permissions(self):
        if self.action in ("update", "partial_update"):
            return [IsAuthenticated(), IsMasterOrSuperuser()]
        return [IsAuthenticated()]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Order.unscoped.select_related("event", "event__created_by").all()
        return Order.objects.select_related("event", "event__created_by").all()
