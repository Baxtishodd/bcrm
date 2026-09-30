from rest_framework import serializers, viewsets

from apps.common.api_permissions import OrganizationWritePermission
from apps.common.permissions import OrganizationPermission
from apps.customers.api import current_organization

from .models import Quotation, QuotationLine, SalesOrder
from .services import next_document_number


class QuotationLineSerializer(serializers.ModelSerializer):
    line_total = serializers.DecimalField(max_digits=24, decimal_places=2, read_only=True)

    class Meta:
        model = QuotationLine
        fields = (
            "public_id",
            "product",
            "variant",
            "description",
            "quantity",
            "unit_price",
            "line_total",
        )


class QuotationSerializer(serializers.ModelSerializer):
    lines = QuotationLineSerializer(many=True, read_only=True)
    subtotal = serializers.DecimalField(max_digits=24, decimal_places=2, read_only=True)
    total = serializers.DecimalField(max_digits=24, decimal_places=2, read_only=True)

    class Meta:
        model = Quotation
        exclude = ("organization",)
        read_only_fields = ("created_by", "paid_amount")
        extra_kwargs = {"number": {"required": False}}

    def validate(self, attrs):
        organization = current_organization(self.context["request"].user)
        if organization is None:
            raise serializers.ValidationError("Foydalanuvchiga korxona biriktirilmagan.")
        customer = attrs.get("customer", getattr(self.instance, "customer", None))
        contact = attrs.get("contact", getattr(self.instance, "contact", None))
        lead = attrs.get("lead", getattr(self.instance, "lead", None))
        assigned_to = attrs.get("assigned_to", getattr(self.instance, "assigned_to", None))
        if customer and customer.organization_id != organization.id:
            raise serializers.ValidationError({"customer": "Bu mijoz boshqa korxonaga tegishli."})
        if lead and lead.organization_id != organization.id:
            raise serializers.ValidationError({"lead": "Bu lead boshqa korxonaga tegishli."})
        if lead and lead.customer_id and customer and lead.customer_id != customer.id:
            raise serializers.ValidationError({"lead": "Lead tanlangan mijozga tegishli emas."})
        if contact and contact.organization_id != organization.id:
            raise serializers.ValidationError({"contact": "Bu kontakt boshqa korxonaga tegishli."})
        if contact and customer and contact.company_id != customer.id:
            raise serializers.ValidationError(
                {"contact": "Kontakt tanlangan mijozga tegishli emas."}
            )
        if assigned_to and not assigned_to.memberships.filter(
            organization=organization,
            is_active=True,
        ).exists():
            raise serializers.ValidationError({"assigned_to": "Xodim bu korxonaga tegishli emas."})
        return attrs


class QuotationViewSet(viewsets.ModelViewSet):
    serializer_class = QuotationSerializer
    permission_classes = (OrganizationWritePermission,)
    required_write_permission = OrganizationPermission.MANAGE_SALES
    filterset_fields = ("status", "customer", "currency")

    def get_queryset(self):
        organization = current_organization(self.request.user)
        if not organization:
            return Quotation.objects.none()
        return Quotation.objects.filter(organization=organization).select_related(
            "customer",
            "contact",
            "lead",
            "assigned_to",
            "created_by",
        ).prefetch_related("lines")

    def perform_create(self, serializer):
        organization = current_organization(self.request.user)
        number = serializer.validated_data.get("number") or next_document_number(
            Quotation,
            organization,
            "QT",
        )
        serializer.save(organization=organization, created_by=self.request.user, number=number)


class SalesOrderSerializer(serializers.ModelSerializer):
    total = serializers.DecimalField(max_digits=24, decimal_places=2, read_only=True)
    balance = serializers.DecimalField(max_digits=24, decimal_places=2, read_only=True)
    payment_status = serializers.CharField(read_only=True)

    class Meta:
        model = SalesOrder
        exclude = ("organization",)
        read_only_fields = ("created_by",)
        extra_kwargs = {"number": {"required": False}}

    def validate(self, attrs):
        organization = current_organization(self.context["request"].user)
        if organization is None:
            raise serializers.ValidationError("Foydalanuvchiga korxona biriktirilmagan.")
        customer = attrs.get("customer", getattr(self.instance, "customer", None))
        quotation = attrs.get("quotation", getattr(self.instance, "quotation", None))
        assigned_to = attrs.get("assigned_to", getattr(self.instance, "assigned_to", None))
        if customer and customer.organization_id != organization.id:
            raise serializers.ValidationError({"customer": "Bu mijoz boshqa korxonaga tegishli."})
        if quotation and quotation.organization_id != organization.id:
            raise serializers.ValidationError({"quotation": "Bu taklif boshqa korxonaga tegishli."})
        if quotation and customer and quotation.customer_id != customer.id:
            raise serializers.ValidationError(
                {"quotation": "Taklif tanlangan mijozga tegishli emas."}
            )
        if assigned_to and not assigned_to.memberships.filter(
            organization=organization,
            is_active=True,
        ).exists():
            raise serializers.ValidationError({"assigned_to": "Xodim bu korxonaga tegishli emas."})
        return attrs


class SalesOrderViewSet(viewsets.ModelViewSet):
    serializer_class = SalesOrderSerializer
    permission_classes = (OrganizationWritePermission,)
    required_write_permission = OrganizationPermission.MANAGE_SALES
    filterset_fields = ("status", "customer", "assigned_to")

    def get_queryset(self):
        organization = current_organization(self.request.user)
        if not organization:
            return SalesOrder.objects.none()
        return SalesOrder.objects.filter(organization=organization).select_related(
            "customer",
            "quotation",
            "assigned_to",
        ).prefetch_related("lines")

    def perform_create(self, serializer):
        organization = current_organization(self.request.user)
        number = serializer.validated_data.get("number") or next_document_number(
            SalesOrder,
            organization,
            "SO",
        )
        serializer.save(organization=organization, created_by=self.request.user, number=number)
