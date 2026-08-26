from django.core.files.storage import default_storage
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import filters, generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.imaging import process_and_store_image
from apps.catalog.models import Image, Product, ProductImageLink, Variant
from apps.catalog.serializers import (
    ProductAdminSerializer,
    ProductImageUploadSerializer,
    ProductListSerializer,
    VariantAdminSerializer,
)
from apps.users.permissions import IsSuperuser


@extend_schema_view(
    create=extend_schema(tags=["catalog-admin"]),
    retrieve=extend_schema(tags=["catalog-admin"]),
    update=extend_schema(tags=["catalog-admin"]),
    partial_update=extend_schema(tags=["catalog-admin"]),
    list=extend_schema(tags=["catalog-admin"]),
)
class ProductAdminViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ProductAdminSerializer
    permission_classes = [IsSuperuser]
    queryset = Product.all_objects.prefetch_related("variants", "image_links__image")

    @extend_schema(tags=["catalog-admin"], request=ProductImageUploadSerializer)
    @action(detail=True, methods=["post"], url_path="images")
    def upload_image(self, request, pk=None):
        product = self.get_object()
        upload_serializer = ProductImageUploadSerializer(data=request.data)
        upload_serializer.is_valid(raise_exception=True)
        image = _store_product_image(
            product,
            upload_serializer.validated_data["image"],
            variant=upload_serializer.validated_data.get("variant"),
            is_primary=upload_serializer.validated_data["is_primary"],
        )
        return Response(
            ProductAdminSerializer(product, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(tags=["catalog-admin"], request=None)
    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        product = self.get_object()
        product.archived_at = timezone.now()
        product.save(update_fields=["archived_at"])
        return Response(ProductAdminSerializer(product, context=self.get_serializer_context()).data)


def _store_product_image(product, uploaded_file, variant, is_primary):
    image = process_and_store_image(uploaded_file)
    return ProductImageLink.objects.create(
        product=product,
        image=image,
        variant=variant,
        is_primary=is_primary,
    ).image


@extend_schema_view(
    retrieve=extend_schema(tags=["catalog-admin"]),
    update=extend_schema(tags=["catalog-admin"]),
    partial_update=extend_schema(tags=["catalog-admin"]),
)
class VariantAdminViewSet(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = VariantAdminSerializer
    permission_classes = [IsSuperuser]
    queryset = Variant.all_objects.all()

    @extend_schema(tags=["catalog-admin"], request=None)
    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        variant = self.get_object()
        variant.archived_at = timezone.now()
        variant.active = False
        variant.save(update_fields=["archived_at", "active"])
        return Response(VariantAdminSerializer(variant).data)


class ProductCursorPagination(CursorPagination):
    ordering = "-created_at"
    page_size = 20


@extend_schema(tags=["catalog"])
class ProductListView(generics.ListAPIView):
    serializer_class = ProductListSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ProductCursorPagination
    filter_backends = [filters.SearchFilter]
    search_fields = ["name"]
    queryset = Product.objects.filter(status=Product.STATUS_ACTIVE).prefetch_related(
        "variants", "image_links__image"
    )


class ProductImageServeView(APIView):
    """Resolves an image key to a presigned S3 URL, returned as JSON rather than
    a 302 redirect. A redirect would force the browser's follow-up request to S3
    to carry an opaque `Origin: null` header (per the Fetch spec's cross-origin
    redirect handling), which no bucket CORS policy can match. Returning the URL
    as JSON lets the frontend use it directly as an <img src> (no CORS needed to
    just display an image) or issue a fresh, non-redirected fetch to it.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["catalog"], responses=None)
    def get(self, request, image_id, variant):
        image = get_object_or_404(Image, pk=image_id)
        if variant == "thumb":
            key = image.thumb_key
        elif variant == "detail":
            key = image.storage_key
        else:
            raise Http404
        if not default_storage.exists(key):
            raise Http404
        return Response({"url": default_storage.url(key)})
