from rest_framework.routers import DefaultRouter

from apps.catalog.views import ProductAdminViewSet, VariantAdminViewSet

router = DefaultRouter()
router.register("products", ProductAdminViewSet, basename="admin-product")
router.register("variants", VariantAdminViewSet, basename="admin-variant")

urlpatterns = router.urls
