from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from rest_framework.permissions import AllowAny, IsAuthenticated

docs_permission_classes = [AllowAny] if settings.DEBUG else [IsAuthenticated]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("apps.users.urls.auth")),
    path("api/v1/users/", include("apps.users.urls.users")),
    path("api/v1/legal-representatives/", include("apps.users.urls.legal_representatives")),
    path("api/v1/", include("apps.orders.urls")),
    path("api/v1/events/", include("apps.events.urls")),
    path("api/v1/", include("apps.tenants.urls")),
    path("api/v1/catalog/", include("apps.catalog.urls")),
    path("api/v1/admin/", include("apps.catalog.urls_admin")),
    path("api/schema/", SpectacularAPIView.as_view(permission_classes=docs_permission_classes), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema", permission_classes=docs_permission_classes), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema", permission_classes=docs_permission_classes), name="redoc"),
]
