from rest_framework import serializers, viewsets

from apps.common.api_permissions import OrganizationWritePermission
from apps.common.permissions import OrganizationPermission
from apps.organizations.models import Membership

from .models import Contact, CustomerCompany


def current_organization(user):
    if not user or not user.is_authenticated:
        return None
    membership = Membership.objects.filter(user=user, is_active=True).first()
    return membership.organization if membership else None


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        exclude = ("organization",)
        read_only_fields = ("public_id", "created_at", "updated_at")


class CustomerCompanySerializer(serializers.ModelSerializer):
    contacts = ContactSerializer(many=True, read_only=True)

    class Meta:
        model = CustomerCompany
        exclude = ("organization",)
        read_only_fields = ("public_id", "created_at", "updated_at")

    def validate(self, attrs):
        organization = current_organization(self.context["request"].user)
        owner = attrs.get("owner", getattr(self.instance, "owner", None))
        if (
            owner
            and not owner.memberships.filter(
                organization=organization,
                is_active=True,
            ).exists()
        ):
            raise serializers.ValidationError({"owner": "Xodim bu korxonaga tegishli emas."})
        return attrs


class CustomerCompanyViewSet(viewsets.ModelViewSet):
    serializer_class = CustomerCompanySerializer
    permission_classes = (OrganizationWritePermission,)
    required_write_permission = OrganizationPermission.MANAGE_CUSTOMERS
    filterset_fields = (
        "relationship_status",
        "business_direction",
        "customer_type",
        "is_active",
        "country",
    )
    search_fields = (
        "name",
        "tax_id",
        "phone",
        "whatsapp",
        "email",
        "product_interest",
        "purchase_purpose",
        "notes",
        "contacts__full_name",
    )

    def get_queryset(self):
        organization = current_organization(self.request.user)
        if not organization:
            return CustomerCompany.objects.none()
        return CustomerCompany.objects.filter(
            organization=organization,
        ).prefetch_related("contacts")

    def perform_create(self, serializer):
        serializer.save(organization=current_organization(self.request.user))
