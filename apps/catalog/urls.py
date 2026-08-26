from django.urls import path

from apps.catalog.views import ProductImageServeView, ProductListView

urlpatterns = [
    path("products/", ProductListView.as_view(), name="catalog-product-list"),
    path("images/<uuid:image_id>/<str:variant>/", ProductImageServeView.as_view(), name="catalog-image"),
]
