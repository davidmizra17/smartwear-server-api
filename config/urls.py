from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from rest_framework.permissions import IsAuthenticated

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("apps.users.urls.auth")),
    path("api/v1/users/", include("apps.users.urls.users")),
    path("api/v1/", include("apps.orders.urls")),
    path("api/v1/events/", include("apps.events.urls")),
    path("api/v1/", include("apps.tenants.urls")),
    path("api/schema/", SpectacularAPIView.as_view(permission_classes=[IsAuthenticated]), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema", permission_classes=[IsAuthenticated]), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema", permission_classes=[IsAuthenticated]), name="redoc"),
]
