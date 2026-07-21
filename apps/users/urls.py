from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from apps.users.views import MeView, TenantTokenObtainPairView

urlpatterns = [
    path("token/", TenantTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("me/", MeView.as_view(), name="me"),
]
