from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.catalog.models import Product
from apps.customers.models import CustomerCompany
from apps.organizations.models import Membership, Organization

from .models import Quotation, QuotationDelivery, QuotationLine, SalesOrder
from .services import convert_quotation_to_order


class QuotationConversionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="sales@example.com",
            password="test-password",
        )
        self.organization = Organization.objects.create(name="Sales Textile", slug="sales")
        Membership.objects.create(
            organization=self.organization,
            user=self.user,
            role=Membership.Role.SALES,
        )
        self.customer = CustomerCompany.objects.create(
            organization=self.organization,
            name="Buyer",
        )
        self.product = Product.objects.create(
            organization=self.organization,
            article="FAB-01",
            name="Fabric",
            unit=Product.Unit.METER,
        )
        self.quotation = Quotation.objects.create(
            organization=self.organization,
            number="QT-TEST-01",
            customer=self.customer,
            created_by=self.user,
            discount_percent=Decimal("10"),
            tax_percent=Decimal("12"),
        )
        QuotationLine.objects.create(
            organization=self.organization,
            quotation=self.quotation,
            product=self.product,
            quantity=Decimal("100"),
            unit_price=Decimal("20000"),
        )
        self.client.force_login(self.user)

    def test_total_applies_discount_then_tax(self):
        self.assertEqual(self.quotation.subtotal, Decimal("2000000"))
        self.assertEqual(self.quotation.discount_amount, Decimal("200000"))
        self.assertEqual(self.quotation.tax_amount, Decimal("216000"))
        self.assertEqual(self.quotation.total, Decimal("2016000"))

    def test_conversion_creates_one_order_and_copies_lines(self):
        order, created = convert_quotation_to_order(self.quotation, self.user)
        duplicate, duplicate_created = convert_quotation_to_order(self.quotation, self.user)

        self.quotation.refresh_from_db()
        self.assertTrue(created)
        self.assertFalse(duplicate_created)
        self.assertEqual(order, duplicate)
        self.assertEqual(SalesOrder.objects.count(), 1)
        self.assertEqual(order.lines.get().quantity, Decimal("100"))
        self.assertEqual(order.total, Decimal("2016000"))
        self.assertEqual(self.quotation.status, Quotation.Status.ACCEPTED)

    def test_delivery_log_records_channel_and_marks_draft_as_sent(self):
        response = self.client.post(
            reverse("sales:delivery-create", args=[self.quotation.public_id]),
            {
                "channel": QuotationDelivery.Channel.TELEGRAM,
                "recipient": "@buyer",
                "status": QuotationDelivery.Status.SENT,
                "notes": "Haftalik price-list yuborildi",
            },
        )

        delivery = self.quotation.deliveries.get()
        self.quotation.refresh_from_db()
        self.assertRedirects(
            response,
            reverse("sales:detail", args=[self.quotation.public_id]),
        )
        self.assertEqual(delivery.organization, self.organization)
        self.assertEqual(delivery.sent_by, self.user)
        self.assertEqual(delivery.channel, QuotationDelivery.Channel.TELEGRAM)
        self.assertEqual(self.quotation.status, Quotation.Status.SENT)
