import html
import imaplib
import re
import smtplib
import ssl
from datetime import UTC, date, timedelta
from email import policy
from email.header import decode_header, make_header
from email.parser import BytesParser
from email.utils import formataddr, getaddresses, make_msgid, parseaddr, parsedate_to_datetime
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.mail import EmailMessage, get_connection
from django.db import transaction
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.text import get_valid_filename

from apps.accounts.models import MailboxAccount
from apps.customers.models import Contact

from .models import (
    ALLOWED_ATTACHMENT_EXTENSIONS,
    MAX_ATTACHMENT_BYTES,
    Conversation,
    MailboxSyncState,
    Message,
    MessageAttachment,
)


class EmailSyncError(Exception):
    pass


def _header(value):
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value))).strip()
    except (LookupError, UnicodeDecodeError):
        return str(value).strip()


def _message_ids(value):
    return re.findall(r"<[^>]+>", value or "")


def _normalize_subject(subject):
    value = subject.strip()
    while True:
        normalized = re.sub(r"^(re|fw|fwd)\s*:\s*", "", value, flags=re.IGNORECASE).strip()
        if normalized == value:
            return value
        value = normalized


def _email_addresses(*values):
    return [address.lower() for _, address in getaddresses(values) if address]


def _plain_body(parsed):
    body = parsed.get_body(preferencelist=("plain",))
    if body:
        try:
            return body.get_content().strip()
        except (LookupError, UnicodeDecodeError):
            pass
    html_body = parsed.get_body(preferencelist=("html",))
    if html_body:
        try:
            return html.unescape(strip_tags(html_body.get_content())).strip()
        except (LookupError, UnicodeDecodeError):
            pass
    if parsed.get_content_maintype() == "text":
        try:
            return parsed.get_content().strip()
        except (LookupError, UnicodeDecodeError):
            return ""
    return ""


def _sent_at(parsed):
    try:
        value = parsedate_to_datetime(parsed.get("Date"))
    except (TypeError, ValueError, OverflowError):
        return timezone.now()
    if value is None:
        return timezone.now()
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _contact_for_sender(organization, sender_email):
    if not sender_email:
        return None
    return (
        Contact.objects.filter(
            organization=organization,
            email__iexact=sender_email,
        )
        .select_related("company")
        .first()
    )


def _conversation_for_email(account, parsed, sender_email, sender_name, subject):
    references = _message_ids(parsed.get("References"))
    in_reply_to = _message_ids(parsed.get("In-Reply-To"))
    parent_ids = [*reversed(in_reply_to), *reversed(references)]
    parent = (
        Message.objects.filter(
            organization=account.organization,
            mailbox=account,
            email_message_id__in=parent_ids,
        )
        .select_related("conversation")
        .first()
        if parent_ids
        else None
    )
    if parent:
        return parent.conversation

    message_id = (parsed.get("Message-ID") or "").strip()
    contact = _contact_for_sender(account.organization, sender_email)
    return Conversation.objects.create(
        organization=account.organization,
        channel=Conversation.Channel.EMAIL,
        title=subject or sender_name or sender_email or "Mavzusiz email",
        external_chat_id=sender_email,
        mailbox=account,
        email_thread_key=(references[0] if references else message_id)[:255],
        contact=contact,
        customer=contact.company if contact else None,
        assigned_to=account.user,
    )


def _save_email_attachments(message, parsed):
    for part in parsed.iter_attachments():
        content = part.get_payload(decode=True) or b""
        if not content or len(content) > MAX_ATTACHMENT_BYTES:
            continue
        original_name = _header(part.get_filename()) or "attachment"
        safe_name = get_valid_filename(Path(original_name).name) or "attachment"
        extension = Path(safe_name).suffix.lower().lstrip(".")
        if extension not in ALLOWED_ATTACHMENT_EXTENSIONS:
            continue
        content_type = part.get_content_type()
        kind = MessageAttachment.Kind.OTHER
        if content_type.startswith("image/"):
            kind = MessageAttachment.Kind.IMAGE
        elif content_type.startswith("text/") or content_type in {
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }:
            kind = MessageAttachment.Kind.DOCUMENT
        attachment = MessageAttachment(
            organization=message.organization,
            message=message,
            original_name=safe_name[:255],
            content_type=content_type[:120],
            size=len(content),
            kind=kind,
        )
        attachment.file.save(safe_name, ContentFile(content), save=False)
        attachment.save()


def import_email_message(account, raw_message, *, folder, uid_validity, uid):
    if Message.objects.filter(
        mailbox=account,
        email_folder=folder,
        imap_uid_validity=uid_validity,
        imap_uid=uid,
    ).exists():
        return None
    parsed = BytesParser(policy=policy.default).parsebytes(raw_message)
    subject = _header(parsed.get("Subject"))
    sender_name, sender_email = parseaddr(_header(parsed.get("From")))
    sender_email = sender_email.lower()
    message_id = (parsed.get("Message-ID") or "").strip()[:255]
    in_reply_to = (parsed.get("In-Reply-To") or "").strip()[:255]
    references = _message_ids(parsed.get("References"))

    with transaction.atomic():
        conversation = _conversation_for_email(
            account,
            parsed,
            sender_email,
            sender_name,
            subject,
        )
        message = Message.objects.create(
            organization=account.organization,
            conversation=conversation,
            direction=Message.Direction.INBOUND,
            status=Message.Status.RECEIVED,
            sender_name=sender_name or sender_email,
            body=_plain_body(parsed) or "[Matnsiz email]",
            sent_at=_sent_at(parsed),
            mailbox=account,
            email_message_id=message_id,
            email_in_reply_to=in_reply_to,
            email_references=references,
            email_subject=subject,
            email_from=sender_email,
            email_to=_email_addresses(parsed.get("To", "")),
            email_cc=_email_addresses(parsed.get("Cc", "")),
            email_folder=folder,
            imap_uid_validity=uid_validity,
            imap_uid=uid,
            metadata={"email_headers": {"reply_to": _header(parsed.get("Reply-To"))}},
        )
        _save_email_attachments(message, parsed)
        return message


def _imap_connection(account):
    context = ssl.create_default_context()
    if account.imap_security == MailboxAccount.Security.SSL:
        return imaplib.IMAP4_SSL(
            account.imap_host,
            account.imap_port,
            ssl_context=context,
            timeout=30,
        )
    server = imaplib.IMAP4(account.imap_host, account.imap_port, timeout=30)
    if account.imap_security == MailboxAccount.Security.STARTTLS:
        server.starttls(ssl_context=context)
    return server


def _uid_validity(server):
    _, values = server.response("UIDVALIDITY")
    if values and values[0]:
        return int(values[0])
    return 0


def _initial_since(days):
    value = date.today() - timedelta(days=days)
    months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    return f"{value.day:02d}-{months[value.month - 1]}-{value.year}"


def sync_mailbox(account, *, days=30, limit=200, folder="INBOX"):
    if not account.is_active:
        return {"found": 0, "imported": 0, "errors": 0}
    state, _ = MailboxSyncState.objects.get_or_create(
        organization=account.organization,
        mailbox=account,
        folder=folder,
    )
    server = None
    try:
        server = _imap_connection(account)
        server.login(account.username, account.get_password())
        status, _ = server.select(folder, readonly=True)
        if status != "OK":
            raise EmailSyncError(f"{folder} papkasini ochib bo'lmadi.")
        uid_validity = _uid_validity(server)
        if state.uid_validity != uid_validity:
            state.uid_validity = uid_validity
            state.last_uid = 0
        if state.last_uid:
            status, data = server.uid("search", None, f"UID {state.last_uid + 1}:*")
        else:
            status, data = server.uid("search", None, "SINCE", _initial_since(days))
        if status != "OK":
            raise EmailSyncError("IMAP xabarlar ro'yxatini qaytarmadi.")
        uids = [int(value) for value in (data[0] or b"").split()]
        uids = uids[-limit:]
        imported = 0
        errors = 0
        for uid in uids:
            try:
                fetch_status, payload = server.uid("fetch", str(uid), "(BODY.PEEK[])")
                if fetch_status != "OK":
                    raise EmailSyncError(f"UID {uid} xabarini olib bo'lmadi.")
                raw_message = next(
                    (item[1] for item in payload if isinstance(item, tuple) and item[1]),
                    None,
                )
                if raw_message and import_email_message(
                    account,
                    raw_message,
                    folder=folder,
                    uid_validity=uid_validity,
                    uid=uid,
                ):
                    imported += 1
            except Exception:
                errors += 1
            state.last_uid = max(state.last_uid, uid)
        state.last_synced_at = timezone.now()
        state.last_error = "" if not errors else f"{errors} ta xat import qilinmadi."
        state.save(
            update_fields=[
                "uid_validity",
                "last_uid",
                "last_synced_at",
                "last_error",
                "updated_at",
            ]
        )
        return {"found": len(uids), "imported": imported, "errors": errors}
    except (imaplib.IMAP4.error, OSError, ValueError, EmailSyncError) as exc:
        state.last_synced_at = timezone.now()
        state.last_error = str(exc)[:1000]
        state.save(update_fields=["last_synced_at", "last_error", "updated_at"])
        raise EmailSyncError(str(exc)) from exc
    finally:
        if server:
            try:
                server.logout()
            except (imaplib.IMAP4.error, OSError):
                try:
                    server.shutdown()
                except (imaplib.IMAP4.error, OSError):
                    pass


def deliver_email_message(message):
    conversation = message.conversation
    account = conversation.mailbox or message.mailbox
    recipients = list(message.email_to or [])
    if not recipients and conversation.external_chat_id:
        recipients = [conversation.external_chat_id]
    cc = list(message.email_cc or [])
    bcc = list((message.metadata or {}).get("email_bcc", []))
    if not account or not account.is_active:
        error = "Suhbatga faol mailbox biriktirilmagan."
    elif not recipients:
        error = "Qabul qiluvchi email manzili mavjud emas."
    else:
        error = ""
    if error:
        message.status = Message.Status.FAILED
        message.error_message = error
        message.save(update_fields=["status", "error_message", "updated_at"])
        return False

    latest_email = (
        conversation.messages.exclude(pk=message.pk)
        .exclude(email_message_id="")
        .order_by("-sent_at")
        .first()
    )
    in_reply_to = latest_email.email_message_id if latest_email else ""
    references = list(latest_email.email_references) if latest_email else []
    if in_reply_to and in_reply_to not in references:
        references.append(in_reply_to)
    subject = message.email_subject or conversation.title or "Mavzusiz email"
    if in_reply_to and not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"
    domain = account.email.partition("@")[2] or None
    message_id = make_msgid(domain=domain)
    headers = {"Message-ID": message_id}
    if in_reply_to:
        headers["In-Reply-To"] = in_reply_to
    if references:
        headers["References"] = " ".join(references)

    connection = get_connection(
        "django.core.mail.backends.smtp.EmailBackend",
        host=account.smtp_host,
        port=account.smtp_port,
        username=account.username,
        password=account.get_password(),
        use_tls=account.smtp_security == MailboxAccount.Security.STARTTLS,
        use_ssl=account.smtp_security == MailboxAccount.Security.SSL,
        timeout=30,
    )
    outgoing = EmailMessage(
        subject=subject,
        body=message.body,
        from_email=formataddr((account.display_name, account.email)),
        to=recipients,
        cc=cc,
        bcc=bcc,
        headers=headers,
        connection=connection,
    )
    for attachment in message.attachments.all():
        attachment.file.open("rb")
        try:
            outgoing.attach(
                attachment.original_name,
                attachment.file.read(),
                attachment.content_type or None,
            )
        finally:
            attachment.file.close()
    try:
        sent_count = outgoing.send(fail_silently=False)
        if sent_count != 1:
            raise EmailSyncError("SMTP xabar yuborilganini tasdiqlamadi.")
    except (smtplib.SMTPException, OSError, EmailSyncError) as exc:
        message.status = Message.Status.FAILED
        message.error_message = str(exc)[:1000]
        message.save(update_fields=["status", "error_message", "updated_at"])
        return False

    message.status = Message.Status.SENT
    message.mailbox = account
    message.email_message_id = message_id
    message.email_in_reply_to = in_reply_to
    message.email_references = references
    message.email_subject = subject
    message.email_from = account.email
    message.email_to = recipients
    message.email_cc = cc
    message.error_message = ""
    message.save(
        update_fields=[
            "status",
            "mailbox",
            "email_message_id",
            "email_in_reply_to",
            "email_references",
            "email_subject",
            "email_from",
            "email_to",
            "email_cc",
            "error_message",
            "updated_at",
        ]
    )
    if not conversation.email_thread_key:
        conversation.email_thread_key = message_id
        conversation.save(update_fields=["email_thread_key", "updated_at"])
    return True
