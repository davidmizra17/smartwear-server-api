from rest_framework import serializers

from apps.orders.models import Order, Product


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["id", "name", "sku"]
        read_only_fields = fields


class OrderSerializer(serializers.ModelSerializer):
    event_title = serializers.CharField(source="event.title", read_only=True)
    event_date = serializers.DateField(source="event.event_date", read_only=True)
    created_by_email = serializers.EmailField(source="event.created_by.email", read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "event",
            "event_title",
            "event_date",
            "created_by_email",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "event",
            "event_title",
            "event_date",
            "created_by_email",
            "created_at",
            "updated_at",
        ]


class OrderStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.STATUS_CHOICES)

    def update(self, instance, validated_data):
        instance.status = validated_data["status"]
        instance.save(update_fields=["status", "updated_at"])
        return instance
