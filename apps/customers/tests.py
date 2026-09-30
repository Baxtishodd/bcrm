from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.crm.models import Activity, Lead
from apps.organizations.models import Membership, Organization
from apps.sales.models import Quotation, QuotationDelivery

from .management.commands.import_customer_workbooks import merge_text, normalized_name
from .models import CustomerCompany


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


class CustomerImportHelpersTests(TestCase):
    def test_normalized_name_ignores_legal_form_and_punctuation(self):
        self.assertEqual(
            normalized_name('ООО "COTONELLA"'),
            normalized_name("Cotonella"),
        )

    def test_merge_text_is_idempotent_for_multiline_source_text(self):
        source = "Birinchi izoh\n\nIkkinchi izoh"

        self.assertEqual(merge_text(source, source), source)
