from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.organizations.models import Membership

from .permissions import (
    MANAGE_PERMISSION_MODULES,
    OrganizationPermission,
    can_edit_record,
    permission_for_method,
    permissions_for_membership,
)


class OrganizationWritePermission(BasePermission):
    """Allow reads to active members and writes by the view's role permission."""

    message = "Bu amal uchun sizda ruxsat mavjud emas."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        membership = (
            Membership.objects.filter(user=request.user, is_active=True)
            .select_related("organization", "custom_role")
            .first()
        )
        if membership is None:
            return False
        required_permission = getattr(view, "required_write_permission", None)
        if not required_permission:
            return request.method in SAFE_METHODS
        permissions = permissions_for_membership(
            membership,
            is_superuser=request.user.is_superuser,
        )
        if request.method in SAFE_METHODS:
            module = MANAGE_PERMISSION_MODULES.get(required_permission)
            if module is None:
                return True
            return permissions.get(
                OrganizationPermission.for_action(module, "view"),
                False,
            )
        return permissions.get(
            permission_for_method(required_permission, request.method),
            False,
        )

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        membership = (
            Membership.objects.filter(user=request.user, is_active=True)
            .select_related("organization", "custom_role")
            .first()
        )
        return can_edit_record(request.user, membership, obj)
