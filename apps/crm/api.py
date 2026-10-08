from rest_framework import serializers, viewsets

from apps.common.api_permissions import OrganizationWritePermission
from apps.common.permissions import OrganizationPermission, can_manage_all_records
from apps.common.tenancy import get_membership
from apps.customers.api import current_organization

from .models import Activity, Lead


class ActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Activity
        exclude = ("organization",)
        read_only_fields = ("public_id", "created_at", "updated_at")


class LeadSerializer(serializers.ModelSerializer):
    activities = ActivitySerializer(many=True, read_only=True)

    class Meta:
        model = Lead
        exclude = ("organization",)
        read_only_fields = ("public_id", "created_at", "updated_at")

    def validate(self, attrs):
        organization = current_organization(self.context["request"].user)
        if organization is None:
            raise serializers.ValidationError("Foydalanuvchiga korxona biriktirilmagan.")
        customer = attrs.get("customer", getattr(self.instance, "customer", None))
        contact = attrs.get("contact", getattr(self.instance, "contact", None))
        stage = attrs.get("stage", getattr(self.instance, "stage", None))
        assigned_to = attrs.get("assigned_to", getattr(self.instance, "assigned_to", None))
        status = attrs.get("status", getattr(self.instance, "status", Lead.Status.NEW))
        lost_reason = attrs.get(
            "lost_reason",
            getattr(self.instance, "lost_reason", ""),
        )
        if customer and customer.organization_id != organization.id:
            raise serializers.ValidationError({"customer": "Bu mijoz boshqa korxonaga tegishli."})
        if contact and contact.organization_id != organization.id:
            raise serializers.ValidationError({"contact": "Bu kontakt boshqa korxonaga tegishli."})
        if contact and customer and contact.company_id != customer.id:
            raise serializers.ValidationError(
                {"contact": "Kontakt tanlangan mijozga tegishli emas."}
            )
        if stage and stage.organization_id != organization.id:
            raise serializers.ValidationError({"stage": "Bu bosqich boshqa korxonaga tegishli."})
        if (
            assigned_to
            and not assigned_to.memberships.filter(
                organization=organization,
                is_active=True,
            ).exists()
        ):
            raise serializers.ValidationError({"assigned_to": "Xodim bu korxonaga tegishli emas."})
        if status == Lead.Status.LOST and not str(lost_reason or "").strip():
            raise serializers.ValidationError(
                {"lost_reason": "Yutqazilgan Lead uchun sababni kiriting."}
            )
        if status == Lead.Status.WON and not customer:
            raise serializers.ValidationError(
                {"customer": "Yutilgan Lead uchun mijozni biriktiring."}
            )
        return attrs


class LeadViewSet(viewsets.ModelViewSet):
    serializer_class = LeadSerializer
    permission_classes = (OrganizationWritePermission,)
    required_write_permission = OrganizationPermission.MANAGE_LEADS
    filterset_fields = (
        "business_direction",
        "status",
        "priority",
        "stage",
        "assigned_to",
    )
    search_fields = ("title", "customer__name", "description")

    def get_queryset(self):
        organization = current_organization(self.request.user)
        if not organization:
            return Lead.objects.none()
        return (
            Lead.objects.filter(organization=organization)
            .select_related("customer", "contact", "stage", "assigned_to")
            .prefetch_related("activities")
        )

    def perform_create(self, serializer):
        membership = get_membership(self.request.user)
        values = {"organization": membership.organization}
        if (
            not can_manage_all_records(self.request.user, membership)
            or serializer.validated_data.get("assigned_to") is None
        ):
            values["assigned_to"] = self.request.user
        serializer.save(**values)
