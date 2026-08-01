from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.orders.filters import OrderFilter
from apps.orders.models import Order
from apps.orders.serializers import OrderSerializer


class OrderViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = OrderFilter
    ordering_fields = ["uploaded_at", "unit_cost", "quantity", "inventory_value"]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Order.unscoped.select_related("product").all()
        return Order.objects.select_related("product").all()
