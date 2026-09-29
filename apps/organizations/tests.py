from io import BytesIO
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse
from PIL import Image

from apps.accounts.models import User

from .forms import OrganizationSettingsForm
from .models import Membership, Organization


class OrganizationSettingsTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com",
            password="test-password",
        )
        self.organization = Organization.objects.create(
            name="Bunyodkor",
            slug="bunyodkor-settings",
        )
        Membership.objects.create(
            organization=self.organization,
            user=self.owner,
            role=Membership.Role.OWNER,
        )
        self.client.force_login(self.owner)

    @staticmethod
    def image_upload(filename):
        output = BytesIO()
        Image.new("RGBA", (320, 120), color=(255, 255, 255, 255)).save(
            output,
            format="PNG",
        )
        return SimpleUploadedFile(filename, output.getvalue(), content_type="image/png")

    def form_data(self, **overrides):
        data = {
            "name": "Bunyodkor Textile",
            "legal_name": "Bunyodkor Textile MChJ",
            "short_name": "Bunyodkor",
            "tax_id": "123456789",
            "phone": "+998901234567",
            "email": "sales@bunyodkor.uz",
            "website": "https://bunyodkor.uz",
            "legal_address": "Toshkent shahri",
            "production_address": "Koson tumani",
            "bank_name": "Test Bank",
            "bank_account": "20208000900000000001",
            "bank_code": "00444",
            "director_name": "Bosh direktor",
            "default_currency": "USD",
            "default_incoterm": "FCA Koson",
            "default_delivery_terms": "14 ish kuni",
            "default_payment_terms": "100% oldindan to'lov",
            "quotation_number_prefix": "bt-q",
            "order_number_prefix": "bt-o",
            "quotation_validity_days": "21",
            "document_footer": "Taklif 21 kun amal qiladi.",
            "email_sender_name": "Bunyodkor Sales",
            "telegram_username": "@bunyodkor",
            "whatsapp_phone": "+998901234567",
        }
        data.update(overrides)
        return data

    def test_owner_can_update_central_settings(self):
        response = self.client.post(
            reverse("organizations:settings"),
            self.form_data(),
        )

        self.organization.refresh_from_db()
        self.assertRedirects(response, reverse("organizations:settings"))
        self.assertEqual(self.organization.legal_name, "Bunyodkor Textile MChJ")
        self.assertEqual(self.organization.default_currency, "USD")
        self.assertEqual(self.organization.quotation_number_prefix, "BT-Q")
        self.assertEqual(self.organization.quotation_validity_days, 21)

    def test_sales_member_cannot_change_settings(self):
        sales_user = User.objects.create_user(
            email="sales-member@example.com",
            password="test-password",
        )
        Membership.objects.create(
            organization=self.organization,
            user=sales_user,
            role=Membership.Role.SALES,
        )
        self.client.force_login(sales_user)

        response = self.client.post(
            reverse("organizations:settings"),
            self.form_data(name="Changed without permission"),
        )

        self.organization.refresh_from_db()
        self.assertRedirects(response, reverse("dashboard"))
        self.assertEqual(self.organization.name, "Bunyodkor")

    def test_form_rejects_invalid_currency_and_prefix(self):
        form = OrganizationSettingsForm(
            data=self.form_data(
                default_currency="US",
                quotation_number_prefix="BT Q!",
            ),
            instance=self.organization,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("default_currency", form.errors)
        self.assertIn("quotation_number_prefix", form.errors)

    def test_currency_field_uses_supported_iso_options(self):
        form = OrganizationSettingsForm(instance=self.organization)

        self.assertEqual(
            list(form.fields["default_currency"].choices),
            [
                ("USD", "AQSh dollari (USD)"),
                ("EUR", "Yevro (EUR)"),
                ("RUB", "Rossiya rubli (RUB)"),
                ("UZS", "O'zbekiston so'mi (UZS)"),
            ],
        )

    def test_settings_page_uses_current_organization_only(self):
        other = Organization.objects.create(
            name="Other Textile",
            slug="other-settings",
            default_currency="EUR",
        )

        response = self.client.get(reverse("organizations:settings"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"].instance, self.organization)
        self.assertNotEqual(response.context["form"].instance, other)

    def test_sidebar_uses_inverse_logo_and_falls_back_to_original_logo(self):
        with TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                self.organization.logo = self.image_upload("main-logo.png")
                self.organization.save(update_fields=["logo", "updated_at"])

                fallback_response = self.client.get(reverse("dashboard"))

                self.assertContains(fallback_response, "brand-logo-surface")
                self.assertContains(fallback_response, self.organization.logo.url)

                self.organization.sidebar_logo = self.image_upload("sidebar-logo.png")
                self.organization.save(update_fields=["sidebar_logo", "updated_at"])
                inverse_response = self.client.get(reverse("dashboard"))

                self.assertContains(inverse_response, "brand-logo-inverse")
                self.assertContains(inverse_response, self.organization.sidebar_logo.url)
                self.assertNotContains(inverse_response, "brand-logo-surface")
