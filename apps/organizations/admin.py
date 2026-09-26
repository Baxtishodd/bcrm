from django.contrib import admin

from .models import Branch, Membership, Organization

admin.site.register(Organization)
admin.site.register(Branch)
admin.site.register(Membership)

