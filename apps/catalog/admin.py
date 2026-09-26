from django.contrib import admin

from .models import Color, Fabric, Product, ProductVariant, Size


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("article", "name", "fabric", "unit", "is_active")
    search_fields = ("article", "name")
    list_filter = ("unit", "is_active")
    inlines = [ProductVariantInline]


admin.site.register(Fabric)
admin.site.register(Color)
admin.site.register(Size)

