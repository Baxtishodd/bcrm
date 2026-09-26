from django.contrib import admin

from .models import Activity, Lead, PipelineStage


class ActivityInline(admin.TabularInline):
    model = Activity
    extra = 0


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "customer",
        "stage",
        "status",
        "estimated_value",
        "currency",
        "assigned_to",
    )
    list_filter = ("status", "priority", "stage", "currency")
    search_fields = ("title", "customer__name", "description")
    inlines = [ActivityInline]


admin.site.register(PipelineStage)

