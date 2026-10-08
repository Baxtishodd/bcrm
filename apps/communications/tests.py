import json
from email.message import EmailMessage as MIMEEmailMessage
from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.messages import get_messages
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from apps.accounts.models import MailboxAccount, User
from apps.crm.models import Lead
from apps.customers.models import Contact, CustomerCompany
from apps.organizations.models import Membership, Organization

from .mailbox import deliver_email_message, import_email_message, sync_mailbox
from .models import (
    Conversation,
    ConversationParticipant,
    MailboxSyncState,
    Message,
    MessageAttachment,
    TelegramUpdate,
)
from .telegram import process_telegram_update


class NoPhotoTelegramClient:
    @staticmethod
    def get_user_profile_photos(user_id):
        return {"total_count": 0, "photos": []}


class CommunicationFrontendTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="seller@example.com",
            password="test-password",
            first_name="Sotuv",
            last_name="Menejeri",
        )
        self.organization = Organization.objects.create(
            name="Message Textile",
            slug="message-textile",
        )
        Membership.objects.create(
            organization=self.organization,
            user=self.user,
            role=Membership.Role.SALES,
        )
        self.internal_peer = User.objects.create_user(
            email="peer@example.com",
            password="test-password",
            first_name="Ichki",
            last_name="Hamkasb",
        )
        Membership.objects.create(
            organization=self.organization,
            user=self.internal_peer,
            role=Membership.Role.SALES,
        )
        self.customer = CustomerCompany.objects.create(
            organization=self.organization,
            name="Atlas Trade",
        )
        self.contact = Contact.objects.create(
            organization=self.organization,
            company=self.customer,
            full_name="Ali Valiyev",
        )
        self.lead = Lead.objects.create(
            organization=self.organization,
            customer=self.customer,
            contact=self.contact,
            title="Atlas uchun futbolka",
        )
        self.conversation = Conversation.objects.create(
            organization=self.organization,
            channel=Conversation.Channel.INTERNAL,
            customer=self.customer,
            contact=self.contact,
            lead=self.lead,
            assigned_to=self.user,
        )
        ConversationParticipant.objects.create(
            organization=self.organization,
            conversation=self.conversation,
            user=self.user,
        )
        ConversationParticipant.objects.create(
            organization=self.organization,
            conversation=self.conversation,
            user=self.internal_peer,
        )
        self.client.force_login(self.user)

    def test_inbox_renders_two_pane_chat_and_linked_objects(self):
        Message.objects.create(
            organization=self.organization,
            conversation=self.conversation,
            direction=Message.Direction.INBOUND,
            status=Message.Status.RECEIVED,
            sender_name="Ali Valiyev",
            body="Assalomu alaykum, narx kerak edi.",
        )

        response = self.client.get(
            reverse("communications:team-conversation", args=[self.conversation.public_id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Assalomu alaykum")
        self.assertContains(response, "Ali Valiyev")
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.unread_count, 0)

    def test_message_is_scoped_to_current_organization(self):
        other_organization = Organization.objects.create(
            name="Hidden Textile",
            slug="hidden-message-textile",
        )
        hidden_conversation = Conversation.objects.create(
            organization=other_organization,
            title="Yashirin suhbat",
        )

        response = self.client.get(
            reverse("communications:conversation", args=[hidden_conversation.public_id])
        )

        self.assertEqual(response.status_code, 404)

    def test_create_internal_message_updates_conversation(self):
        response = self.client.post(
            reverse("communications:send", args=[self.conversation.public_id]),
            {"body": "Taklifni bugun yuboramiz."},
        )

        message = Message.objects.get(body="Taklifni bugun yuboramiz.")
        self.assertRedirects(
            response,
            reverse("communications:team-conversation", args=[self.conversation.public_id]),
        )
        self.assertEqual(message.organization, self.organization)
        self.assertEqual(message.sender, self.user)
        self.assertEqual(message.direction, Message.Direction.OUTBOUND)
        self.assertEqual(message.status, Message.Status.SENT)
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.last_message_at, message.sent_at)
        self.assertEqual(list(get_messages(response.wsgi_request)), [])

    def test_inbox_sync_returns_only_new_messages_and_marks_chat_read(self):
        existing = Message.objects.create(
            organization=self.organization,
            conversation=self.conversation,
            direction=Message.Direction.INBOUND,
            status=Message.Status.RECEIVED,
            sender_name="Ali Valiyev",
            body="Eski xabar",
        )
        new_message = Message.objects.create(
            organization=self.organization,
            conversation=self.conversation,
            direction=Message.Direction.INBOUND,
            status=Message.Status.RECEIVED,
            sender_name="Ali Valiyev",
            body="Yangi real-time xabar",
        )

        response = self.client.get(
            reverse("communications:team-sync"),
            {"conversation": self.conversation.public_id, "after": existing.id},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertNotIn("Eski xabar", payload["messages_html"])
        self.assertIn("Yangi real-time xabar", payload["messages_html"])
        self.assertEqual(payload["latest_message_id"], new_message.id)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.unread_count, 0)

    def test_inbox_sync_cannot_read_another_organization_conversation(self):
        other_organization = Organization.objects.create(
            name="Other Sync Textile",
            slug="other-sync-textile",
        )
        hidden_conversation = Conversation.objects.create(
            organization=other_organization,
            title="Yashirin real-time suhbat",
        )

        response = self.client.get(
            reverse("communications:team-sync"),
            {"conversation": hidden_conversation.public_id},
        )

        self.assertEqual(response.status_code, 404)

    def test_message_can_contain_attachment_only(self):
        with TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            response = self.client.post(
                reverse("communications:send", args=[self.conversation.public_id]),
                {
                    "body": "",
                    "attachment": SimpleUploadedFile(
                        "technical-sheet.pdf",
                        b"%PDF-1.4 test",
                        content_type="application/pdf",
                    ),
                },
            )

        self.assertEqual(response.status_code, 302)
        attachment = MessageAttachment.objects.get()
        self.assertEqual(attachment.original_name, "technical-sheet.pdf")
        self.assertEqual(attachment.kind, MessageAttachment.Kind.DOCUMENT)

    def test_external_channel_message_stays_pending_until_integration(self):
        self.conversation.channel = Conversation.Channel.WHATSAPP
        self.conversation.save(update_fields=["channel", "updated_at"])

        self.client.post(
            reverse("communications:send", args=[self.conversation.public_id]),
            {"body": "WhatsApp uchun xabar"},
        )

        self.assertEqual(
            Message.objects.get(body="WhatsApp uchun xabar").status,
            Message.Status.PENDING,
        )

    @override_settings(TELEGRAM_SUPPORT_BOT="test-token")
    @patch("apps.communications.telegram.TelegramBotClient.send_message")
    def test_telegram_message_is_sent_from_chat(self, send_message):
        send_message.return_value = {"message_id": 321}
        self.conversation.channel = Conversation.Channel.TELEGRAM
        self.conversation.external_chat_id = "998877"
        self.conversation.save(
            update_fields=["channel", "external_chat_id", "updated_at"]
        )

        response = self.client.post(
            reverse("communications:send", args=[self.conversation.public_id]),
            {"body": "Telegram orqali javob"},
        )

        message = Message.objects.get(body="Telegram orqali javob")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(message.status, Message.Status.SENT)
        self.assertEqual(message.external_message_id, "321")
        send_message.assert_called_once_with(message)

    def test_viewer_cannot_open_inbox(self):
        viewer = User.objects.create_user(email="viewer@example.com", password="password")
        Membership.objects.create(
            organization=self.organization,
            user=viewer,
            role=Membership.Role.VIEWER,
        )
        self.client.force_login(viewer)

        response = self.client.get(reverse("communications:inbox"))

        self.assertEqual(response.status_code, 403)

    def test_conversation_rejects_foreign_tenant_contact(self):
        other_organization = Organization.objects.create(
            name="Other Textile",
            slug="other-conversation-textile",
        )
        foreign_contact = Contact.objects.create(
            organization=other_organization,
            full_name="Begona kontakt",
        )
        conversation = Conversation(
            organization=self.organization,
            contact=foreign_contact,
        )

        with self.assertRaises(ValidationError):
            conversation.full_clean()

    def test_lead_timeline_contains_linked_message(self):
        Message.objects.create(
            organization=self.organization,
            conversation=self.conversation,
            direction=Message.Direction.OUTBOUND,
            status=Message.Status.SENT,
            sender=self.user,
            body="Timeline xabari",
        )

        response = self.client.get(reverse("crm:detail", args=[self.lead.public_id]))

        self.assertContains(response, "Timeline xabari")
        self.assertContains(
            response,
            reverse("communications:team-conversation", args=[self.conversation.public_id]),
        )


class InternalTeamChatTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Team Chat Textile",
            slug="team-chat-textile",
        )
        self.owner = User.objects.create_user(
            email="owner@team-chat.uz",
            password="test-password",
            first_name="Owner",
        )
        self.employee = User.objects.create_user(
            email="employee@team-chat.uz",
            password="test-password",
            first_name="Employee",
        )
        self.third_user = User.objects.create_user(
            email="third@team-chat.uz",
            password="test-password",
            first_name="Third",
        )
        self.owner_membership = Membership.objects.create(
            organization=self.organization,
            user=self.owner,
            role=Membership.Role.OWNER,
        )
        self.employee_membership = Membership.objects.create(
            organization=self.organization,
            user=self.employee,
            role=Membership.Role.PRODUCTION,
        )
        Membership.objects.create(
            organization=self.organization,
            user=self.third_user,
            role=Membership.Role.VIEWER,
        )
        self.client.force_login(self.owner)

    def start_chat(self):
        return self.client.post(
            reverse(
                "communications:team-start",
                args=[self.employee_membership.public_id],
            )
        )

    def test_employee_list_shows_message_action_for_other_active_employee(self):
        response = self.client.get(reverse("organizations:employees"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse(
                "communications:team-start",
                args=[self.employee_membership.public_id],
            ),
        )
        self.assertNotContains(
            response,
            reverse(
                "communications:team-start",
                args=[self.owner_membership.public_id],
            ),
        )

    def test_start_action_creates_or_reuses_private_direct_chat(self):
        first_response = self.start_chat()
        second_response = self.start_chat()

        conversation = Conversation.objects.get(channel=Conversation.Channel.INTERNAL)
        self.assertRedirects(
            first_response,
            reverse("communications:team-conversation", args=[conversation.public_id]),
        )
        self.assertEqual(second_response.url, first_response.url)
        self.assertEqual(Conversation.objects.filter(channel="internal").count(), 1)
        self.assertCountEqual(
            conversation.participants.values_list("user_id", flat=True),
            [self.owner.id, self.employee.id],
        )

    def test_start_action_reuses_legacy_chat_without_direct_key(self):
        legacy = Conversation.objects.create(
            organization=self.organization,
            channel=Conversation.Channel.INTERNAL,
            title="Eski suhbat",
        )
        ConversationParticipant.objects.bulk_create(
            [
                ConversationParticipant(
                    organization=self.organization,
                    conversation=legacy,
                    user=self.owner,
                ),
                ConversationParticipant(
                    organization=self.organization,
                    conversation=legacy,
                    user=self.employee,
                ),
            ]
        )

        response = self.start_chat()

        legacy.refresh_from_db()
        self.assertEqual(Conversation.objects.filter(channel="internal").count(), 1)
        self.assertEqual(legacy.internal_direct_key, f"{self.owner.id}:{self.employee.id}")
        self.assertRedirects(
            response,
            reverse("communications:team-conversation", args=[legacy.public_id]),
        )

    def test_message_reaches_recipient_and_chat_is_private(self):
        self.start_chat()
        conversation = Conversation.objects.get(channel=Conversation.Channel.INTERNAL)

        send_response = self.client.post(
            reverse("communications:send", args=[conversation.public_id]),
            {"body": "Ishlab chiqarish rejasini yuboring."},
        )

        self.assertRedirects(
            send_response,
            reverse("communications:team-conversation", args=[conversation.public_id]),
        )
        recipient_state = conversation.participants.get(user=self.employee)
        self.assertEqual(recipient_state.unread_count, 1)

        self.client.force_login(self.employee)
        dashboard_response = self.client.get(reverse("dashboard"))
        self.assertContains(dashboard_response, 'class="sidebar-count">1</small>')
        recipient_response = self.client.get(
            reverse("communications:team-conversation", args=[conversation.public_id])
        )
        self.assertEqual(recipient_response.status_code, 200)
        self.assertContains(recipient_response, "Ishlab chiqarish rejasini yuboring.")
        recipient_state.refresh_from_db()
        self.assertEqual(recipient_state.unread_count, 0)

        self.client.force_login(self.third_user)
        hidden_response = self.client.get(
            reverse("communications:team-conversation", args=[conversation.public_id])
        )
        forbidden_send = self.client.post(
            reverse("communications:send", args=[conversation.public_id]),
            {"body": "Begona xabar"},
        )
        self.assertEqual(hidden_response.status_code, 404)
        self.assertEqual(forbidden_send.status_code, 403)
        self.assertFalse(Message.objects.filter(body="Begona xabar").exists())

    def test_employee_without_mailbox_permission_can_open_team_inbox(self):
        self.start_chat()
        self.client.force_login(self.employee)

        response = self.client.get(reverse("communications:team-inbox"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/messages/team/", response.url)

    def test_team_directory_is_available_to_every_role_and_filters_by_role(self):
        self.client.force_login(self.employee)

        response = self.client.get(
            reverse("communications:team-inbox"),
            {"q": "Kuzatuvchi"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Third")
        self.assertContains(response, "Kuzatuvchi")
        self.assertNotContains(response, ">Jamoa chatlari</a>")
        self.assertContains(response, ">Xabarlar</span>")


class TelegramUpdateTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Telegram Textile",
            slug="telegram-textile",
        )
        self.customer = CustomerCompany.objects.create(
            organization=self.organization,
            name="Telegram Customer",
        )
        self.contact = Contact.objects.create(
            organization=self.organization,
            company=self.customer,
            full_name="Telegram Client",
            telegram="@telegram_client",
        )

    @staticmethod
    def update(**message_overrides):
        message = {
            "message_id": 45,
            "date": 1_700_000_000,
            "chat": {"id": 998877, "type": "private", "username": "telegram_client"},
            "from": {
                "id": 112233,
                "first_name": "Telegram",
                "last_name": "Client",
                "username": "telegram_client",
            },
            "text": "Telegramdan salom",
        }
        message.update(message_overrides)
        return {"update_id": 778899, "message": message}

    def test_incoming_update_creates_linked_conversation_and_message(self):
        message = process_telegram_update(
            self.update(),
            organization=self.organization,
            client=NoPhotoTelegramClient(),
        )

        self.assertEqual(message.body, "Telegramdan salom")
        self.assertEqual(message.direction, Message.Direction.INBOUND)
        self.assertEqual(message.status, Message.Status.RECEIVED)
        self.assertEqual(message.conversation.external_chat_id, "998877")
        self.assertEqual(message.conversation.contact, self.contact)
        self.assertEqual(message.conversation.customer, self.customer)
        message.conversation.refresh_from_db()
        self.assertEqual(message.conversation.unread_count, 1)
        self.assertTrue(TelegramUpdate.objects.get(update_id=778899).processed_at)

    def test_duplicate_update_is_ignored(self):
        update = self.update()
        process_telegram_update(
            update,
            organization=self.organization,
            client=NoPhotoTelegramClient(),
        )

        duplicate = process_telegram_update(
            update,
            organization=self.organization,
            client=NoPhotoTelegramClient(),
        )

        self.assertIsNone(duplicate)
        self.assertEqual(Message.objects.count(), 1)

    def test_incoming_photo_is_downloaded_as_attachment(self):
        class FileClient(NoPhotoTelegramClient):
            @staticmethod
            def download_file(file_id):
                return b"image-content", "photos/file.jpg"

        update = self.update(
            text=None,
            caption="Yangi namuna",
            photo=[{"file_id": "small"}, {"file_id": "large"}],
        )
        with TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            message = process_telegram_update(
                update,
                organization=self.organization,
                client=FileClient(),
            )
            attachment = message.attachments.get()
            self.assertEqual(attachment.kind, MessageAttachment.Kind.IMAGE)
            self.assertEqual(attachment.original_name, "telegram-45.jpg")
            self.assertEqual(attachment.size, len(b"image-content"))

    def test_telegram_profile_photo_is_used_only_for_conversation(self):
        output = BytesIO()
        Image.new("RGB", (96, 96), color=(20, 184, 166)).save(output, format="JPEG")

        class AvatarClient:
            @staticmethod
            def get_user_profile_photos(user_id):
                return {
                    "total_count": 1,
                    "photos": [
                        [
                            {
                                "file_id": "profile-file",
                                "file_unique_id": "profile-unique",
                            }
                        ]
                    ],
                }

            @staticmethod
            def download_file(file_id):
                return output.getvalue(), "photos/profile.jpg"

        with TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            message = process_telegram_update(
                self.update(),
                organization=self.organization,
                client=AvatarClient(),
            )
            conversation = message.conversation
            conversation.refresh_from_db()
            self.contact.refresh_from_db()

            self.assertTrue(conversation.telegram_avatar)
            self.assertEqual(conversation.telegram_avatar_file_id, "profile-unique")
            self.assertTrue(conversation.telegram_avatar_checked_at)
            self.assertFalse(self.contact.avatar)

    @override_settings(TELEGRAM_WEBHOOK_SECRET="webhook-secret")
    @patch("apps.communications.views.process_telegram_update")
    def test_webhook_checks_secret_and_processes_update(self, process_update):
        url = reverse("communications:telegram-webhook")
        forbidden = self.client.post(
            url,
            data=json.dumps(self.update()),
            content_type="application/json",
        )
        accepted = self.client.post(
            url,
            data=json.dumps(self.update()),
            content_type="application/json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="webhook-secret",
        )

        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(accepted.status_code, 200)
        process_update.assert_called_once()


class EmailIntegrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="email-seller@example.com",
            password="test-password",
            first_name="Email",
            last_name="Seller",
        )
        self.organization = Organization.objects.create(
            name="Email Textile",
            slug="email-textile",
        )
        Membership.objects.create(
            organization=self.organization,
            user=self.user,
            role=Membership.Role.SALES,
        )
        self.mailbox = MailboxAccount(
            organization=self.organization,
            user=self.user,
            email="sales@email-textile.uz",
            display_name="Email Textile Sales",
            username="sales@email-textile.uz",
            smtp_host="smtp.email-textile.uz",
            smtp_port=587,
            smtp_security=MailboxAccount.Security.STARTTLS,
            imap_host="imap.email-textile.uz",
            imap_port=993,
            imap_security=MailboxAccount.Security.SSL,
            is_active=True,
        )
        self.mailbox.set_password("mail-password")
        self.mailbox.save()
        self.contact = Contact.objects.create(
            organization=self.organization,
            full_name="Xaridor Ali",
            email="buyer@example.com",
        )

    @staticmethod
    def raw_email(
        *,
        message_id="<first@example.com>",
        subject="Futbolka narxi",
        in_reply_to="",
        references="",
        attachment=False,
    ):
        email_message = MIMEEmailMessage()
        email_message["From"] = "Xaridor Ali <buyer@example.com>"
        email_message["To"] = "sales@email-textile.uz"
        email_message["Subject"] = subject
        email_message["Message-ID"] = message_id
        email_message["Date"] = "Wed, 08 Oct 2026 10:00:00 +0500"
        if in_reply_to:
            email_message["In-Reply-To"] = in_reply_to
        if references:
            email_message["References"] = references
        email_message.set_content("Assalomu alaykum, narxni yuboring.")
        if attachment:
            email_message.add_attachment(
                b"%PDF-1.4 test",
                maintype="application",
                subtype="pdf",
                filename="technical-sheet.pdf",
            )
        return email_message.as_bytes()

    def test_import_email_creates_linked_conversation_and_attachment(self):
        with TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            message = import_email_message(
                self.mailbox,
                self.raw_email(attachment=True),
                folder="INBOX",
                uid_validity=100,
                uid=7,
            )

            self.assertEqual(message.email_subject, "Futbolka narxi")
            self.assertEqual(message.email_from, "buyer@example.com")
            self.assertEqual(message.conversation.channel, Conversation.Channel.EMAIL)
            self.assertEqual(message.conversation.contact, self.contact)
            self.assertEqual(message.conversation.mailbox, self.mailbox)
            self.assertEqual(message.conversation.assigned_to, self.user)
            self.assertEqual(message.attachments.get().original_name, "technical-sheet.pdf")

    def test_email_reply_is_added_to_existing_thread(self):
        first = import_email_message(
            self.mailbox,
            self.raw_email(),
            folder="INBOX",
            uid_validity=100,
            uid=7,
        )
        reply = import_email_message(
            self.mailbox,
            self.raw_email(
                message_id="<reply@example.com>",
                subject="Re: Futbolka narxi",
                in_reply_to="<first@example.com>",
                references="<first@example.com>",
            ),
            folder="INBOX",
            uid_validity=100,
            uid=8,
        )

        self.assertEqual(reply.conversation, first.conversation)
        self.assertEqual(Conversation.objects.count(), 1)

    def test_same_imap_uid_is_not_imported_twice(self):
        raw_message = self.raw_email()
        import_email_message(
            self.mailbox,
            raw_message,
            folder="INBOX",
            uid_validity=100,
            uid=7,
        )

        duplicate = import_email_message(
            self.mailbox,
            raw_message,
            folder="INBOX",
            uid_validity=100,
            uid=7,
        )

        self.assertIsNone(duplicate)
        self.assertEqual(Message.objects.count(), 1)

    def test_email_conversation_is_rendered_in_unified_inbox(self):
        message = import_email_message(
            self.mailbox,
            self.raw_email(),
            folder="INBOX",
            uid_validity=100,
            uid=7,
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("communications:conversation", args=[message.conversation.public_id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Futbolka narxi")
        self.assertContains(response, "sales@email-textile.uz")
        self.assertContains(response, "buyer@example.com")
        self.assertContains(response, "Mijoz:")
        self.assertContains(response, "Mailbox:")
        self.assertContains(response, "Assalomu alaykum, narxni yuboring.")

    @patch("apps.communications.mailbox.get_connection")
    def test_outgoing_reply_uses_conversation_mailbox_and_email_headers(self, connection):
        incoming = import_email_message(
            self.mailbox,
            self.raw_email(),
            folder="INBOX",
            uid_validity=100,
            uid=7,
        )
        outgoing = Message.objects.create(
            organization=self.organization,
            conversation=incoming.conversation,
            direction=Message.Direction.OUTBOUND,
            status=Message.Status.PENDING,
            sender=self.user,
            body="Narx taklifi ilovada.",
        )
        sent_messages = []

        class Connection:
            @staticmethod
            def send_messages(messages):
                sent_messages.extend(messages)
                return 1

        connection.return_value = Connection()

        delivered = deliver_email_message(outgoing)

        outgoing.refresh_from_db()
        self.assertTrue(delivered)
        self.assertEqual(outgoing.status, Message.Status.SENT)
        self.assertEqual(outgoing.mailbox, self.mailbox)
        self.assertEqual(outgoing.email_to, ["buyer@example.com"])
        self.assertEqual(outgoing.email_in_reply_to, "<first@example.com>")
        self.assertEqual(sent_messages[0].to, ["buyer@example.com"])
        self.assertEqual(sent_messages[0].extra_headers["In-Reply-To"], "<first@example.com>")

    @patch("apps.communications.mailbox._imap_connection")
    def test_mailbox_sync_uses_readonly_inbox_and_saves_cursor(self, imap_connection):
        raw_message = self.raw_email()

        class IMAPServer:
            selected_readonly = None

            def login(self, username, password):
                return "OK", []

            def select(self, folder, readonly=False):
                self.selected_readonly = readonly
                return "OK", [b"1"]

            def response(self, name):
                return "UIDVALIDITY", [b"100"]

            def uid(self, command, *args):
                if command == "search":
                    return "OK", [b"7"]
                return "OK", [(b"7 (BODY[])", raw_message), b")"]

            def logout(self):
                return "BYE", []

        server = IMAPServer()
        imap_connection.return_value = server

        result = sync_mailbox(self.mailbox, days=30)

        state = MailboxSyncState.objects.get(mailbox=self.mailbox, folder="INBOX")
        self.assertTrue(server.selected_readonly)
        self.assertEqual(result, {"found": 1, "imported": 1, "errors": 0})
        self.assertEqual(state.uid_validity, 100)
        self.assertEqual(state.last_uid, 7)

    @patch("apps.communications.views.deliver_email_message", return_value=True)
    def test_compose_individual_email_creates_one_conversation_per_recipient(self, deliver):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("communications:email-compose"),
            {
                "mailbox": self.mailbox.pk,
                "to": "buyer@example.com; second@example.com",
                "cc": "manager@example.com",
                "bcc": "audit@example.com",
                "send_mode": "individual",
                "subject": "Yangi taklif",
                "body": "Taklif tafsilotlari.",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Conversation.objects.filter(channel="email").count(), 2)
        self.assertEqual(deliver.call_count, 2)
        recipients = list(
            Message.objects.order_by("email_to").values_list("email_to", flat=True)
        )
        self.assertCountEqual(recipients, [["buyer@example.com"], ["second@example.com"]])
        self.assertTrue(
            Message.objects.filter(metadata__email_bcc=["audit@example.com"]).exists()
        )

    def test_email_compose_form_renders_floating_editor_and_contact_picker(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("communications:email-compose"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "buyer@example.com")
        self.assertContains(response, "data-email-compose-window")
        self.assertContains(response, "data-email-editor")
        self.assertContains(response, "data-editor-command")
        self.assertContains(response, 'name="attachments" multiple')

    def test_email_compose_ajax_get_returns_only_compose_window(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("communications:email-compose"),
            {"to": "buyer@example.com", "subject": "Sinov"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "communications/_email_compose_window.html")
        self.assertContains(response, 'value="buyer@example.com"')
        self.assertContains(response, 'value="Sinov"')
        self.assertNotContains(response, "app-shell")

    @patch("apps.communications.views.deliver_email_message", return_value=True)
    def test_email_compose_ajax_sanitizes_rich_text_and_returns_json(self, deliver):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("communications:email-compose"),
            {
                "mailbox": self.mailbox.pk,
                "to": "buyer@example.com",
                "cc": "",
                "bcc": "",
                "send_mode": "individual",
                "subject": "Formatlangan xat",
                "body": "Salom dunyo",
                "body_html": (
                    '<p><strong>Salom</strong><script>alert(1)</script>'
                    '<a href="javascript:alert(2)">havola</a></p>'
                ),
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        message = Message.objects.get()
        self.assertIn("<strong>Salom</strong>", message.metadata["body_html"])
        self.assertNotIn("<script", message.metadata["body_html"])
        self.assertNotIn("javascript:", message.metadata["body_html"])
        deliver.assert_called_once_with(message)

    @patch("apps.communications.views.deliver_email_message", return_value=True)
    def test_compose_group_email_creates_one_conversation(self, deliver):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("communications:email-compose"),
            {
                "mailbox": self.mailbox.pk,
                "to": "buyer@example.com, second@example.com",
                "cc": "",
                "bcc": "",
                "send_mode": "group",
                "subject": "Guruh taklifi",
                "body": "Barchaga salom.",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Conversation.objects.filter(channel="email").count(), 1)
        message = Message.objects.get()
        self.assertEqual(message.email_to, ["buyer@example.com", "second@example.com"])
        deliver.assert_called_once_with(message)

    @patch("apps.communications.views.deliver_email_message", return_value=True)
    def test_compose_email_accepts_multiple_attachments(self, deliver):
        self.client.force_login(self.user)
        attachments = [
            SimpleUploadedFile("offer.txt", b"offer", content_type="text/plain"),
            SimpleUploadedFile("prices.pdf", b"%PDF-test", content_type="application/pdf"),
        ]

        with TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            response = self.client.post(
                reverse("communications:email-compose"),
                {
                    "mailbox": self.mailbox.pk,
                    "to": "buyer@example.com",
                    "cc": "",
                    "bcc": "",
                    "send_mode": "individual",
                    "subject": "Faylli taklif",
                    "body": "Ikki fayl ilovada.",
                    "attachments": attachments,
                },
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(MessageAttachment.objects.count(), 2)
        deliver.assert_called_once()

    @patch("apps.communications.mailbox.get_connection")
    def test_new_group_email_uses_to_cc_bcc_without_reply_prefix(self, connection):
        conversation = Conversation.objects.create(
            organization=self.organization,
            channel=Conversation.Channel.EMAIL,
            title="Yangi kolleksiya",
            external_chat_id="buyer@example.com",
            mailbox=self.mailbox,
        )
        message = Message.objects.create(
            organization=self.organization,
            conversation=conversation,
            direction=Message.Direction.OUTBOUND,
            status=Message.Status.PENDING,
            sender=self.user,
            body="Katalog ilovada.",
            email_subject="Yangi kolleksiya",
            email_to=["buyer@example.com", "second@example.com"],
            email_cc=["manager@example.com"],
            metadata={"email_bcc": ["audit@example.com"]},
        )
        sent_messages = []

        class Connection:
            @staticmethod
            def send_messages(messages):
                sent_messages.extend(messages)
                return 1

        connection.return_value = Connection()

        self.assertTrue(deliver_email_message(message))
        outgoing = sent_messages[0]
        self.assertEqual(outgoing.subject, "Yangi kolleksiya")
        self.assertEqual(outgoing.to, ["buyer@example.com", "second@example.com"])
        self.assertEqual(outgoing.cc, ["manager@example.com"])
        self.assertEqual(outgoing.bcc, ["audit@example.com"])

    @patch("apps.communications.mailbox.get_connection")
    def test_rich_email_adds_sanitized_html_alternative(self, connection):
        conversation = Conversation.objects.create(
            organization=self.organization,
            channel=Conversation.Channel.EMAIL,
            title="HTML xat",
            external_chat_id="buyer@example.com",
            mailbox=self.mailbox,
        )
        message = Message.objects.create(
            organization=self.organization,
            conversation=conversation,
            direction=Message.Direction.OUTBOUND,
            sender=self.user,
            body="Qalin salom",
            email_subject="HTML xat",
            email_to=["buyer@example.com"],
            metadata={"body_html": "<p><strong>Qalin salom</strong></p>"},
        )
        sent_messages = []

        class Connection:
            @staticmethod
            def send_messages(messages):
                sent_messages.extend(messages)
                return 1

        connection.return_value = Connection()

        self.assertTrue(deliver_email_message(message))
        self.assertEqual(len(sent_messages[0].alternatives), 1)
        self.assertEqual(
            sent_messages[0].alternatives[0].content,
            "<p><strong>Qalin salom</strong></p>",
        )
