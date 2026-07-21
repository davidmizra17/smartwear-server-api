from django.contrib import admin

from .models import Tenant


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "id")
    search_fields = ("name",)
    readonly_fields = ("id", "name")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
