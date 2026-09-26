from rest_framework import serializers, viewsets

from apps.customers.api import current_organization

from .models import Product, ProductVariant


class ProductVariantSerializer(serializers.ModelSerializer):
    color_name = serializers.CharField(source="color.name", read_only=True)
    size_name = serializers.CharField(source="size.name", read_only=True)

    class Meta:
        model = ProductVariant
        exclude = ("organization",)


class ProductSerializer(serializers.ModelSerializer):
    variants = ProductVariantSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        exclude = ("organization",)


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    filterset_fields = ("unit", "fabric", "is_active")
    search_fields = ("article", "name")

    def get_queryset(self):
        organization = current_organization(self.request.user)
        if not organization:
            return Product.objects.none()
        return (
            Product.objects.filter(organization=organization)
            .select_related("fabric")
            .prefetch_related("variants")
        )

    def perform_create(self, serializer):
        serializer.save(organization=current_organization(self.request.user))

