from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class BcrmUserAdmin(UserAdmin):
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "is_staff", "is_active")
    fieldsets = UserAdmin.fieldsets + (
        ("BCRM", {"fields": ("phone", "preferred_language")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("BCRM", {"fields": ("email", "phone")}),
    )

