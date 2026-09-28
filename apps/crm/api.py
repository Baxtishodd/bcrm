from rest_framework import serializers, viewsets

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


class LeadViewSet(viewsets.ModelViewSet):
    serializer_class = LeadSerializer
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
        serializer.save(organization=current_organization(self.request.user))
