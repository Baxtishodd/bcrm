from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from apps.organizations.models import Membership, Organization

from .models import MailboxAccount, User


class MailboxAccountTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="seller@example.com",
            password="test-password",
        )
        self.organization = Organization.objects.create(
            name="Mailbox Textile",
            slug="mailbox-textile",
        )
        Membership.objects.create(
            organization=self.organization,
            user=self.user,
            role=Membership.Role.SALES,
        )
        self.client.force_login(self.user)
        self.data = {
            "email": "seller@company.uz",
            "display_name": "Textile Seller",
            "username": "seller@company.uz",
            "password": "mail-app-password",
            "smtp_host": "smtp.company.uz",
            "smtp_port": "587",
            "smtp_security": MailboxAccount.Security.STARTTLS,
            "imap_host": "imap.company.uz",
            "imap_port": "993",
            "imap_security": MailboxAccount.Security.SSL,
            "is_active": "on",
        }

    def test_user_can_create_mailbox_with_encrypted_password(self):
        response = self.client.post(reverse("accounts:mailbox-create"), self.data)

        account = MailboxAccount.objects.get()
        self.assertRedirects(response, reverse("accounts:mailbox-list"))
        self.assertEqual(account.organization, self.organization)
        self.assertEqual(account.user, self.user)
        self.assertTrue(account.is_default)
        self.assertNotEqual(account.encrypted_password, "mail-app-password")
        self.assertNotIn("mail-app-password", account.encrypted_password)
        self.assertEqual(account.get_password(), "mail-app-password")

    def test_blank_password_on_update_keeps_existing_secret(self):
        account = MailboxAccount(
            organization=self.organization,
            user=self.user,
            email="seller@company.uz",
            username="seller@company.uz",
            smtp_host="smtp.company.uz",
            imap_host="imap.company.uz",
        )
        account.set_password("existing-password")
        account.save()
        encrypted_password = account.encrypted_password
        update_data = {**self.data, "password": "", "display_name": "Updated Seller"}

        response = self.client.post(
            reverse("accounts:mailbox-update", args=[account.public_id]),
            update_data,
        )

        account.refresh_from_db()
        self.assertRedirects(response, reverse("accounts:mailbox-list"))
        self.assertEqual(account.display_name, "Updated Seller")
        self.assertEqual(account.encrypted_password, encrypted_password)
        self.assertEqual(account.get_password(), "existing-password")

    def test_user_cannot_open_another_users_mailbox(self):
        other_user = User.objects.create_user(
            email="other@example.com",
            password="test-password",
        )
        account = MailboxAccount(
            organization=self.organization,
            user=other_user,
            email="other@company.uz",
            username="other@company.uz",
            smtp_host="smtp.company.uz",
            imap_host="imap.company.uz",
        )
        account.set_password("hidden-password")
        account.save()

        response = self.client.get(
            reverse("accounts:mailbox-update", args=[account.public_id])
        )

        self.assertEqual(response.status_code, 404)
        test_response = self.client.post(
            reverse("accounts:mailbox-test", args=[account.public_id])
        )
        self.assertEqual(test_response.status_code, 404)
        list_response = self.client.get(reverse("accounts:mailbox-list"))
        self.assertNotContains(list_response, "other@company.uz")

    @patch("apps.accounts.services.imaplib.IMAP4_SSL")
    @patch("apps.accounts.services.smtplib.SMTP")
    def test_user_can_test_smtp_and_imap_connections(self, smtp, imap):
        self.client.post(reverse("accounts:mailbox-create"), self.data)
        account = MailboxAccount.objects.get()

        response = self.client.post(
            reverse("accounts:mailbox-test", args=[account.public_id])
        )

        self.assertRedirects(response, reverse("accounts:mailbox-list"))
        smtp.assert_called_once_with("smtp.company.uz", 587, timeout=15)
        smtp.return_value.starttls.assert_called_once()
        smtp.return_value.login.assert_called_once_with(
            "seller@company.uz",
            "mail-app-password",
        )
        imap.assert_called_once()
        imap.return_value.login.assert_called_once_with(
            "seller@company.uz",
            "mail-app-password",
        )
        account.refresh_from_db()
        self.assertIsNotNone(account.last_tested_at)
        self.assertEqual(account.last_error, "")
        self.assertTrue(account.smtp_is_verified)
        self.assertTrue(account.imap_is_verified)

    @patch("apps.accounts.services.imaplib.IMAP4_SSL")
    @patch("apps.accounts.services.smtplib.SMTP")
    def test_connection_test_preserves_partial_success(self, smtp, _imap):
        self.client.post(reverse("accounts:mailbox-create"), self.data)
        account = MailboxAccount.objects.get()
        smtp.return_value.login.side_effect = OSError("SMTP blocked")

        response = self.client.post(
            reverse("accounts:mailbox-test", args=[account.public_id])
        )

        self.assertRedirects(response, reverse("accounts:mailbox-list"))
        account.refresh_from_db()
        self.assertFalse(account.smtp_is_verified)
        self.assertTrue(account.imap_is_verified)
        self.assertIn("SMTP blocked", account.last_error)
