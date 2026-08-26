from rest_framework.routers import DefaultRouter

from apps.users.views import LegalRepresentativeViewSet

router = DefaultRouter()
router.register("", LegalRepresentativeViewSet, basename="legal-representative")

urlpatterns = router.urls
