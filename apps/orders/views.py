from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.orders.filters import OrderFilter
from apps.orders.models import Order
from apps.orders.serializers import OrderSerializer, OrderStatusUpdateSerializer
from apps.users.permissions import IsMasterOrSuperuser


class OrderViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = OrderSerializer
    filterset_class = OrderFilter
    ordering_fields = ["created_at", "status", "event__event_date"]
    http_method_names = ["get", "patch", "head", "options"]

    def get_permissions(self):
        if self.action == "status":
            return [IsAuthenticated(), IsMasterOrSuperuser()]
        return [IsAuthenticated()]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Order.unscoped.select_related("event", "event__created_by").all()
        return Order.objects.select_related("event", "event__created_by").all()

    @action(detail=True, methods=["patch"])
    def status(self, request, pk=None):
        order = self.get_object()
        serializer = OrderStatusUpdateSerializer(order, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(OrderSerializer(order).data)
