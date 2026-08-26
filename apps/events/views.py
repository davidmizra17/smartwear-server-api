import logging

from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.catalog.models import Variant
from apps.events.filters import EventFilter
from apps.events.models import Event, OrderLine
from apps.events.permissions import IsEventOwnerOrSuperuser
from apps.events.serializers import (
    EventSerializer,
    OrderLineQtySerializer,
    OrderLineSerializer,
    OrderLineWriteSerializer,
)
from apps.orders.models import Order
from apps.orders.serializers import OrderSerializer
from apps.orders.tasks import send_order_created_email

logger = logging.getLogger(__name__)


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
    ordering_fields = ["event_date", "created_at"]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Event.unscoped.select_related("product", "created_by").prefetch_related("lines").all()
        return Event.objects.select_related("product", "created_by").prefetch_related("lines").all()

    def perform_create(self, serializer):
        user = self.request.user
        # Tenantless privileged accounts are the one case that still cannot
        # create: the row would land in the independent space, which their own
        # scope (DenyAll) can never read back. Independent customers are fine —
        # client resolves to None and OwnerScope picks the row up by created_by.
        if user.tenant_id is None and (user.is_superuser or user.role == "Master"):
            raise PermissionDenied("Tenantless Master and superuser accounts cannot create events.")
        # Both writes together or neither: an Event without its Order would never
        # appear under /orders/ and has no repair path through the API.
        with transaction.atomic():
            event = serializer.save(client=user.tenant, created_by=user)
            Order.objects.create(event=event, client=event.client)

    def _get_order(self, event):
        # Reverse OneToOne would go through the scoped default manager; the event
        # has already been authorised by get_object(), so read it unscoped.
        # Returns None for events predating the Order model, which have none.
        return Order.unscoped.filter(event=event).first()

    def _assert_basket_open(self, event):
        order = self._get_order(event)
        if order is not None and order.status != Order.STATUS_PENDING:
            raise ValidationError(
                f"This order is {order.get_status_display().lower()} and can no longer be modified."
            )
        return order

    @extend_schema(tags=["events"], request=None, responses=OrderSerializer)
    @action(detail=True, methods=["post"], url_path="submit")
    def submit(self, request, pk=None):
        """
        Customer confirms the basket. This — not Event creation — is the point
        at which an order exists to be notified about, so it is what dispatches
        the notification and freezes the lines.
        """
        event = self.get_object()
        order = self._assert_basket_open(event)
        if order is None:
            raise ValidationError("This event has no associated order and cannot be submitted.")
        if not event.lines.exists():
            raise ValidationError("Cannot submit an order with no product lines.")

        order.status = Order.STATUS_SUBMITTED
        order.save(update_fields=["status", "updated_at"])

        # A notification failure must never fail the submission: the order is
        # already committed and the customer would otherwise retry into an error.
        try:
            send_order_created_email.delay(str(order.id))
        except Exception:
            logger.exception(
                "Could not enqueue order-created email for order %s; order was submitted anyway.",
                order.id,
            )
        return Response(OrderSerializer(order).data)

    @extend_schema(tags=["events"], request=OrderLineWriteSerializer, responses=OrderLineSerializer)
    @action(detail=True, methods=["post"], url_path="lines")
    def add_line(self, request, pk=None):
        event = self.get_object()
        self._assert_basket_open(event)
        write_serializer = OrderLineWriteSerializer(data=request.data)
        write_serializer.is_valid(raise_exception=True)
        variant = get_object_or_404(Variant.all_objects, pk=write_serializer.validated_data["variant_id"])

        if not variant.active or variant.archived_at is not None:
            raise ValidationError("This variant is no longer available.")
        if variant.product.status != variant.product.STATUS_ACTIVE or variant.product.archived_at is not None:
            raise ValidationError("This product is no longer available.")

        qty = write_serializer.validated_data["qty"]
        line, created = OrderLine.objects.get_or_create(
            event=event,
            variant=variant,
            defaults={
                "qty": qty,
                "unit_price_cents_snapshot": variant.price_cents,
                "product_name_snapshot": variant.product.name,
                "image_key_snapshot": _primary_image_key(variant),
            },
        )
        if not created:
            line.qty += qty
            line.save(update_fields=["qty", "updated_at"])

        return Response(
            OrderLineSerializer(line).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @extend_schema(tags=["events"], request=None)
    @action(detail=True, methods=["patch", "delete"], url_path=r"lines/(?P<line_id>[^/.]+)")
    def line_detail(self, request, pk=None, line_id=None):
        event = self.get_object()
        self._assert_basket_open(event)
        line = get_object_or_404(OrderLine, pk=line_id, event=event)

        if request.method == "DELETE":
            line.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        # Validated at the boundary rather than hand-parsed: int("abc") and
        # int([1]) raise ValueError/TypeError, which escape as unhandled 500s.
        qty_serializer = OrderLineQtySerializer(data=request.data)
        qty_serializer.is_valid(raise_exception=True)
        line.qty = qty_serializer.validated_data["qty"]
        line.save(update_fields=["qty", "updated_at"])
        return Response(OrderLineSerializer(line).data)


def _primary_image_key(variant):
    link = (
        variant.image_links.filter(is_primary=True).first()
        or variant.image_links.first()
        or variant.product.image_links.filter(is_primary=True).first()
        or variant.product.image_links.first()
    )
    return link.image.storage_key if link else None
