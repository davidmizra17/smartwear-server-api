from django.contrib import admin

from apps.events.models import Event, OrderLine


class OrderLineInline(admin.TabularInline):
    model = OrderLine
    extra = 0


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ["title", "event_date", "status", "created_by", "created_at"]
    list_filter = ["status", "event_date"]
    search_fields = ["title", "notes"]
    inlines = [OrderLineInline]
