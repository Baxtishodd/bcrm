from django.contrib import admin

from .models import Contact, CustomerCompany


class ContactInline(admin.TabularInline):
    model = Contact
    extra = 0


@admin.register(CustomerCompany)
class CustomerCompanyAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "relationship_status",
        "business_direction",
        "customer_type",
        "phone",
        "country",
        "owner",
        "is_active",
    )
    list_filter = (
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
    inlines = [ContactInline]
