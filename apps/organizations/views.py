from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_POST

from apps.common.permissions import (
    OrganizationPermission,
    organization_permission_required,
    owner_required,
)
from apps.common.tenancy import organization_required

from .forms import (
    EmployeeCreateForm,
    EmployeeUpdateForm,
    OrganizationRoleForm,
    OrganizationSettingsForm,
)
from .models import Membership, RolePermission


def _permission_rows(form):
    return [
        {
            "module": module,
            "label": label,
            "fields": [
                form[OrganizationRoleForm.permission_field_name(module, action)]
                for action in RolePermission.Action.values
            ],
        }
        for module, label in RolePermission.Module.choices
    ]


@login_required
@organization_required
@organization_permission_required(OrganizationPermission.UPDATE_ORGANIZATION)
def organization_settings(request):
    form = OrganizationSettingsForm(
        request.POST or None,
        request.FILES or None,
        instance=request.organization,
    )
    if form.is_valid():
        form.save()
        messages.success(request, "Tashkilot sozlamalari saqlandi.")
        return redirect("organizations:settings")

    return render(
        request,
        "organizations/settings.html",
        {
            "form": form,
            "organization": request.organization,
        },
    )


@login_required
@organization_required
@organization_permission_required(OrganizationPermission.VIEW_ORGANIZATION)
def employee_list(request):
    memberships = request.organization.memberships.select_related(
        "user", "branch", "custom_role"
    )
    query = request.GET.get("q", "").strip()
    role = request.GET.get("role", "").strip()
    status = request.GET.get("status", "").strip()
    if query:
        memberships = memberships.filter(
            Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(user__email__icontains=query)
            | Q(user__phone__icontains=query)
        )
    if role.startswith("custom:"):
        memberships = memberships.filter(
            custom_role__public_id=role.removeprefix("custom:")
        )
    elif role in Membership.Role.values:
        memberships = memberships.filter(role=role)
    if status == "active":
        memberships = memberships.filter(is_active=True)
    elif status == "inactive":
        memberships = memberships.filter(is_active=False)
    memberships = memberships.order_by("-is_active", "user__first_name", "user__email")
    page = Paginator(memberships, 25).get_page(request.GET.get("page"))
    pagination_query = request.GET.copy()
    pagination_query.pop("page", None)
    return render(
        request,
        "organizations/employee_list.html",
        {
            "page": page,
            "query": query,
            "role": role,
            "status": status,
            "builtin_role_choices": Membership.Role.choices,
            "custom_role_choices": [
                (f"custom:{item.public_id}", item.name)
                for item in request.organization.custom_roles.all()
            ],
            "paginator": page.paginator,
            "page_obj": page,
            "pagination_query": pagination_query.urlencode(),
            "pagination_page_range": page.paginator.get_elided_page_range(page.number),
        },
    )


@sensitive_post_parameters("password1", "password2")
@login_required
@organization_required
@organization_permission_required(OrganizationPermission.CREATE_ORGANIZATION)
def employee_create(request):
    form = EmployeeCreateForm(
        request.POST or None,
        request.FILES or None,
        organization=request.organization,
    )
    if form.is_valid():
        with transaction.atomic():
            membership = form.save()
        messages.success(request, f"{membership.user.email} xodim sifatida qo'shildi.")
        return redirect("organizations:employees")
    return render(
        request,
        "shared/form.html",
        {
            "form": form,
            "page_title": "Yangi xodim",
            "cancel_url": reverse("organizations:employees"),
            "submit_label": "Xodimni qo'shish",
        },
    )


@login_required
@organization_required
@organization_permission_required(OrganizationPermission.UPDATE_ORGANIZATION)
def employee_update(request, public_id):
    membership = get_object_or_404(
        request.organization.memberships.select_related("user", "branch"),
        public_id=public_id,
    )
    if (
        request.membership.role == Membership.Role.DIRECTOR
        and membership.role == Membership.Role.OWNER
    ):
        return HttpResponseForbidden("Tashkilot egasini faqat egasining o'zi boshqaradi.")
    form = EmployeeUpdateForm(
        request.POST or None,
        request.FILES or None,
        membership=membership,
        actor_membership=request.membership,
    )
    if form.is_valid():
        with transaction.atomic():
            form.save()
        messages.success(request, "Xodim ma'lumotlari saqlandi.")
        return redirect("organizations:employees")
    return render(
        request,
        "shared/form.html",
        {
            "form": form,
            "page_title": "Xodimni tahrirlash",
            "cancel_url": reverse("organizations:employees"),
            "submit_label": "O'zgarishlarni saqlash",
        },
    )


@login_required
@organization_required
@owner_required
def role_list(request):
    roles = request.organization.custom_roles.annotate(
        employee_count=Count("memberships")
    )
    return render(
        request,
        "organizations/role_list.html",
        {
            "roles": roles,
            "modules": RolePermission.Module.choices,
            "actions": RolePermission.Action.choices,
        },
    )


@login_required
@organization_required
@owner_required
def role_create(request):
    form = OrganizationRoleForm(
        request.POST or None,
        organization=request.organization,
    )
    if form.is_valid():
        with transaction.atomic():
            role = form.save()
        messages.success(request, f"“{role.name}” roli yaratildi.")
        return redirect("organizations:roles")
    return render(
        request,
        "organizations/role_form.html",
        {
            "form": form,
            "permission_rows": _permission_rows(form),
            "page_title": "Yangi rol",
            "submit_label": "Rolni yaratish",
        },
    )


@login_required
@organization_required
@owner_required
def role_update(request, public_id):
    role = get_object_or_404(
        request.organization.custom_roles,
        public_id=public_id,
    )
    form = OrganizationRoleForm(
        request.POST or None,
        instance=role,
        organization=request.organization,
    )
    if form.is_valid():
        with transaction.atomic():
            role = form.save()
        messages.success(request, f"“{role.name}” roli saqlandi.")
        return redirect("organizations:roles")
    return render(
        request,
        "organizations/role_form.html",
        {
            "form": form,
            "role": role,
            "permission_rows": _permission_rows(form),
            "page_title": "Rolni tahrirlash",
            "submit_label": "O‘zgarishlarni saqlash",
        },
    )


@require_POST
@login_required
@organization_required
@owner_required
def role_delete(request, public_id):
    role = get_object_or_404(
        request.organization.custom_roles.annotate(
            employee_count=Count("memberships")
        ),
        public_id=public_id,
    )
    if role.employee_count:
        messages.error(
            request,
            "Rol xodimlarga biriktirilgan. Avval ularni boshqa rolga o'tkazing.",
        )
    else:
        name = role.name
        role.delete()
        messages.success(request, f"“{name}” roli o‘chirildi.")
    return redirect("organizations:roles")
