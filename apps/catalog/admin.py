from django.contrib import admin

from .models import (
    Color,
    Fabric,
    PriceList,
    PriceListLine,
    Product,
    ProductVariant,
    Size,
    WovenFabricSpecification,
    YarnSpecification,
)


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0


class YarnSpecificationInline(admin.StackedInline):
    model = YarnSpecification
    extra = 0
    max_num = 1


class WovenFabricSpecificationInline(admin.StackedInline):
    model = WovenFabricSpecification
    extra = 0
    max_num = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "article",
        "name",
        "category",
        "fabric",
        "availability",
        "stock_quantity",
        "list_price",
        "price_currency",
        "is_active",
    )
    search_fields = ("article", "name")
    list_filter = ("category", "unit", "availability", "finish", "is_active")
    inlines = [YarnSpecificationInline, WovenFabricSpecificationInline, ProductVariantInline]


class PriceListLineInline(admin.TabularInline):
    model = PriceListLine
    extra = 0
    fields = (
        "product",
        "color",
        "size",
        "image",
        "description_snapshot",
        "available_quantity",
        "unit",
        "unit_price",
        "minimum_order_quantity",
        "planned_loading_date",
        "sort_order",
    )


@admin.register(PriceList)
class PriceListAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "version",
        "document_type",
        "category",
        "issue_date",
        "valid_until",
        "currency",
        "status",
    )
    list_filter = ("document_type", "category", "status", "currency")
    search_fields = ("number", "title")
    inlines = [PriceListLineInline]


admin.site.register(Fabric)
admin.site.register(Color)
admin.site.register(Size)
