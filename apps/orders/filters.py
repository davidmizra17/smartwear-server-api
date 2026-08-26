import django_filters

from apps.orders.models import Order


class OrderFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=Order.STATUS_CHOICES)
    created_after = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")
    event_title = django_filters.CharFilter(field_name="event__title", lookup_expr="icontains")

    class Meta:
        model = Order
        fields = ["status", "created_after", "created_before", "event_title"]
