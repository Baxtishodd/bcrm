from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.views import PasswordResetConfirmView
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy

from apps.common.permissions import OrganizationPermission, organization_permission_required
from apps.common.tenancy import organization_required

from .forms import MailboxAccountForm
from .models import MailboxAccount
from .services import MailboxConnectionError, test_mailbox_connection


@login_required
def password_change(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    if form.is_valid():
        user = form.save()
        user.must_change_password = False
        user.save(update_fields=["must_change_password"])
        update_session_auth_hash(request, user)
        messages.success(request, "Parolingiz muvaffaqiyatli almashtirildi.")
        return redirect("dashboard")
    return render(
        request,
        "shared/form.html",
        {
            "form": form,
            "page_title": "Parolni almashtirish",
            "cancel_url": "/" if not request.user.must_change_password else "",
            "submit_label": "Parolni saqlash",
        },
    )


class AccountPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "registration/password_reset_confirm.html"
    success_url = reverse_lazy("password-reset-complete")

    def form_valid(self, form):
        response = super().form_valid(form)
        self.user.must_change_password = False
        self.user.save(update_fields=["must_change_password"])
        return response


@login_required
@organization_required
@organization_permission_required(OrganizationPermission.MANAGE_MAILBOX)
def mailbox_list(request):
    accounts = MailboxAccount.objects.filter(
        organization=request.organization,
        user=request.user,
    )
    return render(
        request,
        "accounts/mailbox_list.html",
        {"accounts": accounts, "organization": request.organization},
    )


@login_required
@organization_required
@organization_permission_required(OrganizationPermission.MANAGE_MAILBOX)
def mailbox_create(request):
    form = MailboxAccountForm(request.POST or None)
    if form.is_valid():
        account = form.save(commit=False)
        account.organization = request.organization
        account.user = request.user
        if not MailboxAccount.objects.filter(
            organization=request.organization,
            user=request.user,
        ).exists():
            account.is_default = True
        account.save()
        messages.success(request, "Email akkaunti saqlandi.")
        return redirect("accounts:mailbox-list")
    return render(
        request,
        "shared/form.html",
        {
            "form": form,
            "page_title": "Email akkauntini ulash",
            "submit_label": "Akkauntni saqlash",
            "cancel_url": "/account/email/",
            "organization": request.organization,
        },
    )


@login_required
@organization_required
@organization_permission_required(OrganizationPermission.MANAGE_MAILBOX)
def mailbox_update(request, public_id):
    account = get_object_or_404(
        MailboxAccount,
        public_id=public_id,
        organization=request.organization,
        user=request.user,
    )
    form = MailboxAccountForm(request.POST or None, instance=account)
    if form.is_valid():
        form.save()
        messages.success(request, "Email akkaunti yangilandi.")
        return redirect("accounts:mailbox-list")
    return render(
        request,
        "shared/form.html",
        {
            "form": form,
            "page_title": f"{account.email} sozlamalari",
            "submit_label": "Sozlamalarni saqlash",
            "cancel_url": "/account/email/",
            "organization": request.organization,
        },
    )


@login_required
@organization_required
@organization_permission_required(OrganizationPermission.MANAGE_MAILBOX)
def mailbox_test(request, public_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    account = get_object_or_404(
        MailboxAccount,
        public_id=public_id,
        organization=request.organization,
        user=request.user,
    )
    try:
        test_mailbox_connection(account)
    except MailboxConnectionError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, "SMTP va IMAP ulanishi muvaffaqiyatli tekshirildi.")
    return redirect("accounts:mailbox-list")
