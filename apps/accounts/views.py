from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render

from apps.common.tenancy import organization_required

from .forms import MailboxAccountForm
from .models import MailboxAccount
from .services import MailboxConnectionError, test_mailbox_connection


@login_required
@organization_required
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
