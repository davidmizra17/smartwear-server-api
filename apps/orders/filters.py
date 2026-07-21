import django_filters

from apps.orders.models import Order


class OrderFilter(django_filters.FilterSet):
    uploaded_after = django_filters.DateTimeFilter(field_name="uploaded_at", lookup_expr="gte")
    uploaded_before = django_filters.DateTimeFilter(field_name="uploaded_at", lookup_expr="lte")
    product_name = django_filters.CharFilter(field_name="product__name", lookup_expr="icontains")
    source_file = django_filters.CharFilter(field_name="source_file", lookup_expr="icontains")

    class Meta:
        model = Order
        fields = ["uploaded_after", "uploaded_before", "product_name", "source_file"]
