from datetime import datetime, timedelta
from datetime import timezone as datetime_timezone
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from pypdf import PdfReader

from apps.accounts.models import MailboxAccount, User
from apps.catalog.models import Color, Product, ProductVariant, Size
from apps.common.models import AuditLog
from apps.crm.models import Activity, Lead, PipelineStage
from apps.customers.models import Contact, CustomerCompany
from apps.organizations.models import Membership, Organization

from .forms import (
    PaymentPlanForm,
    QuotationForm,
    QuotationLineForm,
    SalesOrderForm,
)
from .models import (
    OrderLineVariant,
    Payment,
    PaymentPlan,
    Quotation,
    QuotationDelivery,
    QuotationLine,
    SalesOrder,
)
from .services import convert_quotation_to_order, next_document_number


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
        self.mailbox = MailboxAccount(
            organization=self.organization,
            user=self.user,
            email="sales@example.com",
            display_name="Sales Manager",
            username="sales@example.com",
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_security=MailboxAccount.Security.STARTTLS,
            imap_host="imap.example.com",
            imap_port=993,
            imap_security=MailboxAccount.Security.SSL,
        )
        self.mailbox.set_password("app-password")
        self.mailbox.save()
        self.customer = CustomerCompany.objects.create(
            organization=self.organization,
            name="Buyer",
            email="buyer@example.com",
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

    def test_viewer_can_read_quotation_but_cannot_change_it(self):
        membership = Membership.objects.get(
            organization=self.organization,
            user=self.user,
        )
        membership.role = Membership.Role.VIEWER
        membership.save(update_fields=["role", "updated_at"])

        detail_url = reverse("sales:detail", args=[self.quotation.public_id])
        update_url = reverse("sales:update", args=[self.quotation.public_id])
        email_url = reverse("sales:email-send", args=[self.quotation.public_id])

        detail_response = self.client.get(detail_url)
        self.assertEqual(detail_response.status_code, 200)
        self.assertNotContains(detail_response, f'href="{update_url}"')
        self.assertNotContains(detail_response, f'href="{email_url}"')
        self.assertEqual(self.client.get(update_url).status_code, 403)
        self.assertEqual(self.client.get(email_url).status_code, 403)

    def test_sales_member_has_manage_sales_permission(self):
        response = self.client.get(
            reverse("sales:update", args=[self.quotation.public_id])
        )

        self.assertEqual(response.status_code, 200)

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

    def test_payment_plan_and_actual_payment_update_order_balance(self):
        order, _created = convert_quotation_to_order(self.quotation, self.user)

        plan_response = self.client.post(
            reverse("sales:payment-plan-create", args=[order.public_id]),
            {
                "due_date": "2026-10-15",
                "amount": "1000000",
                "notes": "Birinchi to'lov",
            },
        )
        self.assertRedirects(
            plan_response,
            reverse("sales:order-detail", args=[order.public_id]),
        )
        plan = PaymentPlan.objects.get(order=order)

        payment_response = self.client.post(
            reverse("sales:payment-create", args=[order.public_id]),
            {
                "plan": plan.pk,
                "received_on": "2026-10-10",
                "amount": "400000",
                "method": Payment.Method.BANK,
                "reference": "PAY-001",
                "notes": "Qisman tushum",
            },
        )

        self.assertRedirects(
            payment_response,
            reverse("sales:order-detail", args=[order.public_id]),
        )
        order.refresh_from_db()
        plan.refresh_from_db()
        payment = Payment.objects.get(order=order)
        self.assertEqual(payment.organization, self.organization)
        self.assertEqual(payment.created_by, self.user)
        self.assertEqual(order.paid_amount, Decimal("400000"))
        self.assertEqual(order.balance, Decimal("1616000"))
        self.assertEqual(plan.received_amount, Decimal("400000"))
        self.assertEqual(plan.balance, Decimal("600000"))
        self.assertEqual(plan.payment_status, "Qisman to'langan")

        detail_response = self.client.get(
            reverse("sales:order-detail", args=[order.public_id])
        )
        self.assertContains(detail_response, "PAY-001")
        self.assertContains(detail_response, "1000000,00")

        payment.delete()
        order.refresh_from_db()
        self.assertEqual(order.paid_amount, Decimal("0"))

    def test_payment_can_be_edited_and_cancelled_with_audit_history(self):
        order, _created = convert_quotation_to_order(self.quotation, self.user)
        plan = PaymentPlan.objects.create(
            organization=self.organization,
            order=order,
            due_date="2026-10-15",
            amount=Decimal("1000000"),
        )
        payment = Payment.objects.create(
            organization=self.organization,
            order=order,
            plan=plan,
            received_on="2026-10-10",
            amount=Decimal("400000"),
            created_by=self.user,
        )

        update_response = self.client.post(
            reverse("sales:payment-update", args=[payment.public_id]),
            {
                "plan": plan.pk,
                "received_on": "2026-10-11",
                "amount": "450000",
                "method": Payment.Method.CASH,
                "reference": "CASH-01",
                "notes": "Yangilandi",
            },
        )
        self.assertRedirects(
            update_response,
            reverse("sales:order-detail", args=[order.public_id]),
        )
        order.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(order.paid_amount, Decimal("450000"))
        self.assertEqual(payment.reference, "CASH-01")

        blocked_plan_cancel = self.client.post(
            reverse("sales:payment-plan-cancel", args=[plan.public_id]),
            {"reason": "Reja o'zgardi"},
        )
        self.assertRedirects(
            blocked_plan_cancel,
            reverse("sales:order-detail", args=[order.public_id]),
        )
        plan.refresh_from_db()
        self.assertFalse(plan.is_cancelled)

        cancel_response = self.client.post(
            reverse("sales:payment-cancel", args=[payment.public_id]),
            {"reason": "Noto'g'ri kiritilgan"},
        )
        self.assertRedirects(
            cancel_response,
            reverse("sales:order-detail", args=[order.public_id]),
        )
        order.refresh_from_db()
        payment.refresh_from_db()
        self.assertTrue(payment.is_cancelled)
        self.assertEqual(payment.cancelled_by, self.user)
        self.assertEqual(order.paid_amount, Decimal("0"))
        self.assertTrue(
            AuditLog.objects.filter(
                object_public_id=payment.public_id,
                action="cancelled",
                actor=self.user,
            ).exists()
        )

    def test_payment_plan_amount_cannot_be_less_than_received_amount(self):
        order, _created = convert_quotation_to_order(self.quotation, self.user)
        plan = PaymentPlan.objects.create(
            organization=self.organization,
            order=order,
            due_date="2026-10-15",
            amount=Decimal("1000000"),
        )
        Payment.objects.create(
            organization=self.organization,
            order=order,
            plan=plan,
            amount=Decimal("400000"),
            created_by=self.user,
        )

        response = self.client.post(
            reverse("sales:payment-plan-update", args=[plan.public_id]),
            {"due_date": "2026-10-15", "amount": "300000", "notes": ""},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "bog&#x27;langan tushumlar summasidan kam")
        plan.refresh_from_db()
        self.assertEqual(plan.amount, Decimal("1000000"))

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

    @patch("apps.sales.services.EmailMessage.send", return_value=1)
    def test_email_send_attaches_pdf_logs_delivery_and_creates_follow_up(self, send):
        response = self.client.post(
            reverse("sales:email-send", args=[self.quotation.public_id]),
            {
                "account": self.mailbox.pk,
                "recipient": "buyer@example.com",
                "subject": "Test quotation",
                "message": "Please find the quotation attached.",
                "follow_up_at": "2026-10-03T10:00",
            },
        )

        self.assertRedirects(
            response,
            reverse("sales:detail", args=[self.quotation.public_id]),
        )
        send.assert_called_once_with(fail_silently=False)
        delivery = self.quotation.deliveries.get(channel=QuotationDelivery.Channel.EMAIL)
        self.assertEqual(delivery.sender, "sales@example.com")
        self.assertEqual(delivery.subject, "Test quotation")
        self.assertEqual(delivery.message, "Please find the quotation attached.")
        self.assertEqual(delivery.status, QuotationDelivery.Status.SENT)
        follow_up = Activity.objects.get(customer=self.customer)
        self.assertIsNone(follow_up.lead)
        self.assertEqual(follow_up.activity_type, Activity.Type.TASK)
        self.assertEqual(follow_up.assigned_to, self.user)
        self.quotation.refresh_from_db()
        self.assertEqual(self.quotation.status, Quotation.Status.SENT)

    def test_email_form_has_duplicate_submit_guard(self):
        response = self.client.get(
            reverse("sales:email-send", args=[self.quotation.public_id])
        )

        self.assertContains(response, "data-submit-guard")
        self.assertContains(response, "Yuborilmoqda...")
        self.assertContains(response, "data-submit-status")

    @patch("apps.sales.services.EmailMessage.send", side_effect=OSError("SMTP offline"))
    def test_email_failure_is_logged_without_follow_up(self, _send):
        response = self.client.post(
            reverse("sales:email-send", args=[self.quotation.public_id]),
            {
                "account": self.mailbox.pk,
                "recipient": "buyer@example.com",
                "subject": "Test quotation",
                "message": "Please find the quotation attached.",
                "follow_up_at": "2026-10-03T10:00",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Email yuborilmadi")
        delivery = self.quotation.deliveries.get()
        self.assertEqual(delivery.status, QuotationDelivery.Status.FAILED)
        self.assertEqual(
            delivery.notes,
            "Email yuborilmadi. SMTP server bilan aloqa o'rnatilmadi.",
        )
        self.assertFalse(Activity.objects.filter(customer=self.customer).exists())

    @patch("apps.sales.services.EmailMessage.send", return_value=1)
    def test_email_form_rejects_another_users_mailbox(self, send):
        other_user = User.objects.create_user(
            email="other@example.com",
            password="test-password",
        )
        other_mailbox = MailboxAccount(
            organization=self.organization,
            user=other_user,
            email="other@example.com",
            username="other@example.com",
            smtp_host="smtp.example.com",
            imap_host="imap.example.com",
        )
        other_mailbox.set_password("other-password")
        other_mailbox.save()

        response = self.client.post(
            reverse("sales:email-send", args=[self.quotation.public_id]),
            {
                "account": other_mailbox.pk,
                "recipient": "buyer@example.com",
                "subject": "Hidden mailbox",
                "message": "Must not send.",
                "follow_up_at": "2026-10-03T10:00",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("account", response.context["form"].errors)
        send.assert_not_called()
        self.assertFalse(self.quotation.deliveries.exists())


class LeadQuotationWorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="lead-sales@example.com",
            password="test-password",
        )
        self.organization = Organization.objects.create(
            name="Lead Sales Textile",
            slug="lead-sales",
        )
        Membership.objects.create(
            organization=self.organization,
            user=self.user,
            role=Membership.Role.SALES,
        )
        self.customer = CustomerCompany.objects.create(
            organization=self.organization,
            name="Lead Buyer",
        )
        self.contact = Contact.objects.create(
            organization=self.organization,
            company=self.customer,
            full_name="Buyer Contact",
            email="buyer@example.com",
        )
        self.lead = Lead.objects.create(
            organization=self.organization,
            title="New fabric request",
            customer=self.customer,
            contact=self.contact,
            assigned_to=self.user,
            currency="USD",
            description="Monthly fabric requirement",
        )
        self.won_stage = PipelineStage.objects.create(
            organization=self.organization,
            name="Yutildi",
            position=50,
            probability=100,
            is_closed=True,
        )
        self.product = Product.objects.create(
            organization=self.organization,
            article="KNIT-01",
            name="Knitted fabric",
            description="Cotton knitted fabric",
            unit=Product.Unit.KILOGRAM,
            list_price=Decimal("3.25"),
            price_currency="USD",
        )
        color = Color.objects.create(
            organization=self.organization,
            name="Black",
        )
        size = Size.objects.create(
            organization=self.organization,
            name="Standard",
        )
        self.variant = ProductVariant.objects.create(
            organization=self.organization,
            product=self.product,
            color=color,
            size=size,
            sku="KNIT-01-BLK",
        )
        self.client.force_login(self.user)

    def create_quotation_from_lead(self):
        return self.client.post(
            reverse("sales:create-from-lead", args=[self.lead.public_id]),
            {
                "number": "",
                "contact": self.contact.pk,
                "assigned_to": self.user.pk,
                "status": Quotation.Status.DRAFT,
                "currency": "USD",
                "valid_until": "2026-10-13",
                "discount_percent": "0",
                "tax_percent": "0",
                "delivery_terms": "FCA Koson",
                "payment_terms": "100% oldindan to'lov",
                "notes": self.lead.description,
            },
        )

    def test_create_form_is_prefilled_from_lead(self):
        response = self.client.get(reverse("sales:create-from-lead", args=[self.lead.public_id]))

        form = response.context["form"]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(form.initial["customer"], self.customer)
        self.assertEqual(form.initial["contact"], self.contact)
        self.assertEqual(form.initial["lead"], self.lead)
        self.assertEqual(form.initial["assigned_to"], self.user)
        self.assertEqual(form.initial["currency"], "USD")
        self.assertTrue(form.fields["customer"].disabled)
        self.assertTrue(form.fields["lead"].disabled)
        self.assertIn("data-smart-select", form.fields["customer"].widget.attrs)
        self.assertEqual(
            form.fields["contact"].widget.attrs["data-smart-select-depends-on"],
            "customer",
        )
        self.assertIn(
            f'data-parent-value="{self.customer.pk}"',
            str(form["contact"]),
        )

    def test_organization_sales_defaults_are_used_for_new_quotation(self):
        self.organization.default_delivery_terms = "FCA Koson"
        self.organization.default_payment_terms = "100% oldindan to'lov"
        self.organization.quotation_validity_days = 30
        self.organization.quotation_number_prefix = "BT-Q"
        self.organization.save()

        response = self.client.get(reverse("sales:create-from-lead", args=[self.lead.public_id]))
        form = response.context["form"]

        self.assertEqual(form.initial["delivery_terms"], "FCA Koson")
        self.assertEqual(form.initial["payment_terms"], "100% oldindan to'lov")
        self.assertEqual(
            form.initial["valid_until"],
            timezone.localdate() + timedelta(days=30),
        )
        self.assertTrue(next_document_number(Quotation, self.organization).startswith("BT-Q-"))

    def test_create_from_lead_copies_relationships_and_shows_history(self):
        response = self.create_quotation_from_lead()

        quotation = Quotation.objects.get(lead=self.lead)
        self.assertRedirects(
            response,
            reverse("sales:detail", args=[quotation.public_id]),
        )
        self.assertEqual(quotation.customer, self.customer)
        self.assertEqual(quotation.contact, self.contact)
        self.assertEqual(quotation.assigned_to, self.user)
        self.assertEqual(quotation.created_by, self.user)
        self.assertEqual(quotation.currency, "USD")

        lead_response = self.client.get(reverse("crm:detail", args=[self.lead.public_id]))
        self.assertContains(lead_response, quotation.number)
        self.assertContains(lead_response, "Takliflar tarixi")

    def test_catalog_price_and_variant_are_copied_to_line_and_order(self):
        self.create_quotation_from_lead()
        quotation = Quotation.objects.get(lead=self.lead)

        response = self.client.post(
            reverse("sales:line-create", args=[quotation.public_id]),
            {
                "product": self.product.pk,
                "variant": self.variant.pk,
                "description": "",
                "quantity": "2",
                "unit_price": "",
            },
        )

        line = quotation.lines.get()
        self.assertRedirects(
            response,
            reverse("sales:detail", args=[quotation.public_id]),
        )
        self.assertEqual(line.variant, self.variant)
        self.assertEqual(line.unit_price, self.product.list_price)
        self.assertEqual(line.description, self.product.description)

        order, created = convert_quotation_to_order(quotation, self.user)
        self.assertTrue(created)
        variant_quantity = OrderLineVariant.objects.get(order_line__order=order)
        self.assertEqual(variant_quantity.variant, self.variant)
        self.assertEqual(variant_quantity.quantity, 2)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, Lead.Status.WON)
        self.assertEqual(self.lead.stage, self.won_stage)

    def test_complete_lead_quotation_pdf_order_flow(self):
        self.create_quotation_from_lead()
        quotation = Quotation.objects.get(lead=self.lead)
        line_response = self.client.post(
            reverse("sales:line-create", args=[quotation.public_id]),
            {
                "product": self.product.pk,
                "variant": self.variant.pk,
                "description": "E2E knitted fabric",
                "quantity": "1000",
                "unit_price": "3.25",
            },
        )
        self.assertRedirects(
            line_response,
            reverse("sales:detail", args=[quotation.public_id]),
        )

        pdf_response = self.client.get(reverse("sales:pdf", args=[quotation.public_id]))
        self.assertEqual(pdf_response.status_code, 200)
        self.assertTrue(pdf_response.content.startswith(b"%PDF"))

        convert_response = self.client.post(
            reverse("sales:convert", args=[quotation.public_id]),
        )
        order = SalesOrder.objects.get(quotation=quotation)
        self.assertRedirects(
            convert_response,
            reverse("sales:order-detail", args=[order.public_id]),
        )
        quotation.refresh_from_db()
        self.lead.refresh_from_db()
        self.assertEqual(quotation.status, Quotation.Status.ACCEPTED)
        self.assertEqual(self.lead.status, Lead.Status.WON)
        self.assertEqual(order.lines.get().quantity, Decimal("1000"))

    def test_sales_forms_reject_invalid_financial_values(self):
        quotation_form = QuotationForm(
            data={
                "customer": self.customer.pk,
                "contact": self.contact.pk,
                "lead": self.lead.pk,
                "assigned_to": self.user.pk,
                "status": Quotation.Status.DRAFT,
                "currency": "USD",
                "discount_percent": "-1",
                "tax_percent": "101",
                "delivery_terms": "FCA Koson",
                "payment_terms": "Oldindan to'lov",
                "notes": "",
            },
            organization=self.organization,
        )
        line_form = QuotationLineForm(
            data={
                "product": self.product.pk,
                "variant": "",
                "description": "Invalid values",
                "quantity": "0",
                "unit_price": "-0.01",
            },
            organization=self.organization,
        )
        order_form = SalesOrderForm(
            data={
                "customer": self.customer.pk,
                "quotation": "",
                "status": SalesOrder.Status.DRAFT,
                "order_date": "2026-09-30",
                "delivery_date": "",
                "advance_amount": "-1",
                "assigned_to": self.user.pk,
                "notes": "",
            },
            organization=self.organization,
        )

        self.assertFalse(quotation_form.is_valid())
        self.assertIn("discount_percent", quotation_form.errors)
        self.assertIn("tax_percent", quotation_form.errors)
        self.assertFalse(line_form.is_valid())
        self.assertIn("quantity", line_form.errors)
        self.assertIn("unit_price", line_form.errors)
        self.assertFalse(order_form.is_valid())
        self.assertIn("advance_amount", order_form.errors)
        self.assertNotIn("paid_amount", order_form.fields)

        payment_plan_form = PaymentPlanForm(
            data={"due_date": "2026-09-30", "amount": "0", "notes": ""}
        )
        self.assertFalse(payment_plan_form.is_valid())
        self.assertIn("amount", payment_plan_form.errors)

    def test_won_lead_shows_order_action_then_link(self):
        self.create_quotation_from_lead()
        quotation = Quotation.objects.get(lead=self.lead)
        QuotationLine.objects.create(
            organization=self.organization,
            quotation=quotation,
            product=self.product,
            quantity=Decimal("10"),
            unit_price=Decimal("3.25"),
        )
        self.lead.status = Lead.Status.WON
        self.lead.stage = self.won_stage
        self.lead.save()

        response = self.client.get(reverse("crm:detail", args=[self.lead.public_id]))
        self.assertContains(response, "Buyurtma yaratish")

        order, _ = convert_quotation_to_order(quotation, self.user)
        response = self.client.get(reverse("crm:detail", args=[self.lead.public_id]))
        self.assertContains(response, "Buyurtmani ko'rish")
        self.assertContains(response, reverse("sales:order-detail", args=[order.public_id]))

    def test_create_from_lead_is_tenant_scoped(self):
        other_org = Organization.objects.create(name="Other", slug="other-sales")
        other_customer = CustomerCompany.objects.create(
            organization=other_org,
            name="Other buyer",
        )
        other_lead = Lead.objects.create(
            organization=other_org,
            title="Hidden lead",
            customer=other_customer,
        )

        response = self.client.get(reverse("sales:create-from-lead", args=[other_lead.public_id]))

        self.assertEqual(response.status_code, 404)

    def test_lead_without_customer_cannot_create_quotation(self):
        lead = Lead.objects.create(
            organization=self.organization,
            title="Customer missing",
        )

        response = self.client.get(reverse("sales:create-from-lead", args=[lead.public_id]))

        self.assertRedirects(response, reverse("crm:detail", args=[lead.public_id]))
        self.assertFalse(Quotation.objects.filter(lead=lead).exists())

    def test_document_editor_updates_text_and_product_lines(self):
        self.create_quotation_from_lead()
        quotation = Quotation.objects.get(lead=self.lead)
        line = QuotationLine.objects.create(
            organization=self.organization,
            quotation=quotation,
            product=self.product,
            variant=self.variant,
            description="Old description",
            quantity=Decimal("2"),
            unit_price=Decimal("3.25"),
        )

        response = self.client.post(
            reverse("sales:document-edit", args=[quotation.public_id]),
            {
                "document_language": Quotation.DocumentLanguage.UZ,
                "document_title": "MAXSUS SAVDO TAKLIFI",
                "document_intro": "Hurmatli hamkor, yangi taklifimizni taqdim etamiz.",
                "currency": "USD",
                "valid_until": "2026-10-29",
                "discount_percent": "5",
                "tax_percent": "12",
                "delivery_terms": "FCA Koson",
                "payment_terms": "100% oldindan to'lov",
                "notes": "Sinov partiyasi",
                "document_footer": "Bunyodkor Textile savdo bo'limi",
                "lines-TOTAL_FORMS": "1",
                "lines-INITIAL_FORMS": "1",
                "lines-MIN_NUM_FORMS": "0",
                "lines-MAX_NUM_FORMS": "1000",
                "lines-0-id": str(line.pk),
                "lines-0-product": str(self.product.pk),
                "lines-0-variant": str(self.variant.pk),
                "lines-0-description": "Updated description",
                "lines-0-quantity": "3",
                "lines-0-unit_price": "3.50",
            },
        )

        quotation.refresh_from_db()
        line.refresh_from_db()
        self.assertRedirects(
            response,
            reverse("sales:document-edit", args=[quotation.public_id]),
        )
        self.assertEqual(quotation.document_title, "MAXSUS SAVDO TAKLIFI")
        self.assertEqual(quotation.currency, "USD")
        self.assertEqual(line.description, "Updated description")
        self.assertEqual(line.quantity, Decimal("3"))
        self.assertEqual(line.unit_price, Decimal("3.50"))

    def test_pdf_download_contains_document_and_textile_details(self):
        self.organization.legal_name = "Bunyodkor Textile MChJ"
        self.organization.default_incoterm = "FCA Koson"
        self.organization.save()
        self.create_quotation_from_lead()
        quotation = Quotation.objects.get(lead=self.lead)
        quotation.document_intro = "Hurmatli hamkor, tijorat taklifimizni yuboramiz."
        quotation.save()
        Quotation.objects.filter(pk=quotation.pk).update(
            created_at=datetime(2026, 9, 29, 20, 0, tzinfo=datetime_timezone.utc),
        )
        quotation.refresh_from_db()
        QuotationLine.objects.create(
            organization=self.organization,
            quotation=quotation,
            product=self.product,
            variant=self.variant,
            description="100% paxta trikotaj mato",
            quantity=Decimal("1200"),
            unit_price=Decimal("3.25"),
        )

        response = self.client.get(reverse("sales:pdf", args=[quotation.public_id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn(quotation.number, response["Content-Disposition"])
        reader = PdfReader(BytesIO(response.content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        self.assertIn("TIJORAT TAKLIFI", text)
        self.assertIn("30.09.2026", text)
        self.assertIn(self.customer.name, text)
        self.assertIn(self.product.article, text)
        self.assertIn("100% paxta trikotaj mato", text)

    def test_document_editor_and_pdf_are_tenant_scoped(self):
        other_org = Organization.objects.create(name="Hidden", slug="hidden-doc")
        other_user = User.objects.create_user(
            email="hidden@example.com",
            password="test-password",
        )
        other_customer = CustomerCompany.objects.create(
            organization=other_org,
            name="Hidden customer",
        )
        hidden = Quotation.objects.create(
            organization=other_org,
            number="HIDDEN-Q-1",
            customer=other_customer,
            created_by=other_user,
        )
        hidden_order = SalesOrder.objects.create(
            organization=other_org,
            number="HIDDEN-SO-1",
            customer=other_customer,
            quotation=hidden,
            order_date=timezone.localdate(),
            created_by=other_user,
        )

        quotation_urls = (
            reverse("sales:detail", args=[hidden.public_id]),
            reverse("sales:update", args=[hidden.public_id]),
            reverse("sales:line-create", args=[hidden.public_id]),
            reverse("sales:delivery-create", args=[hidden.public_id]),
            reverse("sales:email-send", args=[hidden.public_id]),
            reverse("sales:document-edit", args=[hidden.public_id]),
            reverse("sales:pdf", args=[hidden.public_id]),
        )
        for url in quotation_urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(
            self.client.post(reverse("sales:convert", args=[hidden.public_id])).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse("sales:order-detail", args=[hidden_order.public_id])
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse("sales:order-update", args=[hidden_order.public_id])
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse("sales:payment-plan-create", args=[hidden_order.public_id])
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse("sales:payment-create", args=[hidden_order.public_id])
            ).status_code,
            404,
        )
