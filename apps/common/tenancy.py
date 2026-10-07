from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from apps.organizations.models import Membership

from .permissions import permissions_for_membership


def get_membership(user):
    if not user.is_authenticated:
        return None
    return (
        Membership.objects.select_related("organization")
        .filter(user=user, is_active=True, organization__is_active=True)
        .first()
    )


def organization_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        membership = getattr(request, "membership", None) or get_membership(request.user)
        if membership is None:
            messages.error(request, "Sizga faol korxona biriktirilmagan.")
            return redirect("dashboard")
        request.membership = membership
        request.organization = membership.organization
        request.crm_permissions = permissions_for_membership(
            membership,
            is_superuser=request.user.is_superuser,
        )
        return view_func(request, *args, **kwargs)

    return wrapped
