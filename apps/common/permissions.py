from functools import wraps

from django.core.exceptions import PermissionDenied

from apps.organizations.models import Membership


class OrganizationPermission:
    MANAGE_ORGANIZATION = "manage_organization"
    MANAGE_CUSTOMERS = "manage_customers"
    MANAGE_LEADS = "manage_leads"
    MANAGE_TASKS = "manage_tasks"
    MANAGE_CATALOG = "manage_catalog"
    MANAGE_SALES = "manage_sales"
    MANAGE_MAILBOX = "manage_mailbox"


ROLE_PERMISSIONS = {
    Membership.Role.OWNER: {
        OrganizationPermission.MANAGE_ORGANIZATION,
        OrganizationPermission.MANAGE_CUSTOMERS,
        OrganizationPermission.MANAGE_LEADS,
        OrganizationPermission.MANAGE_TASKS,
        OrganizationPermission.MANAGE_CATALOG,
        OrganizationPermission.MANAGE_SALES,
        OrganizationPermission.MANAGE_MAILBOX,
    },
    Membership.Role.DIRECTOR: {
        OrganizationPermission.MANAGE_ORGANIZATION,
        OrganizationPermission.MANAGE_CUSTOMERS,
        OrganizationPermission.MANAGE_LEADS,
        OrganizationPermission.MANAGE_TASKS,
        OrganizationPermission.MANAGE_CATALOG,
        OrganizationPermission.MANAGE_SALES,
        OrganizationPermission.MANAGE_MAILBOX,
    },
    Membership.Role.SALES: {
        OrganizationPermission.MANAGE_CUSTOMERS,
        OrganizationPermission.MANAGE_LEADS,
        OrganizationPermission.MANAGE_TASKS,
        OrganizationPermission.MANAGE_CATALOG,
        OrganizationPermission.MANAGE_SALES,
        OrganizationPermission.MANAGE_MAILBOX,
    },
    Membership.Role.TECHNOLOGIST: {
        OrganizationPermission.MANAGE_TASKS,
        OrganizationPermission.MANAGE_CATALOG,
    },
    Membership.Role.PRODUCTION: {OrganizationPermission.MANAGE_TASKS},
    Membership.Role.WAREHOUSE: {OrganizationPermission.MANAGE_TASKS},
    Membership.Role.ACCOUNTANT: {
        OrganizationPermission.MANAGE_TASKS,
        OrganizationPermission.MANAGE_MAILBOX,
    },
    Membership.Role.VIEWER: set(),
}


def permissions_for_membership(membership, *, is_superuser=False):
    permissions = {
        OrganizationPermission.MANAGE_ORGANIZATION: False,
        OrganizationPermission.MANAGE_CUSTOMERS: False,
        OrganizationPermission.MANAGE_LEADS: False,
        OrganizationPermission.MANAGE_TASKS: False,
        OrganizationPermission.MANAGE_CATALOG: False,
        OrganizationPermission.MANAGE_SALES: False,
        OrganizationPermission.MANAGE_MAILBOX: False,
    }
    if is_superuser:
        return {name: True for name in permissions}
    if membership is None:
        return permissions
    for name in ROLE_PERMISSIONS.get(membership.role, set()):
        permissions[name] = True
    return permissions


def organization_permission_required(permission):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            permissions = getattr(request, "crm_permissions", {})
            if not permissions.get(permission, False):
                raise PermissionDenied("Bu amal uchun sizda ruxsat mavjud emas.")
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator
