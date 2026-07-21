from rest_framework import serializers

from apps.orders.models import Order, Product


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["id", "name", "sku"]
        read_only_fields = fields


class OrderSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "product",
            "unit_cost",
            "quantity",
            "inventory_value",
            "raw_nombre",
            "source_file",
            "uploaded_at",
        ]
        read_only_fields = fields
