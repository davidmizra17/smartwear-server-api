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
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        Product,
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        related_name="orders",
    )
    client = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        related_name="orders",
    )
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    quantity = models.IntegerField(null=True)
    inventory_value = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    raw_nombre = models.TextField(unique=True)
    source_file = models.TextField()
    uploaded_at = models.DateTimeField()

    objects = TenantScopedManager()
    unscoped = models.Manager()

    class Meta:
        managed = False
        db_table = "order"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.raw_nombre
