from io import BytesIO
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from apps.accounts.models import User
from apps.crm.models import Activity, Lead
from apps.organizations.models import Membership, Organization
from apps.sales.models import Quotation, QuotationDelivery

from .management.commands.import_customer_workbooks import merge_text, normalized_name
from .models import Contact, CustomerCompany


class CustomerFrontendTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="owner@example.com",
            password="test-password",
        )
        self.organization = Organization.objects.create(
            name="Own Textile",
            slug="own-textile",
        )
        Membership.objects.create(
            organization=self.organization,
            user=self.user,
            role=Membership.Role.OWNER,
        )
        self.other_organization = Organization.objects.create(
            name="Other Textile",
            slug="other-textile",
        )
        CustomerCompany.objects.create(
            organization=self.other_organization,
            name="Hidden Customer",
        )
        self.client.force_login(self.user)

    def test_customer_list_is_tenant_scoped(self):
        response = self.client.get(reverse("customers:list"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Hidden Customer")

    def test_customer_create_assigns_current_organization(self):
        response = self.client.post(
            reverse("customers:create"),
            {
                "name": "Visible Customer",
                "relationship_status": CustomerCompany.RelationshipStatus.WORKING,
                "business_direction": CustomerCompany.BusinessDirection.KNIT_FABRIC,
                "customer_type": CustomerCompany.Type.LOCAL,
                "product_interest": "Suprem va interlok",
                "purchase_purpose": "Mato olib, tayyor kiyim ishlab chiqarish",
                "whatsapp": "+998901234567",
                "notes": "Narx taklifi Telegram orqali yuboriladi.",
                "is_active": "on",
            },
        )

        customer = CustomerCompany.objects.get(name="Visible Customer")
        self.assertRedirects(
            response,
            reverse("customers:detail", args=[customer.public_id]),
        )
        self.assertEqual(customer.organization, self.organization)
        self.assertEqual(
            customer.relationship_status,
            CustomerCompany.RelationshipStatus.WORKING,
        )
        self.assertEqual(
            customer.business_direction,
            CustomerCompany.BusinessDirection.KNIT_FABRIC,
        )
        self.assertEqual(customer.product_interest, "Suprem va interlok")

    def test_customer_search_includes_product_and_contact_fields(self):
        customer = CustomerCompany.objects.create(
            organization=self.organization,
            name="Textile Partner",
            product_interest="Interlok 30/1",
        )
        customer.contacts.create(
            organization=self.organization,
            full_name="Dilshod Rahbar",
        )

        by_product = self.client.get(reverse("customers:list"), {"q": "Interlok"})
        by_contact = self.client.get(reverse("customers:list"), {"q": "Dilshod"})

        self.assertContains(by_product, customer.name)
        self.assertContains(by_contact, customer.name)

    def test_customer_list_is_paginated(self):
        CustomerCompany.objects.bulk_create(
            [
                CustomerCompany(
                    organization=self.organization,
                    name=f"Customer {index:02d}",
                )
                for index in range(30)
            ]
        )

        first_page = self.client.get(reverse("customers:list"))
        second_page = self.client.get(reverse("customers:list"), {"page": 2})

        self.assertEqual(len(first_page.context["customers"]), 25)
        self.assertEqual(len(second_page.context["customers"]), 5)
        self.assertEqual(first_page.context["paginator"].count, 30)

    def test_customer_filters_can_be_combined(self):
        matching = CustomerCompany.objects.create(
            organization=self.organization,
            name="Matching textile",
            relationship_status=CustomerCompany.RelationshipStatus.WORKING,
            business_direction=CustomerCompany.BusinessDirection.KNIT_FABRIC,
            country="O'zbekiston",
            owner=self.user,
        )
        CustomerCompany.objects.create(
            organization=self.organization,
            name="Different textile",
            relationship_status=CustomerCompany.RelationshipStatus.POTENTIAL,
            business_direction=CustomerCompany.BusinessDirection.YARN,
            country="Rossiya",
        )

        response = self.client.get(
            reverse("customers:list"),
            {
                "relationship_status": CustomerCompany.RelationshipStatus.WORKING,
                "business_direction": CustomerCompany.BusinessDirection.KNIT_FABRIC,
                "country": "O'zbekiston",
                "owner": self.user.pk,
                "per_page": 50,
            },
        )

        self.assertEqual(list(response.context["customers"]), [matching])
        self.assertEqual(response.context["per_page"], 50)
        self.assertIn("relationship_status=working", response.context["pagination_query"])

    def test_customer_detail_combines_activities_and_deliveries_in_timeline(self):
        customer = CustomerCompany.objects.create(
            organization=self.organization,
            name="Timeline customer",
        )
        lead = Lead.objects.create(
            organization=self.organization,
            customer=customer,
            title="Timeline lead",
        )
        Activity.objects.create(
            organization=self.organization,
            lead=lead,
            customer=customer,
            activity_type=Activity.Type.CALL,
            subject="Narxni muhokama qilish",
        )
        quotation = Quotation.objects.create(
            organization=self.organization,
            customer=customer,
            lead=lead,
            number="QT-TIMELINE",
        )
        QuotationDelivery.objects.create(
            organization=self.organization,
            quotation=quotation,
            channel=QuotationDelivery.Channel.EMAIL,
            recipient="buyer@example.com",
            subject="Tijorat taklifi",
        )

        response = self.client.get(reverse("customers:detail", args=[customer.public_id]))

        self.assertContains(response, "Aloqa tarixi")
        self.assertContains(response, "Narxni muhokama qilish")
        self.assertContains(response, "QT-TIMELINE")
        self.assertContains(response, "buyer@example.com")

    def test_standalone_contact_can_be_created_without_customer(self):
        response = self.client.post(
            reverse("customers:contact-create"),
            {
                "contact_type": Contact.Type.PARTNER,
                "full_name": "Mustaqil hamkor",
                "email": "partner@example.com",
                "country": "O'zbekiston",
                "is_active": "on",
            },
        )

        contact = Contact.objects.get(email="partner@example.com")
        self.assertRedirects(
            response,
            reverse("customers:contact-detail", args=[contact.public_id]),
        )
        self.assertIsNone(contact.company)
        self.assertEqual(contact.organization, self.organization)
        self.assertEqual(contact.owner, self.user)

    def test_contact_form_enables_avatar_editor(self):
        response = self.client.get(reverse("customers:contact-create"))

        self.assertContains(response, 'data-avatar-editor="true"')
        self.assertContains(response, "Profil rasmi")
        self.assertContains(response, 'class="required-mark"')
        self.assertNotContains(response, 'id="id_owner"')

    def test_contact_form_country_is_a_searchable_country_select(self):
        response = self.client.get(reverse("customers:contact-create"))

        self.assertContains(response, 'name="country"')
        self.assertContains(response, 'data-smart-select')
        self.assertContains(response, 'data-smart-select-placeholder="Mamlakat nomini yozing..."')
        self.assertContains(response, '<option value="O&#x27;zbekiston">O&#x27;zbekiston</option>')
        self.assertContains(response, '<option value="Qozog&#x27;iston">Qozog&#x27;iston</option>')

    def test_contact_form_keeps_a_legacy_country_available_when_editing(self):
        contact = Contact.objects.create(
            organization=self.organization,
            full_name="Legacy country contact",
            country="Oldingi mamlakat qiymati",
        )

        response = self.client.get(
            reverse("customers:contact-update", args=[contact.public_id]),
        )

        self.assertContains(response, "Oldingi mamlakat qiymati")

    def test_contact_list_is_tenant_scoped_and_filterable(self):
        visible = Contact.objects.create(
            organization=self.organization,
            full_name="Visible partner",
            contact_type=Contact.Type.PARTNER,
            country="O'zbekiston",
        )
        Contact.objects.create(
            organization=self.other_organization,
            full_name="Hidden partner",
            contact_type=Contact.Type.PARTNER,
        )

        response = self.client.get(
            reverse("customers:contact-list"),
            {"contact_type": Contact.Type.PARTNER, "country": "O'zbekiston"},
        )

        self.assertEqual(list(response.context["contacts"]), [visible])
        self.assertNotContains(response, "Hidden partner")

    def test_contact_list_defaults_to_cards_and_supports_table_view(self):
        Contact.objects.create(
            organization=self.organization,
            full_name="Card view contact",
            contact_type=Contact.Type.PARTNER,
        )

        card_response = self.client.get(reverse("customers:contact-list"))
        table_response = self.client.get(
            reverse("customers:contact-list"),
            {"view": "table"},
        )

        self.assertEqual(card_response.context["view_mode"], "cards")
        self.assertContains(card_response, 'data-view-mode="cards"')
        self.assertContains(card_response, "contact-card-grid")
        self.assertContains(card_response, "Kontaktlarni filtrlash")
        self.assertContains(card_response, "Kontaktlar ro‘yxati")
        self.assertContains(card_response, "contact-results-toolbar")
        self.assertEqual(table_response.context["view_mode"], "table")
        self.assertContains(table_response, "<table")

    def test_contact_list_tabs_separate_all_and_current_users_contacts(self):
        coworker = User.objects.create_user(
            email="coworker@example.com",
            password="test-password",
        )
        Membership.objects.create(
            organization=self.organization,
            user=coworker,
            role=Membership.Role.SALES,
        )
        own_contact = Contact.objects.create(
            organization=self.organization,
            owner=self.user,
            full_name="Own contact",
        )
        coworker_contact = Contact.objects.create(
            organization=self.organization,
            owner=coworker,
            full_name="Coworker contact",
        )

        all_response = self.client.get(reverse("customers:contact-list"))
        mine_response = self.client.get(
            reverse("customers:contact-list"),
            {"scope": "mine", "view": "table"},
        )

        self.assertEqual(
            list(all_response.context["contacts"]),
            [coworker_contact, own_contact],
        )
        self.assertEqual(list(mine_response.context["contacts"]), [own_contact])
        self.assertEqual(mine_response.context["list_scope"], "mine")
        self.assertContains(mine_response, "Barcha kontaktlar")
        self.assertContains(mine_response, "Mening kontaktlarim")
        self.assertContains(mine_response, 'name="scope" value="mine"')
        self.assertContains(mine_response, 'name="view" value="table"')
        self.assertNotContains(mine_response, 'id="id_owner"')
        self.assertIn("scope=mine", mine_response.context["pagination_query"])
        self.assertIn("view=table", mine_response.context["contacts_all_url"])

    def test_contact_list_invalid_scope_falls_back_to_all_contacts(self):
        Contact.objects.create(
            organization=self.organization,
            full_name="Visible contact",
        )

        response = self.client.get(
            reverse("customers:contact-list"),
            {"scope": "unknown"},
        )

        self.assertEqual(response.context["list_scope"], "all")
        self.assertContains(response, "Visible contact")

    def test_duplicate_contact_email_is_rejected(self):
        Contact.objects.create(
            organization=self.organization,
            full_name="Existing contact",
            email="same@example.com",
        )

        response = self.client.post(
            reverse("customers:contact-create"),
            {
                "contact_type": Contact.Type.OTHER,
                "full_name": "Duplicate contact",
                "email": "SAME@example.com",
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bu email bilan kontakt allaqachon mavjud")
        self.assertFalse(Contact.objects.filter(full_name="Duplicate contact").exists())

    def test_contact_detail_shows_linked_lead_and_activity(self):
        contact = Contact.objects.create(
            organization=self.organization,
            full_name="Standalone prospect",
            contact_type=Contact.Type.PROSPECT,
        )
        lead = Lead.objects.create(
            organization=self.organization,
            contact=contact,
            title="Contact opportunity",
        )
        Activity.objects.create(
            organization=self.organization,
            contact=contact,
            activity_type=Activity.Type.CALL,
            subject="Contact follow-up",
        )

        response = self.client.get(
            reverse("customers:contact-detail", args=[contact.public_id]),
        )

        self.assertContains(response, lead.title)
        self.assertContains(response, "Contact follow-up")


class CustomerImportHelpersTests(TestCase):
    def test_normalized_name_ignores_legal_form_and_punctuation(self):
        self.assertEqual(
            normalized_name('ООО "COTONELLA"'),
            normalized_name("Cotonella"),
        )

    def test_merge_text_is_idempotent_for_multiline_source_text(self):
        source = "Birinchi izoh\n\nIkkinchi izoh"

        self.assertEqual(merge_text(source, source), source)


class ContactAvatarTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Avatar Textile",
            slug="avatar-textile",
        )
        self.media_directory = TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.media_directory.name)
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)
        self.addCleanup(self.media_directory.cleanup)

    @staticmethod
    def image_upload(filename="contact.jpg", size=(2000, 1000)):
        output = BytesIO()
        Image.new("RGB", size, color=(24, 116, 102)).save(
            output,
            format="JPEG",
            quality=90,
        )
        return SimpleUploadedFile(
            filename,
            output.getvalue(),
            content_type="image/jpeg",
        )

    def test_avatar_is_optimized_and_gets_a_unique_name(self):
        contact = Contact.objects.create(
            organization=self.organization,
            full_name="Avatar contact",
            avatar=self.image_upload(),
        )

        self.assertTrue(contact.avatar.name.startswith("images/contact/"))
        self.assertTrue(contact.avatar.name.endswith((".webp", ".jpg", ".png")))
        with Image.open(contact.avatar.path) as stored_image:
            self.assertLessEqual(stored_image.width, 1600)
            self.assertLessEqual(stored_image.height, 1600)
