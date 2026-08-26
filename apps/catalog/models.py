import uuid

from django.db import models

from apps.catalog.managers import NotArchivedManager


class Product(models.Model):
    STATUS_ACTIVE = "active"
    STATUS_DISCONTINUED = "discontinued"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_DISCONTINUED, "Discontinued"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.TextField()
    style_code = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = NotArchivedManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "catalog_product"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Variant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    sku = models.CharField(max_length=100, unique=True)
    color = models.CharField(max_length=100, null=True, blank=True)
    size = models.CharField(max_length=50, null=True, blank=True)
    price_cents = models.PositiveIntegerField()
    currency = models.CharField(max_length=3)
    active = models.BooleanField(default=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = NotArchivedManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "catalog_variant"
        ordering = ["sku"]

    def __str__(self):
        return self.sku


class Image(models.Model):
    SOURCE_MANUAL_UPLOAD = "manual_upload"
    SOURCE_CHOICES = [
        (SOURCE_MANUAL_UPLOAD, "Manual upload"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    storage_key = models.TextField()
    thumb_key = models.TextField()
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_MANUAL_UPLOAD)
    original_filename = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "catalog_image"

    def __str__(self):
        return self.original_filename


class ProductImageLink(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="image_links")
    image = models.ForeignKey(Image, on_delete=models.CASCADE, related_name="product_links")
    variant = models.ForeignKey(
        Variant,
        on_delete=models.CASCADE,
        related_name="image_links",
        null=True,
        blank=True,
    )
    is_primary = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "catalog_product_image_link"
        constraints = [
            models.UniqueConstraint(fields=["product", "image"], name="unique_product_image"),
        ]
        ordering = ["sort_order"]
