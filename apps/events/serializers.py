from rest_framework import serializers

from apps.events.models import Event, OrderLine
from apps.orders.models import Product
from apps.orders.serializers import ProductSerializer


class OrderLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderLine
        fields = [
            "id",
            "variant",
            "qty",
            "unit_price_cents_snapshot",
            "product_name_snapshot",
            "image_key_snapshot",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class OrderLineWriteSerializer(serializers.Serializer):
    variant_id = serializers.UUIDField()
    qty = serializers.IntegerField(min_value=1, default=1)


class EventSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        # Deprecated write path, superseded by POST /events/{id}/lines/. Kept so
        # historical events (created before the product picker) remain readable/editable.
        queryset=Product.objects.all(),
        source="product",
        required=False,
        allow_null=True,
        write_only=True,
    )
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True)
    lines = OrderLineSerializer(many=True, read_only=True)

    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "event_date",
            "quantity",
            "notes",
            "product",
            "product_id",
            "lines",
            "created_by_email",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by_email", "created_at", "updated_at"]
