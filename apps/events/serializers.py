from rest_framework import serializers

from apps.events.models import Event
from apps.orders.models import Product
from apps.orders.serializers import ProductSerializer


class EventSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source="product",
        required=False,
        allow_null=True,
        write_only=True,
    )
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True)

    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "event_date",
            "quantity",
            "notes",
            "status",
            "product",
            "product_id",
            "created_by_email",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by_email", "created_at", "updated_at"]
