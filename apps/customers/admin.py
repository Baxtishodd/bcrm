from django.contrib import admin

from .models import Contact, CustomerCompany


class ContactInline(admin.TabularInline):
    model = Contact
    extra = 0


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("full_name", "contact_type", "company", "phone", "owner", "is_active")
    list_filter = ("contact_type", "is_active", "country")
    search_fields = ("full_name", "company__name", "phone", "email", "tags")


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
