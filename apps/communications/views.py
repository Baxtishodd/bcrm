import json
from datetime import timedelta
from pathlib import Path
from uuid import UUID

from django.conf import settings
from django.contrib import messages as flash_messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Count, OuterRef, Prefetch, Q, Subquery
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.accounts.models import MailboxAccount
from apps.common.permissions import (
    OrganizationPermission,
    ensure_record_editable,
    organization_permission_required,
)
from apps.common.tenancy import organization_required
from apps.crm.models import Activity
from apps.customers.models import Contact
from apps.organizations.models import Membership
from apps.sales.models import Quotation, QuotationDelivery
from apps.sales.pdf import build_quotation_pdf, quotation_pdf_filename

from .forms import ConversationForm, EmailComposeForm, MessageComposeForm
from .mailbox import deliver_email_message
from .models import Conversation, ConversationParticipant, Message, MessageAttachment
from .telegram import TelegramAPIError, deliver_telegram_message, process_telegram_update


def _conversation_queryset(organization, *, user=None, team_mode=False):
    conversations = Conversation.objects.filter(organization=organization).select_related(
        "customer",
        "contact",
        "lead",
        "assigned_to",
    )
    if team_mode:
        if user is None:
            return conversations.none()
        participant_count = (
            ConversationParticipant.objects.filter(conversation_id=OuterRef("pk"))
            .values("conversation_id")
            .annotate(total=Count("id"))
            .values("total")[:1]
        )
        return (
            conversations.filter(
                channel=Conversation.Channel.INTERNAL,
                participants__user=user,
            )
            .annotate(participant_total=Subquery(participant_count))
            .filter(participant_total=2)
            .prefetch_related("participants__user")
            .distinct()
        )
    return conversations.exclude(channel=Conversation.Channel.INTERNAL)


def _filtered_conversations(
    organization,
    *,
    user=None,
    team_mode=False,
    query="",
    channel="",
    mailbox="",
):
    latest_message = Message.objects.filter(conversation=OuterRef("pk")).order_by("-sent_at")
    conversations = _conversation_queryset(
        organization,
        user=user,
        team_mode=team_mode,
    ).annotate(
        latest_message_body=Subquery(latest_message.values("body")[:1])
    )
    if query:
        search = (
            Q(title__icontains=query)
            | Q(contact__full_name__icontains=query)
            | Q(customer__name__icontains=query)
            | Q(lead__title__icontains=query)
            | Q(messages__body__icontains=query)
        )
        if team_mode:
            search |= Q(participants__user__first_name__icontains=query)
            search |= Q(participants__user__last_name__icontains=query)
            search |= Q(participants__user__email__icontains=query)
        conversations = conversations.filter(search).distinct()
    if not team_mode and channel in Conversation.Channel.values:
        conversations = conversations.filter(channel=channel)
    if not team_mode and mailbox:
        try:
            mailbox_public_id = UUID(mailbox)
        except (TypeError, ValueError):
            return conversations.none()
        conversations = conversations.filter(mailbox__public_id=mailbox_public_id)
    return conversations


def _attach_team_context(conversations, user):
    for conversation in conversations:
        participants = list(conversation.participants.all())
        current = next((item for item in participants if item.user_id == user.id), None)
        peer = next((item.user for item in participants if item.user_id != user.id), user)
        conversation.team_peer = peer
        conversation.display_unread_count = current.unread_count if current else 0


def _mark_conversation_read(conversation, user, *, team_mode):
    if team_mode:
        ConversationParticipant.objects.filter(
            conversation=conversation,
            user=user,
        ).update(unread_count=0, last_read_at=timezone.now(), updated_at=timezone.now())
    elif conversation.unread_count:
        conversation.unread_count = 0
        conversation.save(update_fields=["unread_count", "updated_at"])


def _team_members(organization, user, query=""):
    memberships = (
        Membership.objects.filter(organization=organization, is_active=True)
        .exclude(user=user)
        .select_related("user", "branch", "custom_role")
        .order_by("user__first_name", "user__last_name", "user__email")
    )
    if query:
        matching_roles = [
            value
            for value, label in Membership.Role.choices
            if query.casefold() in label.casefold()
        ]
        memberships = memberships.filter(
            Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(user__email__icontains=query)
            | Q(branch__name__icontains=query)
            | Q(role__in=matching_roles)
            | Q(custom_role__name__icontains=query)
        )
    return memberships


def _render_inbox(request, public_id=None, *, team_mode=False):
    query = request.GET.get("q", "").strip()
    channel = "" if team_mode else request.GET.get("channel", "").strip()
    mailbox = "" if team_mode else request.GET.get("mailbox", "").strip()
    conversations = list(
        _filtered_conversations(
            request.organization,
            user=request.user,
            team_mode=team_mode,
            query=query,
            channel=channel,
            mailbox=mailbox,
        )
    )
    if team_mode:
        _attach_team_context(conversations, request.user)
    else:
        for conversation in conversations:
            conversation.display_unread_count = conversation.unread_count

    selected = None
    if public_id:
        selected = get_object_or_404(
            _conversation_queryset(
                request.organization,
                user=request.user,
                team_mode=team_mode,
            ).prefetch_related(
                Prefetch(
                    "messages",
                    queryset=Message.objects.select_related("sender").prefetch_related(
                        "attachments"
                    ),
                )
            ),
            public_id=public_id,
        )
        if team_mode:
            _attach_team_context([selected], request.user)
    elif conversations:
        url_name = (
            "communications:team-conversation"
            if team_mode
            else "communications:conversation"
        )
        return redirect(url_name, public_id=conversations[0].public_id)

    if selected:
        _mark_conversation_read(selected, request.user, team_mode=team_mode)
        if team_mode:
            for conversation in conversations:
                if conversation.pk == selected.pk:
                    conversation.display_unread_count = 0
                    break

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
            "channel_choices": [
                item for item in Conversation.Channel.choices
                if item[0] != Conversation.Channel.INTERNAL
            ],
            "mailboxes": (
                MailboxAccount.objects.none()
                if team_mode
                else MailboxAccount.objects.filter(
                    organization=request.organization,
                    is_active=True,
                ).select_related("user")
            ),
            "telegram_enabled": bool(settings.TELEGRAM_SUPPORT_BOT),
            "team_mode": team_mode,
            "team_members": (
                _team_members(request.organization, request.user, query)
                if team_mode
                else Membership.objects.none()
            ),
            "organization": request.organization,
        },
    )


@login_required
@organization_required
@organization_permission_required(OrganizationPermission.VIEW_MAILBOX)
def inbox(request, public_id=None):
    return _render_inbox(request, public_id, team_mode=False)


@login_required
@organization_required
def team_inbox(request, public_id=None):
    return _render_inbox(request, public_id, team_mode=True)


def _sync_inbox(request, *, team_mode=False):
    public_id = request.GET.get("conversation", "").strip()
    query = request.GET.get("q", "").strip()
    channel = "" if team_mode else request.GET.get("channel", "").strip()
    mailbox = "" if team_mode else request.GET.get("mailbox", "").strip()
    try:
        after_id = max(0, int(request.GET.get("after", "0")))
    except (TypeError, ValueError):
        after_id = 0

    selected = None
    new_messages = Message.objects.none()
    if public_id:
        selected = get_object_or_404(
            _conversation_queryset(
                request.organization,
                user=request.user,
                team_mode=team_mode,
            ),
            public_id=public_id,
        )
        if team_mode:
            _attach_team_context([selected], request.user)
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
        _mark_conversation_read(selected, request.user, team_mode=team_mode)

    conversations = list(
        _filtered_conversations(
            request.organization,
            user=request.user,
            team_mode=team_mode,
            query=query,
            channel=channel,
            mailbox=mailbox,
        )
    )
    if team_mode:
        _attach_team_context(conversations, request.user)
    else:
        for conversation in conversations:
            conversation.display_unread_count = conversation.unread_count
    message_items = list(new_messages)
    selected_avatar_url = ""
    if selected and team_mode and selected.team_peer.avatar:
        selected_avatar_url = selected.team_peer.avatar.url
    elif selected and selected.telegram_avatar:
        selected_avatar_url = selected.telegram_avatar.url
    response = JsonResponse(
        {
            "conversation_list_html": render_to_string(
                "communications/_conversation_list.html",
                {
                    "conversations": conversations,
                    "selected_conversation": selected,
                    "team_mode": team_mode,
                },
                request=request,
            ),
            "messages_html": render_to_string(
                "communications/_message_items.html",
                {
                    "message_items": message_items,
                    "show_empty": False,
                    "team_mode": team_mode,
                },
                request=request,
            ),
            "latest_message_id": max([after_id, *(item.id for item in message_items)]),
            "selected_avatar_url": selected_avatar_url,
        }
    )
    response["Cache-Control"] = "no-store"
    return response


@login_required
@organization_required
@organization_permission_required(OrganizationPermission.UPDATE_MAILBOX)
def inbox_sync(request):
    return _sync_inbox(request, team_mode=False)


@login_required
@organization_required
def team_inbox_sync(request):
    return _sync_inbox(request, team_mode=True)


@login_required
@organization_required
@require_POST
def start_internal_conversation(request, membership_id):
    target_membership = get_object_or_404(
        Membership.objects.select_related("user"),
        public_id=membership_id,
        organization=request.organization,
        is_active=True,
    )
    if target_membership.user_id == request.user.id:
        raise PermissionDenied("O'zingiz bilan ichki chat ochib bo'lmaydi.")
    user_ids = sorted([request.user.id, target_membership.user_id])
    direct_key = f"{user_ids[0]}:{user_ids[1]}"
    with transaction.atomic():
        conversation = Conversation.objects.select_for_update().filter(
            organization=request.organization,
            channel=Conversation.Channel.INTERNAL,
            internal_direct_key=direct_key,
        ).first()
        if conversation is None:
            participant_count = (
                ConversationParticipant.objects.filter(conversation_id=OuterRef("pk"))
                .values("conversation_id")
                .annotate(total=Count("id"))
                .values("total")[:1]
            )
            conversation = (
                Conversation.objects.select_for_update()
                .filter(
                    organization=request.organization,
                    channel=Conversation.Channel.INTERNAL,
                    participants__user_id=user_ids[0],
                )
                .filter(participants__user_id=user_ids[1])
                .annotate(participant_total=Subquery(participant_count))
                .filter(participant_total=2)
                .order_by("id")
                .first()
            )
        if conversation is None:
            conversation = Conversation.objects.create(
                organization=request.organization,
                channel=Conversation.Channel.INTERNAL,
                internal_direct_key=direct_key,
                title="Jamoa suhbati",
            )
        elif conversation.internal_direct_key != direct_key:
            conversation.internal_direct_key = direct_key
            conversation.save(update_fields=["internal_direct_key", "updated_at"])
        ConversationParticipant.objects.get_or_create(
            organization=request.organization,
            conversation=conversation,
            user=request.user,
        )
        ConversationParticipant.objects.get_or_create(
            organization=request.organization,
            conversation=conversation,
            user=target_membership.user,
        )
    return redirect("communications:team-conversation", public_id=conversation.public_id)


@login_required
@organization_required
@organization_permission_required(OrganizationPermission.CREATE_MAILBOX)
def conversation_create(request):
    form = ConversationForm(request.POST or None, organization=request.organization)
    if form.is_valid():
        conversation = form.save(commit=False)
        conversation.organization = request.organization
        conversation.full_clean()
        conversation.save()
        participant_users = [request.user]
        if conversation.assigned_to_id and conversation.assigned_to_id != request.user.id:
            participant_users.append(conversation.assigned_to)
        for user in participant_users:
            ConversationParticipant.objects.get_or_create(
                organization=request.organization,
                conversation=conversation,
                user=user,
            )
        flash_messages.success(request, "Yangi suhbat yaratildi.")
        return redirect("communications:team-conversation", public_id=conversation.public_id)
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


def _email_compose_quotation(request, value):
    if not value:
        return None
    if not request.crm_permissions.get(OrganizationPermission.UPDATE_SALES, False):
        raise PermissionDenied("Tijorat taklifini yuborish uchun ruxsat mavjud emas.")
    quotation = get_object_or_404(
        Quotation.objects.select_related(
            "organization",
            "customer",
            "contact",
            "lead",
            "assigned_to",
        ).prefetch_related(
            "lines__product",
            "lines__variant__color",
            "lines__variant__size",
        ),
        public_id=value,
        organization=request.organization,
    )
    ensure_record_editable(request, quotation)
    return quotation


def _email_compose_initial(request, quotation):
    initial = {
        "to": request.GET.get("to", ""),
        "subject": request.GET.get("subject", ""),
        "send_mode": EmailComposeForm.SendMode.INDIVIDUAL,
    }
    if quotation:
        recipient = ""
        if quotation.contact and quotation.contact.email:
            recipient = quotation.contact.email
        elif quotation.customer.email:
            recipient = quotation.customer.email
        initial.update(
            {
                "to": recipient,
                "subject": (
                    f"{quotation.number} — "
                    f"{request.organization.document_name} tijorat taklifi"
                ),
                "body": (
                    f"Assalomu alaykum,\n\n{quotation.number} raqamli tijorat taklifini "
                    "PDF ko'rinishida ilova qilmoqdamiz.\n\nHurmat bilan,\n"
                    f"{request.organization.document_name}"
                ),
                "quotation": quotation.public_id,
            }
        )
    return initial


def _record_quotation_delivery(*, quotation, message, sent, actor, filename):
    QuotationDelivery.objects.create(
        organization=quotation.organization,
        quotation=quotation,
        channel=QuotationDelivery.Channel.EMAIL,
        recipient=", ".join(message.email_to),
        sender=message.mailbox.email if message.mailbox else "",
        subject=message.email_subject[:255],
        message=message.body,
        status=(
            QuotationDelivery.Status.SENT if sent else QuotationDelivery.Status.FAILED
        ),
        sent_by=actor,
        notes=(
            f"{filename} PDF fayli ilova qilindi."
            if sent
            else message.error_message or "Email yuborilmadi."
        ),
    )


@login_required
@organization_required
@organization_permission_required(OrganizationPermission.CREATE_MAILBOX)
def email_compose(request):
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    quotation_value = request.POST.get("quotation") or request.GET.get("quotation")
    quotation = _email_compose_quotation(request, quotation_value)
    form = EmailComposeForm(
        request.POST or None,
        request.FILES or None,
        organization=request.organization,
        user=request.user,
        initial=_email_compose_initial(request, quotation) if request.method == "GET" else None,
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
        quotation_filename = quotation_pdf_filename(quotation) if quotation else ""
        quotation_pdf = build_quotation_pdf(quotation) if quotation else None

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
                    contact=quotation.contact if quotation else contact,
                    customer=(
                        quotation.customer
                        if quotation
                        else contact.company if contact else None
                    ),
                    lead=quotation.lead if quotation else None,
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
                        "body_html": form.cleaned_data["body_html"],
                        **(
                            {"quotation_public_id": str(quotation.public_id)}
                            if quotation
                            else {}
                        ),
                    },
                )
                if quotation_pdf is not None:
                    _save_message_attachments(
                        communication_message,
                        [ContentFile(quotation_pdf, name=quotation_filename)],
                    )
                _save_message_attachments(
                    communication_message,
                    form.cleaned_data["attachments"],
                )
            if first_conversation is None:
                first_conversation = conversation
            sent = deliver_email_message(communication_message)
            if sent:
                sent_count += 1
            else:
                failed_count += 1
            if quotation:
                _record_quotation_delivery(
                    quotation=quotation,
                    message=communication_message,
                    sent=sent,
                    actor=request.user,
                    filename=quotation_filename,
                )

        if quotation and sent_count:
            if quotation.status == Quotation.Status.DRAFT:
                quotation.status = Quotation.Status.SENT
                quotation.save(update_fields=["status", "updated_at"])
            Activity.objects.create(
                organization=request.organization,
                lead=quotation.lead,
                customer=quotation.customer,
                activity_type=Activity.Type.TASK,
                subject=f"{quotation.number} taklifi bo'yicha bog'lanish",
                details=(
                    f"{', '.join(recipients)} manziliga yuborilgan taklif bo'yicha "
                    "javobni aniqlash."
                ),
                due_at=timezone.now() + timedelta(days=3),
                assigned_to=quotation.assigned_to or request.user,
            )

        result_message = ""
        if sent_count:
            result_message = f"{sent_count} ta email muvaffaqiyatli yuborildi."
            flash_messages.success(
                request,
                result_message,
            )
        if failed_count:
            result_message = f"{failed_count} ta email yuborilmadi."
            flash_messages.error(
                request,
                f"{failed_count} ta email yuborilmadi. Suhbat ichida xatolik tafsiloti saqlandi.",
            )
        if is_ajax:
            return JsonResponse(
                {
                    "ok": failed_count == 0,
                    "message": result_message,
                    "conversation_url": (
                        request.build_absolute_uri(
                            f"/messages/{first_conversation.public_id}/"
                        )
                        if first_conversation
                        else ""
                    ),
                },
                status=200 if failed_count == 0 else 502,
            )
        return redirect(
            "communications:conversation",
            public_id=first_conversation.public_id,
        )

    if request.method == "POST" and is_ajax:
        return JsonResponse(
            {
                "ok": False,
                "errors": {
                    field: [str(error) for error in errors]
                    for field, errors in form.errors.items()
                },
            },
            status=422,
        )

    contacts = Contact.objects.filter(
        organization=request.organization,
        is_active=True,
    ).exclude(email="").select_related("company")
    context = {
        "form": form,
        "contacts": contacts,
        "organization": request.organization,
        "quotation": quotation,
    }
    if is_ajax:
        return render(request, "communications/_email_compose_window.html", context)
    return render(
        request,
        "communications/email_compose.html",
        context,
    )


@login_required
@organization_required
@require_POST
def message_create(request, public_id):
    conversation = get_object_or_404(
        Conversation,
        public_id=public_id,
        organization=request.organization,
    )
    if conversation.channel == Conversation.Channel.INTERNAL:
        if not conversation.participants.filter(user=request.user).exists():
            raise PermissionDenied("Bu jamoa suhbatida ishtirok etmaysiz.")
    elif not request.crm_permissions.get(OrganizationPermission.CREATE_MAILBOX, False):
        raise PermissionDenied("Bu kanalga xabar yuborish uchun ruxsat mavjud emas.")
    conversation_url = (
        "communications:team-conversation"
        if conversation.channel == Conversation.Channel.INTERNAL
        else "communications:conversation"
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
        return redirect(conversation_url, public_id=conversation.public_id)

    if conversation.status != Conversation.Status.OPEN:
        flash_messages.error(request, "Yopilgan yoki arxivlangan suhbatga xabar yuborib bo'lmaydi.")
        return redirect(conversation_url, public_id=conversation.public_id)

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
    return redirect(conversation_url, public_id=conversation.public_id)


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
