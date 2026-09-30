from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.crm.models import Activity, Lead
from apps.customers.models import CustomerCompany
from apps.organizations.models import Membership, Organization
from apps.sales.models import Payment, PaymentPlan, Quotation, SalesOrder


class CrossModulePermissionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="viewer@example.com",
            password="test-password",
        )
        self.organization = Organization.objects.create(
            name="Permission Textile",
            slug="permission-textile",
        )
        self.membership = Membership.objects.create(
            organization=self.organization,
            user=self.user,
            role=Membership.Role.VIEWER,
        )
        self.customer = CustomerCompany.objects.create(
            organization=self.organization,
            name="Read only customer",
        )
        self.lead = Lead.objects.create(
            organization=self.organization,
            customer=self.customer,
            title="Read only lead",
        )
        self.task = Activity.objects.create(
            organization=self.organization,
            lead=self.lead,
            activity_type=Activity.Type.TASK,
            subject="Read only task",
        )
        self.client.force_login(self.user)

    def set_role(self, role):
        self.membership.role = role
        self.membership.save(update_fields=["role", "updated_at"])

    def test_viewer_can_read_modules_but_cannot_open_write_views(self):
        read_urls = (
            reverse("customers:list"),
            reverse("crm:list"),
            reverse("tasks:list"),
            reverse("catalog:list"),
            reverse("sales:list"),
        )
        write_urls = (
            reverse("customers:create"),
            reverse("crm:create"),
            reverse("tasks:create"),
            reverse("catalog:create"),
            reverse("accounts:mailbox-list"),
        )

        for url in read_urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
        for url in write_urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_viewer_ui_hides_mutation_controls_and_kanban_drag_handle(self):
        customer_response = self.client.get(
            reverse("customers:detail", args=[self.customer.public_id])
        )
        lead_response = self.client.get(reverse("crm:list"))
        task_response = self.client.get(reverse("tasks:list"))

        self.assertNotContains(customer_response, "Kontakt qo&#x27;shish")
        self.assertNotContains(lead_response, reverse("crm:create"))
        self.assertNotContains(lead_response, "data-kanban-update-url")
        self.assertNotContains(task_response, reverse("tasks:create"))

    def test_viewer_can_read_api_but_cannot_write(self):
        endpoints = (
            "/api/v1/customers/companies/",
            "/api/v1/crm/leads/",
            "/api/v1/catalog/products/",
            "/api/v1/sales/quotations/",
        )

        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint, method="get"):
                self.assertEqual(self.client.get(endpoint).status_code, 200)
            with self.subTest(endpoint=endpoint, method="post"):
                self.assertEqual(self.client.post(endpoint, {}).status_code, 403)

    def test_technologist_can_manage_catalog_and_tasks_only(self):
        self.set_role(Membership.Role.TECHNOLOGIST)

        self.assertEqual(self.client.get(reverse("catalog:create")).status_code, 200)
        self.assertEqual(self.client.get(reverse("tasks:create")).status_code, 200)
        self.assertEqual(self.client.get(reverse("customers:create")).status_code, 403)
        self.assertEqual(self.client.get(reverse("crm:create")).status_code, 403)
        self.assertEqual(self.client.get(reverse("accounts:mailbox-list")).status_code, 403)

    def test_accountant_can_manage_tasks_and_own_mailbox(self):
        self.set_role(Membership.Role.ACCOUNTANT)

        self.assertEqual(self.client.get(reverse("tasks:create")).status_code, 200)
        self.assertEqual(self.client.get(reverse("accounts:mailbox-list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("catalog:create")).status_code, 403)

    def test_sales_member_can_manage_commercial_modules(self):
        self.set_role(Membership.Role.SALES)

        allowed_urls = (
            reverse("customers:create"),
            reverse("crm:create"),
            reverse("tasks:create"),
            reverse("catalog:create"),
            reverse("sales:create"),
            reverse("accounts:mailbox-list"),
        )

        for url in allowed_urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_every_employee_role_has_the_expected_write_access(self):
        write_urls = {
            "organization": reverse("organizations:employees"),
            "customers": reverse("customers:create"),
            "leads": reverse("crm:create"),
            "tasks": reverse("tasks:create"),
            "catalog": reverse("catalog:create"),
            "sales": reverse("sales:create"),
            "mailbox": reverse("accounts:mailbox-list"),
        }
        expected_access = {
            Membership.Role.OWNER: set(write_urls),
            Membership.Role.DIRECTOR: set(write_urls),
            Membership.Role.SALES: {
                "customers",
                "leads",
                "tasks",
                "catalog",
                "sales",
                "mailbox",
            },
            Membership.Role.TECHNOLOGIST: {"tasks", "catalog"},
            Membership.Role.PRODUCTION: {"tasks"},
            Membership.Role.WAREHOUSE: {"tasks"},
            Membership.Role.ACCOUNTANT: {"tasks", "mailbox"},
            Membership.Role.VIEWER: set(),
        }

        for role, allowed_modules in expected_access.items():
            self.set_role(role)
            for module, url in write_urls.items():
                with self.subTest(role=role, module=module):
                    expected_status = 200 if module in allowed_modules else 403
                    self.assertEqual(self.client.get(url).status_code, expected_status)


class SalesReportTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="report-owner@example.com",
            password="test-password",
        )
        self.salesperson = User.objects.create_user(
            email="seller@example.com",
            password="test-password",
            first_name="Sardor",
            last_name="Sotuvchi",
        )
        self.organization = Organization.objects.create(
            name="Report Textile",
            slug="report-textile",
        )
        Membership.objects.create(
            organization=self.organization,
            user=self.owner,
            role=Membership.Role.OWNER,
        )
        Membership.objects.create(
            organization=self.organization,
            user=self.salesperson,
            role=Membership.Role.SALES,
        )
        self.customer = CustomerCompany.objects.create(
            organization=self.organization,
            name="Report Customer",
        )
        lead_rows = (
            ("New USD", Lead.Status.NEW, Lead.BusinessDirection.YARN, "USD", 1000, ""),
            (
                "Progress UZS",
                Lead.Status.IN_PROGRESS,
                Lead.BusinessDirection.KNIT_FABRIC,
                "UZS",
                2000000,
                "",
            ),
            ("Won USD", Lead.Status.WON, Lead.BusinessDirection.YARN, "USD", 3000, ""),
            (
                "Lost USD",
                Lead.Status.LOST,
                Lead.BusinessDirection.YARN,
                "USD",
                500,
                "Narx mos kelmadi",
            ),
        )
        self.leads = []
        for title, status, direction, currency, value, lost_reason in lead_rows:
            self.leads.append(Lead.objects.create(
                organization=self.organization,
                customer=self.customer,
                title=title,
                status=status,
                business_direction=direction,
                currency=currency,
                estimated_value=value,
                lost_reason=lost_reason,
                assigned_to=self.salesperson,
            ))
        quotation = Quotation.objects.create(
            organization=self.organization,
            number="QT-REPORT-1",
            customer=self.customer,
            lead=self.leads[2],
            currency="USD",
            created_by=self.salesperson,
        )
        order = SalesOrder.objects.create(
            organization=self.organization,
            number="SO-REPORT-1",
            customer=self.customer,
            quotation=quotation,
            order_date=date(2026, 9, 30),
            created_by=self.salesperson,
        )
        plan = PaymentPlan.objects.create(
            organization=self.organization,
            order=order,
            due_date=timezone.localdate() + timedelta(days=15),
            amount=Decimal("2000"),
        )
        Payment.objects.create(
            organization=self.organization,
            order=order,
            plan=plan,
            received_on=timezone.localdate() + timedelta(days=10),
            amount=Decimal("750"),
            created_by=self.salesperson,
        )
        self.client.force_login(self.owner)

    def test_report_calculates_funnel_conversion_and_currency_totals(self):
        response = self.client.get(reverse("sales-report"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_count"], 4)
        self.assertEqual(response.context["won_count"], 1)
        self.assertEqual(response.context["lost_count"], 1)
        self.assertEqual(response.context["conversion_rate"], 50.0)
        self.assertEqual(
            response.context["lost_reasons"],
            [{"lost_reason": "Narx mos kelmadi", "count": 1}],
        )
        pipeline = {
            row["currency"]: row["total"]
            for row in response.context["pipeline_by_currency"]
        }
        self.assertEqual(pipeline["USD"], 1000)
        self.assertEqual(pipeline["UZS"], 2000000)
        self.assertEqual(
            response.context["payment_comparison"],
            [
                {
                    "currency": "USD",
                    "planned": Decimal("2000"),
                    "actual": Decimal("750"),
                    "difference": Decimal("-1250"),
                }
            ],
        )
        self.assertEqual(
            response.context["cash_forecast"],
            [
                {
                    "currency": "USD",
                    "overdue": Decimal("0"),
                    "next_7_days": Decimal("0"),
                    "next_30_days": Decimal("1250"),
                }
            ],
        )

    def test_dashboard_shows_currency_cashflow_forecast(self):
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "7/30 kunlik tushum prognozi")
        self.assertContains(response, "1000,00")
        self.assertContains(response, "2000000,00")
        self.assertEqual(
            response.context["pipeline_by_currency"],
            [
                {"currency": "USD", "total": Decimal("1000")},
                {"currency": "UZS", "total": Decimal("2000000")},
            ],
        )
        self.assertEqual(response.context["orders_by_currency"], [])
        self.assertEqual(
            response.context["cash_forecast"],
            [
                {
                    "currency": "USD",
                    "overdue": Decimal("0"),
                    "next_7_days": Decimal("0"),
                    "next_30_days": Decimal("1250"),
                }
            ],
        )

    def test_report_filters_by_manager_and_business_direction(self):
        response = self.client.get(
            reverse("sales-report"),
            {
                "assigned_to": self.salesperson.pk,
                "business_direction": Lead.BusinessDirection.YARN,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_count"], 3)
        self.assertEqual(response.context["won_count"], 1)
        self.assertEqual(response.context["lost_count"], 1)

    def test_report_excludes_another_organizations_data(self):
        other_organization = Organization.objects.create(
            name="Other Report Textile",
            slug="other-report-textile",
        )
        other_customer = CustomerCompany.objects.create(
            organization=other_organization,
            name="Other Customer",
        )
        Lead.objects.create(
            organization=other_organization,
            customer=other_customer,
            title="Hidden won lead",
            status=Lead.Status.WON,
        )

        response = self.client.get(reverse("sales-report"))

        self.assertEqual(response.context["total_count"], 4)
        self.assertNotContains(response, "Hidden won lead")

    def test_sales_employee_cannot_open_management_report(self):
        self.client.force_login(self.salesperson)

        response = self.client.get(reverse("sales-report"))
        dashboard_response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 403)
        self.assertNotContains(dashboard_response, reverse("sales-report"))
