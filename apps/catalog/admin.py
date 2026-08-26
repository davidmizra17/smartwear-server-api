from django.contrib import admin

from apps.catalog.models import Image, Product, ProductImageLink, Variant


class VariantInline(admin.TabularInline):
    model = Variant
    extra = 0


class ProductImageLinkInline(admin.TabularInline):
    model = ProductImageLink
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "style_code", "status", "archived_at"]
    list_filter = ["status"]
    search_fields = ["name", "style_code"]
    inlines = [VariantInline, ProductImageLinkInline]

    def get_queryset(self, request):
        return Product.all_objects.all()


@admin.register(Variant)
class VariantAdmin(admin.ModelAdmin):
    list_display = ["sku", "product", "color", "size", "price_cents", "currency", "active"]
    list_filter = ["active"]
    search_fields = ["sku", "product__name"]

    def get_queryset(self, request):
        return Variant.all_objects.all()


@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    list_display = ["original_filename", "storage_key", "width", "height", "source", "created_at"]
    search_fields = ["original_filename", "storage_key"]
