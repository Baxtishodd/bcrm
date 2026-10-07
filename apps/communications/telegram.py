import json
import mimetypes
import secrets
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.text import get_valid_filename

from apps.customers.models import Contact
from apps.organizations.models import Organization

from .models import (
    MAX_ATTACHMENT_BYTES,
    Conversation,
    Message,
    MessageAttachment,
    TelegramUpdate,
)


class TelegramAPIError(Exception):
    pass


class TelegramBotClient:
    api_root = "https://api.telegram.org"

    def __init__(self, token=None):
        self.token = (token or settings.TELEGRAM_SUPPORT_BOT).strip()
        if not self.token:
            raise ImproperlyConfigured("TELEGRAM_SUPPORT_BOT kiritilmagan.")

    def _method_url(self, method):
        return f"{self.api_root}/bot{self.token}/{method}"

    def _file_url(self, file_path):
        safe_path = "/".join(urllib.parse.quote(part) for part in file_path.split("/"))
        return f"{self.api_root}/file/bot{self.token}/{safe_path}"

    @staticmethod
    def _multipart(data, files):
        boundary = f"----bcrm{secrets.token_hex(16)}"
        body = bytearray()
        for key, value in data.items():
            body.extend(f"--{boundary}\r\n".encode())
            body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
            body.extend(str(value).encode("utf-8"))
            body.extend(b"\r\n")
        for key, (filename, content, content_type) in files.items():
            safe_name = get_valid_filename(Path(filename).name) or "attachment"
            body.extend(f"--{boundary}\r\n".encode())
            body.extend(
                (
                    f'Content-Disposition: form-data; name="{key}"; '
                    f'filename="{safe_name}"\r\n'
                ).encode()
            )
            body.extend(f"Content-Type: {content_type}\r\n\r\n".encode())
            body.extend(content)
            body.extend(b"\r\n")
        body.extend(f"--{boundary}--\r\n".encode())
        return bytes(body), f"multipart/form-data; boundary={boundary}"

    def call(self, method, data=None, files=None, timeout=35):
        data = data or {}
        headers = {"Accept": "application/json"}
        if files:
            payload, content_type = self._multipart(data, files)
            headers["Content-Type"] = content_type
        else:
            payload = urllib.parse.urlencode(data).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        request = urllib.request.Request(
            self._method_url(method),
            data=payload,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                result = json.loads(exc.read().decode("utf-8"))
                description = result.get("description", "Telegram HTTP xatosi")
            except (UnicodeDecodeError, json.JSONDecodeError):
                description = "Telegram HTTP xatosi"
            raise TelegramAPIError(description) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise TelegramAPIError("Telegram bilan bog'lanib bo'lmadi.") from exc
        except json.JSONDecodeError as exc:
            raise TelegramAPIError("Telegram noto'g'ri javob qaytardi.") from exc
        if not result.get("ok"):
            raise TelegramAPIError(result.get("description", "Telegram API xatosi"))
        return result.get("result")

    def get_me(self):
        return self.call("getMe")

    def get_updates(self, *, offset=None, timeout=25):
        data = {
            "timeout": timeout,
            "allowed_updates": json.dumps(["message"]),
        }
        if offset is not None:
            data["offset"] = offset
        return self.call("getUpdates", data, timeout=timeout + 10)

    def set_webhook(self, url, secret_token):
        return self.call(
            "setWebhook",
            {
                "url": url,
                "secret_token": secret_token,
                "allowed_updates": json.dumps(["message"]),
            },
        )

    def delete_webhook(self):
        return self.call("deleteWebhook")

    def get_webhook_info(self):
        return self.call("getWebhookInfo")

    def get_user_profile_photos(self, user_id):
        return self.call(
            "getUserProfilePhotos",
            {"user_id": user_id, "offset": 0, "limit": 1},
        )

    def download_file(self, file_id):
        file_info = self.call("getFile", {"file_id": file_id})
        file_path = file_info.get("file_path")
        if not file_path:
            raise TelegramAPIError("Telegram fayl manzilini qaytarmadi.")
        request = urllib.request.Request(self._file_url(file_path), method="GET")
        try:
            with urllib.request.urlopen(request, timeout=35) as response:
                content = response.read(MAX_ATTACHMENT_BYTES + 1)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            raise TelegramAPIError("Telegram faylini yuklab bo'lmadi.") from exc
        if len(content) > MAX_ATTACHMENT_BYTES:
            raise TelegramAPIError("Telegram fayli 10 MB chegaradan katta.")
        return content, file_path

    @staticmethod
    def _split_text(text, limit=4096):
        return [text[index : index + limit] for index in range(0, len(text), limit)] or [""]

    def send_message(self, message):
        chat_id = message.conversation.external_chat_id
        if not chat_id:
            raise TelegramAPIError("Telegram chat ID mavjud emas. Mijoz avval botga yozishi kerak.")

        attachment = message.attachments.first()
        results = []
        if attachment:
            attachment.file.open("rb")
            try:
                content = attachment.file.read()
            finally:
                attachment.file.close()
            field_name = "photo" if attachment.kind == MessageAttachment.Kind.IMAGE else "document"
            method = "sendPhoto" if field_name == "photo" else "sendDocument"
            content_type = attachment.content_type or mimetypes.guess_type(
                attachment.original_name
            )[0]
            data = {"chat_id": chat_id}
            if message.body:
                data["caption"] = message.body[:1024]
            results.append(
                self.call(
                    method,
                    data,
                    {
                        field_name: (
                            attachment.original_name,
                            content,
                            content_type or "application/octet-stream",
                        )
                    },
                )
            )
            remaining_text = message.body[1024:]
        else:
            remaining_text = message.body

        for part in self._split_text(remaining_text):
            if part:
                results.append(self.call("sendMessage", {"chat_id": chat_id, "text": part}))
        if not results:
            raise TelegramAPIError("Yuboriladigan xabar bo'sh.")
        return results[-1]


def get_telegram_organization():
    organizations = Organization.objects.filter(is_active=True)
    slug = settings.TELEGRAM_ORGANIZATION_SLUG
    if slug:
        try:
            return organizations.get(slug=slug)
        except Organization.DoesNotExist as exc:
            raise ImproperlyConfigured(
                "TELEGRAM_ORGANIZATION_SLUG bo'yicha faol tashkilot topilmadi."
            ) from exc
    if organizations.count() == 1:
        return organizations.first()
    raise ImproperlyConfigured(
        "Bir nechta tashkilot mavjud. .env ichida TELEGRAM_ORGANIZATION_SLUG kiriting."
    )


def _telegram_contact(organization, username):
    if not username:
        return None
    normalized = username.lstrip("@").lower()
    variants = (
        normalized,
        f"@{normalized}",
        f"t.me/{normalized}",
        f"https://t.me/{normalized}",
    )
    return (
        Contact.objects.filter(organization=organization)
        .filter(
            Q(telegram__iexact=variants[0])
            | Q(telegram__iexact=variants[1])
            | Q(telegram__iexact=variants[2])
            | Q(telegram__iexact=variants[3])
        )
        .select_related("company")
        .first()
    )


def _message_media(telegram_message):
    photos = telegram_message.get("photo") or []
    if photos:
        return (
            photos[-1].get("file_id"),
            f"telegram-{telegram_message['message_id']}.jpg",
            "image/jpeg",
        )
    document = telegram_message.get("document")
    if document:
        return (
            document.get("file_id"),
            document.get("file_name") or f"telegram-{telegram_message['message_id']}",
            document.get("mime_type") or "application/octet-stream",
        )
    for field, extension, content_type in (
        ("voice", "ogg", "audio/ogg"),
        ("audio", "mp3", "audio/mpeg"),
        ("video", "mp4", "video/mp4"),
    ):
        media = telegram_message.get(field)
        if media:
            return (
                media.get("file_id"),
                media.get("file_name") or f"telegram-{telegram_message['message_id']}.{extension}",
                media.get("mime_type") or content_type,
            )
    return None, "", ""


def _fallback_body(telegram_message):
    if telegram_message.get("sticker"):
        return f"[Stiker] {telegram_message['sticker'].get('emoji', '')}".strip()
    if telegram_message.get("contact"):
        contact = telegram_message["contact"]
        return (
            f"[Kontakt] {contact.get('first_name', '')} "
            f"{contact.get('phone_number', '')}"
        ).strip()
    if telegram_message.get("location"):
        location = telegram_message["location"]
        return f"[Lokatsiya] {location.get('latitude')}, {location.get('longitude')}"
    if telegram_message.get("voice"):
        return "[Ovozli xabar]"
    if telegram_message.get("video"):
        return "[Video]"
    if telegram_message.get("audio"):
        return "[Audio]"
    return "[Telegram xabari]"


def _refresh_telegram_avatar(conversation, sender, client):
    user_id = sender.get("id")
    if not user_id:
        return
    checked_at = conversation.telegram_avatar_checked_at
    if checked_at and checked_at >= timezone.now() - timedelta(hours=24):
        return

    now = timezone.now()
    try:
        profile_photos = client.get_user_profile_photos(user_id)
        photos = profile_photos.get("photos") or []
        if not photos or not photos[0]:
            conversation.telegram_avatar_checked_at = now
            conversation.save(update_fields=["telegram_avatar_checked_at", "updated_at"])
            return
        photo = photos[0][-1]
        unique_id = photo.get("file_unique_id", "")
        if unique_id and unique_id == conversation.telegram_avatar_file_id:
            conversation.telegram_avatar_checked_at = now
            conversation.save(update_fields=["telegram_avatar_checked_at", "updated_at"])
            return
        content, _ = client.download_file(photo["file_id"])
        conversation.telegram_avatar.save(
            f"telegram-avatar-{user_id}.jpg",
            ContentFile(content),
            save=False,
        )
        conversation.telegram_avatar_file_id = unique_id
        conversation.telegram_avatar_checked_at = now
        conversation.save(
            update_fields=[
                "telegram_avatar",
                "telegram_avatar_file_id",
                "telegram_avatar_checked_at",
                "updated_at",
            ]
        )
    except (KeyError, OSError, TelegramAPIError, ValidationError):
        conversation.telegram_avatar_checked_at = now
        conversation.save(update_fields=["telegram_avatar_checked_at", "updated_at"])


def process_telegram_update(update, *, organization=None, client=None):
    update_id = update.get("update_id")
    telegram_message = update.get("message")
    if update_id is None or not telegram_message:
        return None
    organization = organization or get_telegram_organization()
    client = client or TelegramBotClient()

    with transaction.atomic():
        update_record, created = TelegramUpdate.objects.get_or_create(
            update_id=update_id,
            defaults={"organization": organization, "payload": update},
        )
        if not created:
            return None

        chat = telegram_message.get("chat") or {}
        sender = telegram_message.get("from") or {}
        chat_id = str(chat.get("id", ""))
        if not chat_id:
            raise TelegramAPIError("Telegram update ichida chat ID yo'q.")
        sender_name = " ".join(
            part for part in (sender.get("first_name"), sender.get("last_name")) if part
        )
        username = sender.get("username") or chat.get("username") or ""
        title = sender_name or chat.get("title") or (f"@{username}" if username else chat_id)
        contact = _telegram_contact(organization, username)
        conversation, _ = Conversation.objects.get_or_create(
            organization=organization,
            channel=Conversation.Channel.TELEGRAM,
            external_chat_id=chat_id,
            defaults={
                "title": title,
                "contact": contact,
                "customer": contact.company if contact else None,
            },
        )
        _refresh_telegram_avatar(conversation, sender, client)
        external_message_id = str(telegram_message.get("message_id", ""))
        if Message.objects.filter(
            conversation=conversation,
            external_message_id=external_message_id,
        ).exists():
            update_record.processed_at = timezone.now()
            update_record.save(update_fields=["processed_at", "updated_at"])
            return None

        body = (telegram_message.get("text") or telegram_message.get("caption") or "").strip()
        file_id, filename, content_type = _message_media(telegram_message)
        sent_timestamp = telegram_message.get("date")
        message = Message.objects.create(
            organization=organization,
            conversation=conversation,
            direction=Message.Direction.INBOUND,
            status=Message.Status.RECEIVED,
            sender_name=sender_name or (f"@{username}" if username else title),
            body=body or _fallback_body(telegram_message),
            external_message_id=external_message_id,
            sent_at=(
                datetime.fromtimestamp(sent_timestamp, tz=UTC)
                if sent_timestamp
                else timezone.now()
            ),
            metadata={
                "telegram_update_id": update_id,
                "telegram_user_id": sender.get("id"),
                "telegram_username": username,
                "telegram_chat_type": chat.get("type"),
            },
        )
        if file_id:
            content, telegram_path = client.download_file(file_id)
            safe_name = get_valid_filename(Path(filename).name) or Path(telegram_path).name
            kind = MessageAttachment.Kind.OTHER
            if content_type.startswith("image/"):
                kind = MessageAttachment.Kind.IMAGE
            elif content_type in {
                "application/pdf",
                "application/msword",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/vnd.ms-excel",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "text/plain",
            }:
                kind = MessageAttachment.Kind.DOCUMENT
            attachment = MessageAttachment(
                organization=organization,
                message=message,
                original_name=safe_name[:255],
                content_type=content_type[:120],
                size=len(content),
                kind=kind,
            )
            attachment.file.save(safe_name, ContentFile(content), save=False)
            attachment.save()

        update_record.processed_at = timezone.now()
        update_record.save(update_fields=["processed_at", "updated_at"])
        return message


def deliver_telegram_message(message, *, client=None):
    client = client or TelegramBotClient()
    try:
        result = client.send_message(message)
    except (TelegramAPIError, ImproperlyConfigured) as exc:
        message.status = Message.Status.FAILED
        message.error_message = str(exc)
        message.save(update_fields=["status", "error_message", "updated_at"])
        return False
    message.status = Message.Status.SENT
    message.external_message_id = str(result.get("message_id", ""))
    message.error_message = ""
    message.save(
        update_fields=["status", "external_message_id", "error_message", "updated_at"]
    )
    return True
