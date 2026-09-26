from rest_framework import serializers, viewsets

from apps.organizations.models import Membership

from .models import Contact, CustomerCompany


def current_organization(user):
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


class CustomerCompanyViewSet(viewsets.ModelViewSet):
    serializer_class = CustomerCompanySerializer
    filterset_fields = ("customer_type", "is_active", "country")
    search_fields = ("name", "tax_id", "phone", "email")

    def get_queryset(self):
        organization = current_organization(self.request.user)
        if not organization:
            return CustomerCompany.objects.none()
        return CustomerCompany.objects.filter(
            organization=organization,
        ).prefetch_related("contacts")

    def perform_create(self, serializer):
        serializer.save(organization=current_organization(self.request.user))

