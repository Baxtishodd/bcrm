from django.contrib import admin

from .models import (
    Branch,
    Membership,
    Organization,
    OrganizationRole,
    RolePermission,
)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "tax_id", "phone", "default_currency", "is_active")
    search_fields = ("name", "legal_name", "tax_id")
    fieldsets = (
        (
            "Asosiy ma'lumotlar",
            {
                "fields": (
                    "name",
                    "legal_name",
                    "short_name",
                    "slug",
                    "tax_id",
                    "director_name",
                    "is_active",
                )
            },
        ),
        (
            "Aloqa va manzillar",
            {
                "fields": (
                    "phone",
                    "email",
                    "website",
                    "legal_address",
                    "production_address",
                )
            },
        ),
        ("Bank", {"fields": ("bank_name", "bank_account", "bank_code")}),
        (
            "Savdo standartlari",
            {
                "fields": (
                    "default_currency",
                    "default_incoterm",
                    "default_delivery_terms",
                    "default_payment_terms",
                    "quotation_number_prefix",
                    "order_number_prefix",
                    "quotation_validity_days",
                )
            },
        ),
        (
            "Hujjatlar",
            {
                "fields": (
                    "logo",
                    "sidebar_logo",
                    "signature_image",
                    "stamp_image",
                    "document_footer",
                )
            },
        ),
        (
            "Integratsiya identifikatorlari",
            {
                "fields": (
                    "email_sender_name",
                    "telegram_username",
                    "whatsapp_phone",
                )
            },
        ),
    )


admin.site.register(Branch)
admin.site.register(Membership)
admin.site.register(OrganizationRole)
admin.site.register(RolePermission)
