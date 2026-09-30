from rest_framework import serializers, viewsets

from apps.customers.api import current_organization

from .models import (
    Product,
    ProductVariant,
    WovenFabricSpecification,
    YarnSpecification,
)


class YarnSpecificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = YarnSpecification
        exclude = ("organization", "product")


class WovenFabricSpecificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = WovenFabricSpecification
        exclude = ("organization", "product")


class ProductVariantSerializer(serializers.ModelSerializer):
    color_name = serializers.CharField(source="color.name", read_only=True)
    size_name = serializers.CharField(source="size.name", read_only=True)

    class Meta:
        model = ProductVariant
        exclude = ("organization",)


class ProductSerializer(serializers.ModelSerializer):
    variants = ProductVariantSerializer(many=True, read_only=True)
    yarn_specification = YarnSpecificationSerializer(read_only=True)
    woven_specification = WovenFabricSpecificationSerializer(read_only=True)

    class Meta:
        model = Product
        exclude = ("organization",)

    def validate(self, attrs):
        organization = current_organization(self.context["request"].user)
        fabric = attrs.get("fabric", getattr(self.instance, "fabric", None))
        if fabric and (organization is None or fabric.organization_id != organization.id):
            raise serializers.ValidationError({"fabric": "Bu mato boshqa korxonaga tegishli."})
        return attrs


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    filterset_fields = (
        "category",
        "unit",
        "fabric",
        "availability",
        "finish",
        "is_active",
    )
    search_fields = ("article", "name", "fabric__name")

    def get_queryset(self):
        organization = current_organization(self.request.user)
        if not organization:
            return Product.objects.none()
        return (
            Product.objects.filter(organization=organization)
            .select_related("fabric", "yarn_specification", "woven_specification")
            .prefetch_related("variants")
        )

    def perform_create(self, serializer):
        serializer.save(organization=current_organization(self.request.user))
