import uuid

from django.conf import settings
from django.db import models

from apps.orders.managers import TenantScopedManager
from apps.orders.models import Product


class Event(models.Model):
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
