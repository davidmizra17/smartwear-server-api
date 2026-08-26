from django.db import transaction
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.reverse import reverse

from apps.catalog.models import Image, Product, ProductImageLink, Variant


class ImageSerializer(serializers.ModelSerializer):
    thumb_url = serializers.SerializerMethodField()
    detail_url = serializers.SerializerMethodField()

    class Meta:
        model = Image
        fields = ["id", "original_filename", "width", "height", "thumb_url", "detail_url"]
        read_only_fields = fields

    @extend_schema_field(serializers.URLField())
    def get_thumb_url(self, obj):
        return self._build_url(obj, "thumb")

    @extend_schema_field(serializers.URLField())
    def get_detail_url(self, obj):
        return self._build_url(obj, "detail")

    def _build_url(self, obj, variant):
        request = self.context.get("request")
        path = reverse("catalog-image", kwargs={"image_id": obj.id, "variant": variant})
        return request.build_absolute_uri(path) if request else path


class VariantAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Variant
        fields = ["id", "sku", "color", "size", "price_cents", "currency", "active", "archived_at"]
        read_only_fields = ["id", "archived_at"]


class ProductImageLinkSerializer(serializers.ModelSerializer):
    image = ImageSerializer(read_only=True)

    class Meta:
        model = ProductImageLink
        fields = ["id", "image", "variant", "is_primary", "sort_order"]
        read_only_fields = ["id", "image"]


class ProductAdminSerializer(serializers.ModelSerializer):
    variants = VariantAdminSerializer(many=True, required=False)
    image_links = ProductImageLinkSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "style_code",
            "status",
            "archived_at",
            "variants",
            "image_links",
        ]
        read_only_fields = ["id", "archived_at"]

    def create(self, validated_data):
        variants_data = validated_data.pop("variants", [])
        with transaction.atomic():
            product = Product.objects.create(**validated_data)
            for variant_data in variants_data:
                Variant.objects.create(product=product, **variant_data)
        return product


class ProductImageUploadSerializer(serializers.Serializer):
    image = serializers.ImageField()
    variant_id = serializers.PrimaryKeyRelatedField(
        queryset=Variant.objects.all(), source="variant", required=False, allow_null=True
    )
    is_primary = serializers.BooleanField(default=False)


class VariantSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Variant
        fields = ["id", "sku", "color", "size", "price_cents", "currency"]
        read_only_fields = fields


class ProductListSerializer(serializers.ModelSerializer):
    variants = VariantSummarySerializer(many=True, read_only=True)
    primary_image = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ["id", "name", "style_code", "variants", "primary_image"]
        read_only_fields = fields

    @extend_schema_field(ImageSerializer(allow_null=True))
    def get_primary_image(self, obj):
        link = next((link for link in obj.image_links.all() if link.is_primary), None)
        link = link or next(iter(obj.image_links.all()), None)
        if link is None:
            return None
        return ImageSerializer(link.image, context=self.context).data
