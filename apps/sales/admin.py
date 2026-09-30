from django.contrib import admin

from .models import (
    OrderLine,
    OrderLineVariant,
    Payment,
    PaymentPlan,
    Quotation,
    QuotationDelivery,
    QuotationLine,
    SalesOrder,
)


class QuotationLineInline(admin.TabularInline):
    model = QuotationLine
    extra = 0


class QuotationDeliveryInline(admin.TabularInline):
    model = QuotationDelivery
    extra = 0


@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "customer",
        "contact",
        "status",
        "currency",
        "valid_until",
        "assigned_to",
        "created_by",
    )
    list_filter = ("status", "currency")
    search_fields = ("number", "customer__name")
    inlines = [QuotationLineInline, QuotationDeliveryInline]


admin.site.register(SalesOrder)
admin.site.register(OrderLine)
admin.site.register(OrderLineVariant)
admin.site.register(PaymentPlan)
admin.site.register(Payment)
