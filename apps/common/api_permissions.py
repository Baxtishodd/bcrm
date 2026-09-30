from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.organizations.models import Membership

from .permissions import permissions_for_membership


class OrganizationWritePermission(BasePermission):
    """Allow reads to active members and writes by the view's role permission."""

    message = "Bu amal uchun sizda ruxsat mavjud emas."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        membership = (
            Membership.objects.filter(user=request.user, is_active=True)
            .select_related("organization")
            .first()
        )
        if membership is None:
            return False
        if request.method in SAFE_METHODS:
            return True
        required_permission = getattr(view, "required_write_permission", None)
        if not required_permission:
            return False
        permissions = permissions_for_membership(
            membership,
            is_superuser=request.user.is_superuser,
        )
        return permissions.get(required_permission, False)
