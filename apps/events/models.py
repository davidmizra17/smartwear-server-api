import uuid

from django.conf import settings
from django.db import models

from apps.catalog.models import Variant
from apps.orders.managers import TenantScopedManager
from apps.orders.models import Product


class Event(models.Model):
    # Deprecated: superseded by Order.status (apps.orders), which is the
    # client-facing order status and is Master-only to change. Kept
    # read-only at the DB level for historical rows; not exposed via
    # EventSerializer.
    STATUS_PENDING = "pending"
    STATUS_ORDERED = "ordered"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_ORDERED, "Ordered"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        related_name="events",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="events",
    )
    # Deprecated: single-product legacy field, superseded by the `lines` relation
    # (OrderLine). Kept read-only for historical events created before the
    # product picker existed; new code must not write to this field.
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        db_constraint=False,
        null=True,
        blank=True,
        related_name="events",
    )
    title = models.CharField(max_length=200)
    event_date = models.DateField()
    # Deprecated alongside `product` — superseded by summing `lines`.
    quantity = models.PositiveIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantScopedManager()
    unscoped = models.Manager()

    class Meta:
        ordering = ["event_date"]

    def __str__(self):
        return self.title


class OrderLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="lines")
    variant = models.ForeignKey(
        Variant,
        on_delete=models.SET_NULL,
        null=True,
        related_name="order_lines",
    )
    qty = models.PositiveIntegerField()
    unit_price_cents_snapshot = models.PositiveIntegerField()
    product_name_snapshot = models.TextField()
    image_key_snapshot = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "events_order_line"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.product_name_snapshot} x{self.qty}"
