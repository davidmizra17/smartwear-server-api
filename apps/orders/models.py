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
    # Lifecycle: pending (customer is still composing the basket) -> submitted
    # (customer confirmed; lines are frozen and the tenant is notified) ->
    # ordered / cancelled (Master's decision). Only the pending -> submitted
    # transition is owner-driven; the rest are Master-only.
    STATUS_PENDING = "pending"
    STATUS_SUBMITTED = "submitted"
    STATUS_ORDERED = "ordered"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SUBMITTED, "Submitted"),
        (STATUS_ORDERED, "Ordered"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.OneToOneField(
        "events.Event",
        on_delete=models.CASCADE,
        related_name="order",
    )
    # Null for independent customers; mirrors Event.client, from which it is
    # copied on creation.
    client = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        null=True,
        blank=True,
        related_name="orders",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Order has no created_by of its own; it reaches the creating user through
    # its Event.
    objects = TenantScopedManager(owner_path="event__created_by_id")
    unscoped = models.Manager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order for {self.event_id}"
