from functools import wraps

from django.core.exceptions import PermissionDenied

from apps.organizations.models import Membership, RolePermission


class OrganizationPermission:
    MODULES = tuple(RolePermission.Module.values)
    ACTIONS = tuple(RolePermission.Action.values)

    MANAGE_ORGANIZATION = "manage_organization"
    MANAGE_CUSTOMERS = "manage_customers"
    MANAGE_LEADS = "manage_leads"
    MANAGE_TASKS = "manage_tasks"
    MANAGE_CATALOG = "manage_catalog"
    MANAGE_SALES = "manage_sales"
    MANAGE_MAILBOX = "manage_mailbox"

    @staticmethod
    def for_action(module, action):
        return f"{action}_{module}"


for _module in OrganizationPermission.MODULES:
    for _action in OrganizationPermission.ACTIONS:
        setattr(
            OrganizationPermission,
            f"{_action.upper()}_{_module.upper()}",
            OrganizationPermission.for_action(_module, _action),
        )


MANAGE_PERMISSION_MODULES = {
    OrganizationPermission.MANAGE_ORGANIZATION: RolePermission.Module.ORGANIZATION,
    OrganizationPermission.MANAGE_CUSTOMERS: RolePermission.Module.CUSTOMERS,
    OrganizationPermission.MANAGE_LEADS: RolePermission.Module.LEADS,
    OrganizationPermission.MANAGE_TASKS: RolePermission.Module.TASKS,
    OrganizationPermission.MANAGE_CATALOG: RolePermission.Module.CATALOG,
    OrganizationPermission.MANAGE_SALES: RolePermission.Module.SALES,
    OrganizationPermission.MANAGE_MAILBOX: RolePermission.Module.MAILBOX,
}


ROLE_MANAGED_MODULES = {
    Membership.Role.OWNER: set(RolePermission.Module.values),
    Membership.Role.DIRECTOR: set(RolePermission.Module.values),
    Membership.Role.SALES: {
        RolePermission.Module.CUSTOMERS,
        RolePermission.Module.LEADS,
        RolePermission.Module.TASKS,
        RolePermission.Module.CATALOG,
        RolePermission.Module.SALES,
        RolePermission.Module.MAILBOX,
    },
    Membership.Role.TECHNOLOGIST: {
        RolePermission.Module.TASKS,
        RolePermission.Module.CATALOG,
    },
    Membership.Role.PRODUCTION: {RolePermission.Module.TASKS},
    Membership.Role.WAREHOUSE: {RolePermission.Module.TASKS},
    Membership.Role.ACCOUNTANT: {
        RolePermission.Module.TASKS,
        RolePermission.Module.MAILBOX,
    },
    Membership.Role.VIEWER: set(),
}

LEGACY_READ_MODULES = {
    RolePermission.Module.CUSTOMERS,
    RolePermission.Module.LEADS,
    RolePermission.Module.TASKS,
    RolePermission.Module.CATALOG,
    RolePermission.Module.SALES,
}


def permissions_for_membership(membership, *, is_superuser=False):
    permissions = {
        OrganizationPermission.for_action(module, action): False
        for module in OrganizationPermission.MODULES
        for action in OrganizationPermission.ACTIONS
    }
    permissions.update({name: False for name in MANAGE_PERMISSION_MODULES})
    if is_superuser or (
        membership is not None and membership.role == Membership.Role.OWNER
    ):
        return {name: True for name in permissions}
    if membership is None:
        return permissions

    if membership.custom_role_id:
        entries = membership.custom_role.permission_entries.values_list(
            "module", "action"
        )
        for module, action in entries:
            permissions[OrganizationPermission.for_action(module, action)] = True
    else:
        # Eski tizimdagi rollarning o'qish imkoniyatini o'zgartirmaymiz.
        for module in LEGACY_READ_MODULES:
            permissions[
                OrganizationPermission.for_action(module, RolePermission.Action.VIEW)
            ] = True
        for module in ROLE_MANAGED_MODULES.get(membership.role, set()):
            for action in OrganizationPermission.ACTIONS:
                permissions[OrganizationPermission.for_action(module, action)] = True

    for legacy_name, module in MANAGE_PERMISSION_MODULES.items():
        permissions[legacy_name] = all(
            permissions[OrganizationPermission.for_action(module, action)]
            for action in (
                RolePermission.Action.CREATE,
                RolePermission.Action.UPDATE,
                RolePermission.Action.DELETE,
            )
        )
    return permissions


def permission_for_method(required_permission, method):
    module = MANAGE_PERMISSION_MODULES.get(required_permission)
    if module is None:
        return required_permission
    action = {
        "POST": RolePermission.Action.CREATE,
        "PUT": RolePermission.Action.UPDATE,
        "PATCH": RolePermission.Action.UPDATE,
        "DELETE": RolePermission.Action.DELETE,
    }.get(method, RolePermission.Action.VIEW)
    return OrganizationPermission.for_action(module, action)


def record_owner_id(instance):
    """Return the employee responsible for a business record."""
    for field_name in ("owner_id", "assigned_to_id", "created_by_id"):
        if hasattr(instance, field_name):
            owner_id = getattr(instance, field_name)
            if owner_id is not None:
                return owner_id

    for relation_name in ("quotation", "order", "lead", "customer"):
        relation_id = getattr(instance, f"{relation_name}_id", None)
        if relation_id is not None:
            return record_owner_id(getattr(instance, relation_name))
    return None


def can_manage_all_records(user, membership):
    if user.is_superuser:
        return True
    if membership is None or not membership.is_active:
        return False
    return membership.role == Membership.Role.OWNER or membership.can_manage_all_records


def can_edit_record(user, membership, instance):
    if can_manage_all_records(user, membership):
        return True
    return record_owner_id(instance) == user.id


def ensure_record_editable(request, instance):
    if not can_edit_record(
        request.user,
        getattr(request, "membership", None),
        instance,
    ):
        raise PermissionDenied(
            "Bu yozuv boshqa xodimga biriktirilgan. Uni o'zgartirish uchun "
            "sizda maxsus ruxsat bo'lishi kerak."
        )


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


def owner_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        membership = getattr(request, "membership", None)
        if not request.user.is_superuser and (
            membership is None or membership.role != Membership.Role.OWNER
        ):
            raise PermissionDenied("Rollarni faqat tashkilot egasi boshqarishi mumkin.")
        return view_func(request, *args, **kwargs)

    return wrapped
