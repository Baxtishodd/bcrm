from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.crm.models import Activity, Lead
from apps.customers.models import Contact, CustomerCompany
from apps.organizations.models import Membership, Organization
from apps.sales.models import Payment, PaymentPlan, Quotation, SalesOrder

from .views import build_sales_dashboard_analytics


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
        self.order = SalesOrder.objects.create(
            organization=self.organization,
            number="SO-REPORT-1",
            customer=self.customer,
            quotation=quotation,
            order_date=date(2026, 9, 30),
            created_by=self.salesperson,
        )
        self.plan = PaymentPlan.objects.create(
            organization=self.organization,
            order=self.order,
            due_date=timezone.localdate() + timedelta(days=15),
            amount=Decimal("2000"),
        )
        Payment.objects.create(
            organization=self.organization,
            order=self.order,
            plan=self.plan,
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
        self.assertContains(response, "Savdo analitikasi")
        self.assertContains(response, "js/sales-analytics.js")
        self.assertContains(response, "badge-status-new")
        self.assertContains(response, "badge-status-in_progress")
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

    def test_dashboard_sales_analytics_compares_matching_month_periods(self):
        today = date(2026, 10, 8)

        def order(order_date, total, balance, status=SalesOrder.Status.CONFIRMED):
            return SimpleNamespace(
                order_date=order_date,
                currency="USD",
                total=Decimal(total),
                balance=Decimal(balance),
                status=status,
            )

        current_first = order(date(2026, 10, 2), "1200", "400")
        current_second = order(date(2026, 10, 6), "800", "800")
        previous_matching = order(date(2026, 9, 3), "1000", "0")
        previous_after_cutoff = order(date(2026, 9, 20), "900", "900")
        cancelled = order(
            date(2026, 10, 4),
            "500",
            "500",
            SalesOrder.Status.CANCELLED,
        )
        payments = [
            SimpleNamespace(
                order=current_first,
                received_on=date(2026, 10, 5),
                amount=Decimal("750"),
                is_cancelled=False,
            ),
            SimpleNamespace(
                order=current_second,
                received_on=date(2026, 10, 5),
                amount=Decimal("100"),
                is_cancelled=True,
            ),
        ]

        rows = build_sales_dashboard_analytics(
            [
                current_first,
                current_second,
                previous_matching,
                previous_after_cutoff,
                cancelled,
            ],
            payments,
            today,
        )

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["current_sales"], Decimal("2000"))
        self.assertEqual(row["previous_sales"], Decimal("1000"))
        self.assertEqual(row["change_percent"], Decimal("100.0"))
        self.assertEqual(row["current_receipts"], Decimal("750"))
        self.assertEqual(row["outstanding"], Decimal("2100"))
        self.assertEqual(row["order_count"], 2)
        self.assertEqual(row["average_order"], Decimal("1000"))
        self.assertEqual(row["daily_current"][-1], Decimal("2000"))
        self.assertEqual(row["daily_previous"][-1], Decimal("1000"))
        self.assertEqual(row["monthly_sales"][-1], Decimal("2000"))
        self.assertEqual(row["monthly_sales"][-2], Decimal("1900"))

    def test_dashboard_sales_analytics_keeps_currencies_separate(self):
        usd_order = SimpleNamespace(
            order_date=date(2026, 10, 2),
            currency="USD",
            total=Decimal("100"),
            balance=Decimal("40"),
            status=SalesOrder.Status.CONFIRMED,
        )
        uzs_order = SimpleNamespace(
            order_date=date(2026, 10, 3),
            currency="UZS",
            total=Decimal("1200000"),
            balance=Decimal("200000"),
            status=SalesOrder.Status.CONFIRMED,
        )

        rows = build_sales_dashboard_analytics(
            [usd_order, uzs_order],
            [],
            date(2026, 10, 8),
        )

        self.assertEqual([row["currency"] for row in rows], ["USD", "UZS"])
        self.assertEqual(rows[0]["current_sales"], Decimal("100"))
        self.assertEqual(rows[1]["current_sales"], Decimal("1200000"))

    def test_dashboard_sales_analytics_puts_preferred_currency_first(self):
        usd_order = SimpleNamespace(
            order_date=date(2026, 10, 2),
            currency="USD",
            total=Decimal("100"),
            balance=Decimal("40"),
            status=SalesOrder.Status.CONFIRMED,
        )
        eur_order = SimpleNamespace(
            order_date=date(2026, 10, 3),
            currency="EUR",
            total=Decimal("80"),
            balance=Decimal("20"),
            status=SalesOrder.Status.CONFIRMED,
        )

        rows = build_sales_dashboard_analytics(
            [eur_order, usd_order],
            [],
            date(2026, 10, 8),
            preferred_currency="USD",
        )

        self.assertEqual([row["currency"] for row in rows], ["USD", "EUR"])

    def test_dashboard_supports_tasks_without_a_lead(self):
        contact = Contact.objects.create(
            organization=self.organization,
            full_name="Dashboard contact",
        )
        Activity.objects.create(
            organization=self.organization,
            contact=contact,
            customer=self.customer,
            activity_type=Activity.Type.TASK,
            subject="Kontakt bilan bog'lanish",
        )
        Activity.objects.create(
            organization=self.organization,
            customer=self.customer,
            activity_type=Activity.Type.TASK,
            subject="Mijoz bilan bog'lanish",
        )

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard contact")
        self.assertContains(
            response,
            reverse("customers:contact-detail", args=[contact.public_id]),
        )
        self.assertContains(
            response,
            reverse("customers:detail", args=[self.customer.public_id]),
        )

    def test_sidebar_context_is_consistent_on_dashboard_and_password_change(self):
        self.organization.logo = "images/organization/test-logo.png"
        self.organization.save(update_fields=["logo", "updated_at"])
        expected_links = (
            reverse("sales-report"),
            reverse("accounts:mailbox-list"),
            reverse("organizations:settings"),
            reverse("organizations:employees"),
        )

        for url in (reverse("dashboard"), reverse("accounts:password-change")):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["organization"], self.organization)
                self.assertContains(response, self.organization.logo.url)
                for expected_link in expected_links:
                    self.assertContains(response, expected_link)
                self.assertContains(response, '<use href="#icon-dashboard"></use>', html=True)
                self.assertContains(response, '<use href="#icon-customers"></use>', html=True)
                self.assertContains(response, '<use href="#icon-reports"></use>', html=True)
                self.assertContains(response, "<span>Dashboard</span>", html=True)
                self.assertContains(response, 'class="sidebar-toggle"')
                self.assertContains(response, 'aria-controls="sidebar-navigation"')
                self.assertContains(response, "js/sidebar.js")
                self.assertContains(response, "js/motion.js")

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

    def test_financial_filters_and_debt_aging(self):
        overdue_plan = PaymentPlan.objects.create(
            organization=self.organization,
            order=self.order,
            due_date=timezone.localdate() - timedelta(days=10),
            amount=Decimal("600"),
            notes="Kechikkan test to'lovi",
        )

        response = self.client.get(
            reverse("sales-report"),
            {
                "customer": self.customer.pk,
                "currency": "USD",
                "payment_status": "overdue",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["aging_summary"],
            [
                {
                    "currency": "USD",
                    "days_1_7": Decimal("0"),
                    "days_8_30": Decimal("600"),
                    "days_31_60": Decimal("0"),
                    "days_60_plus": Decimal("0"),
                }
            ],
        )
        self.assertEqual(len(response.context["debt_rows"]), 1)
        self.assertEqual(response.context["debt_rows"][0]["plan"], overdue_plan)

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


class RecordOwnershipPermissionTests(TestCase):
    def setUp(self):
        self.first_employee = User.objects.create_user(
            email="first-sales@example.com",
            password="test-password",
        )
        self.second_employee = User.objects.create_user(
            email="second-sales@example.com",
            password="test-password",
        )
        self.organization = Organization.objects.create(
            name="Ownership Textile",
            slug="ownership-textile",
        )
        Membership.objects.create(
            organization=self.organization,
            user=self.first_employee,
            role=Membership.Role.SALES,
        )
        self.second_membership = Membership.objects.create(
            organization=self.organization,
            user=self.second_employee,
            role=Membership.Role.SALES,
        )
        self.customer = CustomerCompany.objects.create(
            organization=self.organization,
            name="First employee customer",
            owner=self.first_employee,
        )
        self.contact = Contact.objects.create(
            organization=self.organization,
            company=self.customer,
            full_name="First employee contact",
            owner=self.first_employee,
        )
        self.lead = Lead.objects.create(
            organization=self.organization,
            customer=self.customer,
            contact=self.contact,
            title="First employee lead",
            assigned_to=self.first_employee,
        )
        self.task = Activity.objects.create(
            organization=self.organization,
            lead=self.lead,
            activity_type=Activity.Type.TASK,
            subject="First employee task",
            assigned_to=self.first_employee,
        )
        self.quotation = Quotation.objects.create(
            organization=self.organization,
            number="QT-OWN-1",
            customer=self.customer,
            lead=self.lead,
            assigned_to=self.first_employee,
            created_by=self.first_employee,
        )
        self.order = SalesOrder.objects.create(
            organization=self.organization,
            number="SO-OWN-1",
            customer=self.customer,
            quotation=self.quotation,
            order_date=date.today(),
            assigned_to=self.first_employee,
            created_by=self.first_employee,
        )
        self.plan = PaymentPlan.objects.create(
            organization=self.organization,
            order=self.order,
            due_date=date.today() + timedelta(days=7),
            amount=Decimal("100"),
        )
        self.payment = Payment.objects.create(
            organization=self.organization,
            order=self.order,
            plan=self.plan,
            amount=Decimal("25"),
            created_by=self.first_employee,
        )

    def mutation_form_urls(self):
        return (
            reverse("customers:update", args=[self.customer.public_id]),
            reverse("customers:contact-update", args=[self.contact.public_id]),
            reverse("crm:update", args=[self.lead.public_id]),
            reverse("sales:update", args=[self.quotation.public_id]),
            reverse("sales:order-update", args=[self.order.public_id]),
            reverse("sales:payment-plan-update", args=[self.plan.public_id]),
            reverse("sales:payment-update", args=[self.payment.public_id]),
        )

    def test_employee_cannot_edit_another_employees_records(self):
        self.client.force_login(self.second_employee)

        for url in self.mutation_form_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

        self.assertEqual(
            self.client.get(
                reverse("sales:create-from-lead", args=[self.lead.public_id])
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                reverse("communications:email-compose"),
                {"quotation": self.quotation.public_id},
            ).status_code,
            403,
        )

    def test_mutation_controls_are_hidden_for_another_employees_records(self):
        self.client.force_login(self.second_employee)

        customer_response = self.client.get(
            reverse("customers:detail", args=[self.customer.public_id])
        )
        lead_response = self.client.get(
            reverse("crm:detail", args=[self.lead.public_id])
        )
        quotation_response = self.client.get(
            reverse("sales:detail", args=[self.quotation.public_id])
        )
        order_response = self.client.get(
            reverse("sales:order-detail", args=[self.order.public_id])
        )

        self.assertNotContains(
            customer_response,
            reverse("customers:update", args=[self.customer.public_id]),
        )
        self.assertNotContains(
            lead_response,
            reverse("crm:update", args=[self.lead.public_id]),
        )
        self.assertNotContains(
            quotation_response,
            reverse("sales:update", args=[self.quotation.public_id]),
        )
        self.assertNotContains(
            order_response,
            reverse("sales:order-update", args=[self.order.public_id]),
        )

    def test_employee_can_edit_own_records(self):
        self.client.force_login(self.first_employee)

        for url in self.mutation_form_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_designated_employee_can_edit_all_records(self):
        self.second_membership.can_manage_all_records = True
        self.second_membership.save(
            update_fields=["can_manage_all_records", "updated_at"]
        )
        self.client.force_login(self.second_employee)

        for url in self.mutation_form_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_api_rejects_updates_to_another_employees_records(self):
        self.client.force_login(self.second_employee)
        endpoints = (
            f"/api/v1/customers/companies/{self.customer.pk}/",
            f"/api/v1/crm/leads/{self.lead.pk}/",
            f"/api/v1/sales/quotations/{self.quotation.pk}/",
            f"/api/v1/sales/orders/{self.order.pk}/",
        )

        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                response = self.client.patch(
                    endpoint,
                    data="{}",
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 403)

    def test_api_assigns_new_records_to_the_creator_by_default(self):
        self.client.force_login(self.second_employee)

        response = self.client.post(
            "/api/v1/customers/companies/",
            {
                "name": "Second employee customer",
                "owner": self.first_employee.pk,
            },
        )

        self.assertEqual(response.status_code, 201)
        created = CustomerCompany.objects.get(name="Second employee customer")
        self.assertEqual(created.owner, self.second_employee)
