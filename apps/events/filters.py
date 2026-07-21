import django_filters

from apps.events.models import Event


class EventFilter(django_filters.FilterSet):
    event_date_after = django_filters.DateFilter(field_name="event_date", lookup_expr="gte")
    event_date_before = django_filters.DateFilter(field_name="event_date", lookup_expr="lte")
    product_name = django_filters.CharFilter(field_name="product__name", lookup_expr="icontains")

    class Meta:
        model = Event
        fields = ["event_date_after", "event_date_before", "status", "product_name"]
