import json
from pathlib import Path
from uuid import UUID

from django.conf import settings
from django.contrib import messages as flash_messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.db.models import OuterRef, Prefetch, Q, Subquery
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils.crypto import constant_time_compare
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.accounts.models import MailboxAccount
from apps.common.permissions import OrganizationPermission, organization_permission_required
from apps.common.tenancy import organization_required
from apps.customers.models import Contact

from .forms import ConversationForm, EmailComposeForm, MessageComposeForm
from .mailbox import deliver_email_message
from .models import Conversation, Message, MessageAttachment
from .telegram import TelegramAPIError, deliver_telegram_message, process_telegram_update


def _conversation_queryset(organization):
    return Conversation.objects.filter(organization=organization).select_related(
        "customer",
        "contact",
        "lead",
        "assigned_to",
    )


def _filtered_conversations(organization, *, query="", channel="", mailbox=""):
    latest_message = Message.objects.filter(conversation=OuterRef("pk")).order_by("-sent_at")
    conversations = _conversation_queryset(organization).annotate(
        latest_message_body=Subquery(latest_message.values("body")[:1])
    )
    if query:
        conversations = conversations.filter(
            Q(title__icontains=query)
            | Q(contact__full_name__icontains=query)
            | Q(customer__name__icontains=query)
            | Q(lead__title__icontains=query)
            | Q(messages__body__icontains=query)
        ).distinct()
    if channel in Conversation.Channel.values:
        conversations = conversations.filter(channel=channel)
    if mailbox:
        try:
            mailbox_public_id = UUID(mailbox)
        except (TypeError, ValueError):
            return conversations.none()
        conversations = conversations.filter(mailbox__public_id=mailbox_public_id)
    return conversations


@login_required
@organization_required
@organization_permission_required(OrganizationPermission.MANAGE_MAILBOX)
def inbox(request, public_id=None):
    query = request.GET.get("q", "").strip()
    channel = request.GET.get("channel", "").strip()
    mailbox = request.GET.get("mailbox", "").strip()
    conversations = list(
        _filtered_conversations(
            request.organization,
            query=query,
            channel=channel,
            mailbox=mailbox,
        )
    )

    selected = None
    if public_id:
        selected = get_object_or_404(
            _conversation_queryset(request.organization).prefetch_related(
                Prefetch(
                    "messages",
                    queryset=Message.objects.select_related("sender").prefetch_related("attachments"),
                )
            ),
            public_id=public_id,
        )
    elif conversations:
        return redirect("communications:conversation", public_id=conversations[0].public_id)

    if selected and selected.unread_count:
        selected.unread_count = 0
        selected.save(update_fields=["unread_count", "updated_at"])

    return render(
        request,
        "communications/inbox.html",
        {
            "conversations": conversations,
            "selected_conversation": selected,
            "compose_form": MessageComposeForm(),
            "query": query,
            "selected_channel": channel,
            "selected_mailbox": mailbox,
            "channel_choices": Conversation.Channel.choices,
            "mailboxes": MailboxAccount.objects.filter(
                organization=request.organization,
                is_active=True,
            ).select_related("user"),
            "telegram_enabled": bool(settings.TELEGRAM_SUPPORT_BOT),
            "organization": request.organization,
        },
    )


@login_required
@organization_required
@organization_permission_required(OrganizationPermission.MANAGE_MAILBOX)
def inbox_sync(request):
    public_id = request.GET.get("conversation", "").strip()
    query = request.GET.get("q", "").strip()
    channel = request.GET.get("channel", "").strip()
    mailbox = request.GET.get("mailbox", "").strip()
    try:
        after_id = max(0, int(request.GET.get("after", "0")))
    except (TypeError, ValueError):
        after_id = 0

    selected = None
    new_messages = Message.objects.none()
    if public_id:
        selected = get_object_or_404(
            _conversation_queryset(request.organization),
            public_id=public_id,
        )
        new_messages = (
            Message.objects.filter(
                organization=request.organization,
                conversation=selected,
                id__gt=after_id,
            )
            .select_related("sender")
            .prefetch_related("attachments")
            .order_by("sent_at", "id")
        )
        if selected.unread_count:
            selected.unread_count = 0
            selected.save(update_fields=["unread_count", "updated_at"])

    conversations = list(
        _filtered_conversations(
            request.organization,
            query=query,
            channel=channel,
            mailbox=mailbox,
        )
    )
    message_items = list(new_messages)
    response = JsonResponse(
        {
            "conversation_list_html": render_to_string(
                "communications/_conversation_list.html",
                {
                    "conversations": conversations,
                    "selected_conversation": selected,
                },
                request=request,
            ),
            "messages_html": render_to_string(
                "communications/_message_items.html",
                {"message_items": message_items, "show_empty": False},
                request=request,
            ),
            "latest_message_id": max(
                [after_id, *(item.id for item in message_items)],
            ),
            "selected_avatar_url": (
                selected.telegram_avatar.url
                if selected and selected.telegram_avatar
                else ""
            ),
        }
    )
    response["Cache-Control"] = "no-store"
    return response


@login_required
@organization_required
@organization_permission_required(OrganizationPermission.MANAGE_MAILBOX)
def conversation_create(request):
    form = ConversationForm(request.POST or None, organization=request.organization)
    if form.is_valid():
        conversation = form.save(commit=False)
        conversation.organization = request.organization
        conversation.full_clean()
        conversation.save()
        flash_messages.success(request, "Yangi suhbat yaratildi.")
        return redirect("communications:conversation", public_id=conversation.public_id)
    return render(
        request,
        "shared/form.html",
        {
            "form": form,
            "page_title": "Yangi suhbat",
            "cancel_url": "/messages/",
            "organization": request.organization,
        },
    )


def _attachment_kind(attachment):
    content_type = getattr(attachment, "content_type", "") or ""
    if content_type.startswith("image/"):
        return MessageAttachment.Kind.IMAGE
    if Path(attachment.name).suffix.lower() in {
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".txt",
    }:
        return MessageAttachment.Kind.DOCUMENT
    return MessageAttachment.Kind.OTHER


def _save_message_attachments(message, attachments):
    for attachment in attachments:
        attachment.seek(0)
        MessageAttachment.objects.create(
            organization=message.organization,
            message=message,
            file=attachment,
            original_name=Path(attachment.name).name[:255],
            content_type=(getattr(attachment, "content_type", "") or "")[:120],
            size=attachment.size,
            kind=_attachment_kind(attachment),
        )


@login_required
@organization_required
@organization_permission_required(OrganizationPermission.MANAGE_MAILBOX)
def email_compose(request):
    form = EmailComposeForm(
        request.POST or None,
        request.FILES or None,
        organization=request.organization,
        user=request.user,
    )
    if request.method == "POST" and form.is_valid():
        recipients = form.cleaned_data["to"]
        send_mode = form.cleaned_data["send_mode"]
        recipient_groups = (
            [[recipient] for recipient in recipients]
            if send_mode == EmailComposeForm.SendMode.INDIVIDUAL
            else [recipients]
        )
        sent_count = 0
        failed_count = 0
        first_conversation = None

        for recipient_group in recipient_groups:
            primary_recipient = recipient_group[0]
            contact = None
            if len(recipient_group) == 1:
                contact = (
                    Contact.objects.filter(
                        organization=request.organization,
                        email__iexact=primary_recipient,
                        is_active=True,
                    )
                    .select_related("company")
                    .first()
                )
            with transaction.atomic():
                conversation = Conversation.objects.create(
                    organization=request.organization,
                    channel=Conversation.Channel.EMAIL,
                    title=form.cleaned_data["subject"][:220],
                    external_chat_id=primary_recipient,
                    mailbox=form.cleaned_data["mailbox"],
                    contact=contact,
                    customer=contact.company if contact else None,
                    assigned_to=request.user,
                )
                communication_message = Message.objects.create(
                    organization=request.organization,
                    conversation=conversation,
                    direction=Message.Direction.OUTBOUND,
                    status=Message.Status.PENDING,
                    sender=request.user,
                    sender_name=request.user.get_full_name() or request.user.email,
                    body=form.cleaned_data["body"].strip(),
                    mailbox=form.cleaned_data["mailbox"],
                    email_subject=form.cleaned_data["subject"],
                    email_to=recipient_group,
                    email_cc=form.cleaned_data["cc"],
                    metadata={
                        "email_bcc": form.cleaned_data["bcc"],
                        "send_mode": send_mode,
                    },
                )
                _save_message_attachments(
                    communication_message,
                    form.cleaned_data["attachments"],
                )
            if first_conversation is None:
                first_conversation = conversation
            if deliver_email_message(communication_message):
                sent_count += 1
            else:
                failed_count += 1

        if sent_count:
            flash_messages.success(
                request,
                f"{sent_count} ta email muvaffaqiyatli yuborildi.",
            )
        if failed_count:
            flash_messages.error(
                request,
                f"{failed_count} ta email yuborilmadi. Suhbat ichida xatolik tafsiloti saqlandi.",
            )
        return redirect(
            "communications:conversation",
            public_id=first_conversation.public_id,
        )

    contacts = Contact.objects.filter(
        organization=request.organization,
        is_active=True,
    ).exclude(email="").select_related("company")
    return render(
        request,
        "communications/email_compose.html",
        {
            "form": form,
            "contacts": contacts,
            "organization": request.organization,
        },
    )


@login_required
@organization_required
@organization_permission_required(OrganizationPermission.MANAGE_MAILBOX)
@require_POST
def message_create(request, public_id):
    conversation = get_object_or_404(
        Conversation,
        public_id=public_id,
        organization=request.organization,
    )
    form = MessageComposeForm(request.POST, request.FILES)
    if not form.is_valid():
        error = next(iter(form.non_field_errors()), None)
        if not error:
            error = next(
                (errors[0] for errors in form.errors.values() if errors),
                "Xabar yuborilmadi.",
            )
        flash_messages.error(request, error)
        return redirect("communications:conversation", public_id=conversation.public_id)

    if conversation.status != Conversation.Status.OPEN:
        flash_messages.error(request, "Yopilgan yoki arxivlangan suhbatga xabar yuborib bo'lmaydi.")
        return redirect("communications:conversation", public_id=conversation.public_id)

    attachment = form.cleaned_data.get("attachment")
    with transaction.atomic():
        communication_message = Message.objects.create(
            organization=request.organization,
            conversation=conversation,
            direction=Message.Direction.OUTBOUND,
            status=(
                Message.Status.SENT
                if conversation.channel == Conversation.Channel.INTERNAL
                else Message.Status.PENDING
            ),
            sender=request.user,
            sender_name=request.user.get_full_name() or request.user.email,
            body=form.cleaned_data.get("body", "").strip(),
        )
        if attachment:
            _save_message_attachments(communication_message, [attachment])

    if conversation.channel == Conversation.Channel.TELEGRAM:
        if not deliver_telegram_message(communication_message):
            flash_messages.error(
                request,
                f"Telegram xabari yuborilmadi: {communication_message.error_message}",
            )
    elif conversation.channel == Conversation.Channel.EMAIL:
        if not deliver_email_message(communication_message):
            flash_messages.error(
                request,
                f"Email yuborilmadi: {communication_message.error_message}",
            )
    elif conversation.channel != Conversation.Channel.INTERNAL:
        flash_messages.info(
            request,
            "Xabar navbatga saqlandi. Kanal integratsiyasi ulangach yuboriladi.",
        )
    return redirect("communications:conversation", public_id=conversation.public_id)


@csrf_exempt
@require_POST
def telegram_webhook(request):
    expected_secret = settings.TELEGRAM_WEBHOOK_SECRET
    supplied_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not expected_secret:
        return JsonResponse({"ok": False, "error": "Webhook secret sozlanmagan."}, status=503)
    if not constant_time_compare(supplied_secret, expected_secret):
        return JsonResponse({"ok": False}, status=403)
    if len(request.body) > 1024 * 1024:
        return JsonResponse({"ok": False, "error": "Update juda katta."}, status=413)
    try:
        update = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"ok": False, "error": "Noto'g'ri JSON."}, status=400)
    try:
        process_telegram_update(update)
    except (TelegramAPIError, ImproperlyConfigured) as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=503)
    return JsonResponse({"ok": True})
