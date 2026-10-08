from django.contrib import admin

from .models import (
    Conversation,
    ConversationParticipant,
    MailboxSyncState,
    Message,
    MessageAttachment,
    TelegramUpdate,
)


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    fields = ("direction", "status", "sender_name", "body", "sent_at")
    readonly_fields = ("sent_at",)


class ConversationParticipantInline(admin.TabularInline):
    model = ConversationParticipant
    extra = 0
    fields = ("user", "unread_count", "last_read_at")


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("display_title", "organization", "channel", "status", "last_message_at")
    list_filter = ("channel", "status")
    search_fields = ("title", "contact__full_name", "customer__name", "lead__title")
    inlines = (ConversationParticipantInline, MessageInline)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("conversation", "direction", "status", "sender_name", "sent_at")
    list_filter = ("direction", "status")
    search_fields = ("body", "sender_name", "external_message_id")


@admin.register(ConversationParticipant)
class ConversationParticipantAdmin(admin.ModelAdmin):
    list_display = ("conversation", "user", "organization", "unread_count", "last_read_at")
    search_fields = ("user__email", "user__first_name", "user__last_name")


@admin.register(MessageAttachment)
class MessageAttachmentAdmin(admin.ModelAdmin):
    list_display = ("original_name", "message", "kind", "size", "created_at")


@admin.register(TelegramUpdate)
class TelegramUpdateAdmin(admin.ModelAdmin):
    list_display = ("update_id", "organization", "processed_at", "error_message")
    search_fields = ("update_id", "error_message")
    readonly_fields = (
        "update_id",
        "organization",
        "payload",
        "processed_at",
        "error_message",
    )


@admin.register(MailboxSyncState)
class MailboxSyncStateAdmin(admin.ModelAdmin):
    list_display = (
        "mailbox",
        "folder",
        "last_uid",
        "last_synced_at",
        "last_error",
    )
    list_filter = ("folder",)
