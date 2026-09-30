from io import BytesIO
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
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
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.organization.name, "Bunyodkor")

        sidebar_response = self.client.get(reverse("dashboard"))
        self.assertNotContains(sidebar_response, reverse("organizations:settings"))

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


class EmployeeManagementTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com",
            password="test-password",
            first_name="Owner",
        )
        self.organization = Organization.objects.create(
            name="Bunyodkor",
            slug="bunyodkor-employees",
        )
        self.owner_membership = Membership.objects.create(
            organization=self.organization,
            user=self.owner,
            role=Membership.Role.OWNER,
        )
        self.client.force_login(self.owner)

    def employee_data(self, **overrides):
        data = {
            "first_name": "Sardor",
            "last_name": "Sotuvchi",
            "email": "sardor@example.com",
            "phone": "+998901112233",
            "role": Membership.Role.SALES,
            "branch": "",
            "password1": "Strong-test-password-2026",
            "password2": "Strong-test-password-2026",
        }
        data.update(overrides)
        return data

    def test_owner_can_create_employee_login(self):
        response = self.client.post(
            reverse("organizations:employee-create"),
            self.employee_data(),
        )

        self.assertRedirects(response, reverse("organizations:employees"))
        employee = User.objects.get(email="sardor@example.com")
        self.assertTrue(employee.check_password("Strong-test-password-2026"))
        self.assertTrue(employee.must_change_password)
        self.assertTrue(
            Membership.objects.filter(
                organization=self.organization,
                user=employee,
                role=Membership.Role.SALES,
                is_active=True,
            ).exists()
        )

    def test_new_employee_completes_secure_first_login_flow(self):
        create_response = self.client.post(
            reverse("organizations:employee-create"),
            self.employee_data(),
        )
        self.assertRedirects(create_response, reverse("organizations:employees"))

        employee_client = Client()
        login_response = employee_client.post(
            reverse("login"),
            {
                "username": "sardor@example.com",
                "password": "Strong-test-password-2026",
            },
        )
        self.assertRedirects(
            login_response,
            reverse("dashboard"),
            fetch_redirect_response=False,
        )

        dashboard_response = employee_client.get(reverse("dashboard"))
        self.assertRedirects(
            dashboard_response,
            reverse("accounts:password-change"),
            fetch_redirect_response=False,
        )

        password_change_response = employee_client.post(
            reverse("accounts:password-change"),
            {
                "old_password": "Strong-test-password-2026",
                "new_password1": "Employee-secure-password-2026",
                "new_password2": "Employee-secure-password-2026",
            },
        )
        self.assertRedirects(password_change_response, reverse("dashboard"))
        self.assertEqual(employee_client.get(reverse("dashboard")).status_code, 200)

        employee = User.objects.get(email="sardor@example.com")
        employee.refresh_from_db()
        self.assertFalse(employee.must_change_password)
        self.assertTrue(employee.check_password("Employee-secure-password-2026"))

        membership = employee.memberships.get(organization=self.organization)
        membership.is_active = False
        membership.save(update_fields=["is_active", "updated_at"])

        blocked_response = employee_client.get(reverse("dashboard"))
        self.assertRedirects(
            blocked_response,
            reverse("login"),
            fetch_redirect_response=False,
        )
        self.assertNotIn("_auth_user_id", employee_client.session)

    def test_existing_user_can_be_attached_without_resetting_password(self):
        existing = User.objects.create_user(
            email="existing@example.com",
            password="existing-password",
        )

        response = self.client.post(
            reverse("organizations:employee-create"),
            self.employee_data(
                email=existing.email,
                password1="",
                password2="",
            ),
        )

        self.assertRedirects(response, reverse("organizations:employees"))
        existing.refresh_from_db()
        self.assertTrue(existing.check_password("existing-password"))
        self.assertTrue(
            Membership.objects.filter(
                organization=self.organization,
                user=existing,
                role=Membership.Role.SALES,
            ).exists()
        )

    def test_sales_member_cannot_open_employee_management(self):
        sales_user = User.objects.create_user(
            email="sales@example.com",
            password="test-password",
        )
        Membership.objects.create(
            organization=self.organization,
            user=sales_user,
            role=Membership.Role.SALES,
        )
        self.client.force_login(sales_user)

        list_response = self.client.get(reverse("organizations:employees"))
        create_response = self.client.get(reverse("organizations:employee-create"))

        self.assertEqual(list_response.status_code, 403)
        self.assertEqual(create_response.status_code, 403)

    def test_owner_cannot_deactivate_self(self):
        response = self.client.post(
            reverse(
                "organizations:employee-update",
                args=[self.owner_membership.public_id],
            ),
            {
                "first_name": "Owner",
                "last_name": "",
                "email": self.owner.email,
                "phone": "",
                "role": Membership.Role.OWNER,
                "branch": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "O&#x27;zingizni bloklay olmaysiz.")
        self.owner_membership.refresh_from_db()
        self.assertTrue(self.owner_membership.is_active)

    def test_director_cannot_edit_owner(self):
        director = User.objects.create_user(
            email="director@example.com",
            password="test-password",
        )
        Membership.objects.create(
            organization=self.organization,
            user=director,
            role=Membership.Role.DIRECTOR,
        )
        self.client.force_login(director)

        response = self.client.get(
            reverse(
                "organizations:employee-update",
                args=[self.owner_membership.public_id],
            )
        )

        self.assertEqual(response.status_code, 403)

    def test_owner_can_change_employee_role_and_status(self):
        employee = User.objects.create_user(
            email="employee@example.com",
            password="test-password",
            first_name="Old",
        )
        membership = Membership.objects.create(
            organization=self.organization,
            user=employee,
            role=Membership.Role.SALES,
        )

        response = self.client.post(
            reverse("organizations:employee-update", args=[membership.public_id]),
            {
                "first_name": "Updated",
                "last_name": "Employee",
                "email": employee.email,
                "phone": "+998900000000",
                "role": Membership.Role.ACCOUNTANT,
                "branch": "",
            },
        )

        self.assertRedirects(response, reverse("organizations:employees"))
        employee.refresh_from_db()
        membership.refresh_from_db()
        self.assertEqual(employee.first_name, "Updated")
        self.assertEqual(membership.role, Membership.Role.ACCOUNTANT)
        self.assertFalse(membership.is_active)
