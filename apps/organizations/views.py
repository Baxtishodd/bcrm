from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.common.tenancy import organization_required

from .forms import OrganizationSettingsForm
from .models import Membership


@login_required
@organization_required
def organization_settings(request):
    can_manage = request.user.is_superuser or request.membership.role in {
        Membership.Role.OWNER,
        Membership.Role.DIRECTOR,
    }
    if not can_manage:
        messages.error(
            request,
            "Tashkilot sozlamalarini faqat egasi yoki direktori o'zgartira oladi.",
        )
        return redirect("dashboard")

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
