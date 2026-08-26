import uuid

from django.db import models

from apps.orders.managers import TenantScopedManager


class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.TextField(unique=True)
    sku = models.TextField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "product"

    def __str__(self):
        return self.name


class Order(models.Model):
    STATUS_PENDING = "pending"
    STATUS_ORDERED = "ordered"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_ORDERED, "Ordered"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.OneToOneField(
        "events.Event",
        on_delete=models.CASCADE,
        related_name="order",
    )
    client = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        related_name="orders",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantScopedManager()
    unscoped = models.Manager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order for {self.event_id}"
