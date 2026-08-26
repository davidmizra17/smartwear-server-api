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
from apps.events.serializers import EventSerializer, OrderLineSerializer, OrderLineWriteSerializer
from apps.orders.models import Order


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
        event = serializer.save(client=user.tenant, created_by=user)
        Order.objects.create(event=event, client=event.client)

    @extend_schema(tags=["events"], request=OrderLineWriteSerializer, responses=OrderLineSerializer)
    @action(detail=True, methods=["post"], url_path="lines")
    def add_line(self, request, pk=None):
        event = self.get_object()
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
        line = get_object_or_404(OrderLine, pk=line_id, event=event)

        if request.method == "DELETE":
            line.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        qty = request.data.get("qty")
        if qty is None or int(qty) < 1:
            raise ValidationError({"qty": "Must be a positive integer."})
        line.qty = int(qty)
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
