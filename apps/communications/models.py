import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone

from apps.common.images import OptimizedImageField
from apps.common.models import OrganizationScopedModel

MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
ALLOWED_ATTACHMENT_EXTENSIONS = (
    "jpg",
    "jpeg",
    "png",
    "webp",
    "pdf",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "txt",
    "zip",
    "ogg",
    "mp3",
    "mp4",
    "webm",
)


def message_attachment_upload_to(instance, filename):
    extension = Path(filename).suffix.lower()
    if extension not in {f".{item}" for item in ALLOWED_ATTACHMENT_EXTENSIONS}:
        extension = ""
    today = timezone.localdate()
    return f"messages/{today:%Y/%m}/{uuid.uuid4().hex}{extension}"


def validate_attachment_size(uploaded_file):
    if uploaded_file and uploaded_file.size > MAX_ATTACHMENT_BYTES:
        raise ValidationError("Fayl hajmi 10 MB dan katta bo'lmasligi kerak.")


class Conversation(OrganizationScopedModel):
    class Channel(models.TextChoices):
        INTERNAL = "internal", "Ichki chat"
        TELEGRAM = "telegram", "Telegram"
        WHATSAPP = "whatsapp", "WhatsApp"
        EMAIL = "email", "Email"

    class Status(models.TextChoices):
        OPEN = "open", "Ochiq"
        CLOSED = "closed", "Yopilgan"
        ARCHIVED = "archived", "Arxivlangan"

    channel = models.CharField(
        max_length=20,
        choices=Channel.choices,
        default=Channel.INTERNAL,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
    )
    title = models.CharField(max_length=220, blank=True)
    external_chat_id = models.CharField(max_length=255, blank=True)
    mailbox = models.ForeignKey(
        "accounts.MailboxAccount",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="conversations",
    )
    email_thread_key = models.CharField(max_length=255, blank=True)
    telegram_avatar = OptimizedImageField(blank=True)
    telegram_avatar_file_id = models.CharField(max_length=255, blank=True)
    telegram_avatar_checked_at = models.DateTimeField(null=True, blank=True)
    customer = models.ForeignKey(
        "customers.CustomerCompany",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="conversations",
    )
    contact = models.ForeignKey(
        "customers.Contact",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="conversations",
    )
    lead = models.ForeignKey(
        "crm.Lead",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="conversations",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_conversations",
    )
    last_message_at = models.DateTimeField(null=True, blank=True)
    unread_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-last_message_at", "-updated_at"]
        indexes = [
            models.Index(fields=["organization", "channel"]),
            models.Index(fields=["organization", "last_message_at"]),
        ]

    def __str__(self):
        return self.display_title

    @property
    def display_title(self):
        if self.title:
            return self.title
        if self.contact_id:
            return self.contact.full_name
        if self.customer_id:
            return self.customer.name
        if self.lead_id:
            return self.lead.title
        return "Nomsiz suhbat"

    def clean(self):
        super().clean()
        errors = {}
        for field_name in ("customer", "contact", "lead"):
            related = getattr(self, field_name, None)
            if related and related.organization_id != self.organization_id:
                errors[field_name] = "Tanlangan obyekt boshqa tashkilotga tegishli."
        if self.contact_id and self.customer_id:
            if self.contact.company_id and self.contact.company_id != self.customer_id:
                errors["contact"] = "Kontakt tanlangan mijozga tegishli emas."
        if self.lead_id and self.customer_id:
            if self.lead.customer_id and self.lead.customer_id != self.customer_id:
                errors["lead"] = "Lead tanlangan mijozga tegishli emas."
        if self.assigned_to_id and not self.assigned_to.memberships.filter(
            organization_id=self.organization_id,
            is_active=True,
        ).exists():
            errors["assigned_to"] = "Mas'ul xodim ushbu tashkilotga tegishli emas."
        if self.mailbox_id and self.mailbox.organization_id != self.organization_id:
            errors["mailbox"] = "Mailbox boshqa tashkilotga tegishli."
        if errors:
            raise ValidationError(errors)


class Message(OrganizationScopedModel):
    class Direction(models.TextChoices):
        INBOUND = "inbound", "Kiruvchi"
        OUTBOUND = "outbound", "Chiquvchi"
        SYSTEM = "system", "Tizim"

    class Status(models.TextChoices):
        PENDING = "pending", "Navbatda"
        SENT = "sent", "Yuborildi"
        DELIVERED = "delivered", "Yetkazildi"
        READ = "read", "O'qildi"
        RECEIVED = "received", "Qabul qilindi"
        FAILED = "failed", "Xatolik"

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    direction = models.CharField(max_length=12, choices=Direction.choices)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="communication_messages",
    )
    sender_name = models.CharField(max_length=160, blank=True)
    body = models.TextField(blank=True)
    external_message_id = models.CharField(max_length=255, blank=True)
    reply_to = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="replies",
    )
    sent_at = models.DateTimeField(default=timezone.now)
    read_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    mailbox = models.ForeignKey(
        "accounts.MailboxAccount",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="messages",
    )
    email_message_id = models.CharField(max_length=255, blank=True)
    email_in_reply_to = models.CharField(max_length=255, blank=True)
    email_references = models.JSONField(default=list, blank=True)
    email_subject = models.CharField(max_length=500, blank=True)
    email_from = models.EmailField(blank=True)
    email_to = models.JSONField(default=list, blank=True)
    email_cc = models.JSONField(default=list, blank=True)
    email_folder = models.CharField(max_length=255, blank=True)
    imap_uid_validity = models.PositiveBigIntegerField(null=True, blank=True)
    imap_uid = models.PositiveBigIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["sent_at", "id"]
        indexes = [
            models.Index(fields=["organization", "conversation", "sent_at"]),
            models.Index(fields=["organization", "external_message_id"]),
            models.Index(fields=["mailbox", "email_message_id"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["mailbox", "email_folder", "imap_uid_validity", "imap_uid"],
                name="uniq_imported_email_uid",
            )
        ]

    def __str__(self):
        return self.body[:80] or self.get_direction_display()

    def clean(self):
        super().clean()
        errors = {}
        if self.conversation_id and self.conversation.organization_id != self.organization_id:
            errors["conversation"] = "Suhbat boshqa tashkilotga tegishli."
        if self.reply_to_id and self.reply_to.conversation_id != self.conversation_id:
            errors["reply_to"] = "Javob xabari boshqa suhbatga tegishli."
        if self.mailbox_id and self.mailbox.organization_id != self.organization_id:
            errors["mailbox"] = "Mailbox boshqa tashkilotga tegishli."
        if not self.body.strip() and not self.pk:
            # Yangi xabar fayl bilan yuborilishi mumkin; forma yakuniy tekshiradi.
            pass
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        update_fields = {"last_message_at": self.sent_at, "updated_at": timezone.now()}
        if is_new and self.direction == self.Direction.INBOUND:
            Conversation.objects.filter(pk=self.conversation_id).update(
                last_message_at=self.sent_at,
                unread_count=models.F("unread_count") + 1,
                updated_at=timezone.now(),
            )
        else:
            Conversation.objects.filter(pk=self.conversation_id).update(**update_fields)


class MessageAttachment(OrganizationScopedModel):
    class Kind(models.TextChoices):
        IMAGE = "image", "Rasm"
        DOCUMENT = "document", "Hujjat"
        OTHER = "other", "Fayl"

    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField(
        upload_to=message_attachment_upload_to,
        validators=[
            FileExtensionValidator(ALLOWED_ATTACHMENT_EXTENSIONS),
            validate_attachment_size,
        ],
    )
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=120, blank=True)
    size = models.PositiveIntegerField(default=0)
    kind = models.CharField(
        max_length=12,
        choices=Kind.choices,
        default=Kind.OTHER,
    )

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.original_name

    def clean(self):
        super().clean()
        if self.message_id and self.message.organization_id != self.organization_id:
            raise ValidationError({"message": "Xabar boshqa tashkilotga tegishli."})


class TelegramUpdate(OrganizationScopedModel):
    update_id = models.BigIntegerField(unique=True)
    payload = models.JSONField(default=dict)
    processed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-update_id"]

    def __str__(self):
        return str(self.update_id)


class MailboxSyncState(OrganizationScopedModel):
    mailbox = models.ForeignKey(
        "accounts.MailboxAccount",
        on_delete=models.CASCADE,
        related_name="sync_states",
    )
    folder = models.CharField(max_length=255, default="INBOX")
    uid_validity = models.PositiveBigIntegerField(null=True, blank=True)
    last_uid = models.PositiveBigIntegerField(default=0)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)

    class Meta:
        ordering = ["mailbox", "folder"]
        constraints = [
            models.UniqueConstraint(
                fields=["mailbox", "folder"],
                name="uniq_mailbox_sync_folder",
            )
        ]

    def __str__(self):
        return f"{self.mailbox.email}: {self.folder}"
