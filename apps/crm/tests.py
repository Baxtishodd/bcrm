import json
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.customers.models import Contact, CustomerCompany
from apps.organizations.models import Membership, Organization

from .forms import LeadForm
from .models import Activity, Lead, PipelineStage


class DemoLeadSeedTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Bunyodkor Demo",
            slug="bunyodkor-demo",
        )
        self.user = User.objects.create_user(
            email="demo-sales@example.com",
            password="test-password",
        )
        Membership.objects.create(
            organization=self.organization,
            user=self.user,
            role=Membership.Role.SALES,
        )
        for direction, label in CustomerCompany.BusinessDirection.choices:
            CustomerCompany.objects.create(
                organization=self.organization,
                name=f"{label} demo mijoz",
                business_direction=direction,
            )

    def test_seed_creates_all_directions_without_duplicates(self):
        output = StringIO()
        for _ in range(2):
            call_command(
                "seed_demo_leads",
                organization=self.organization.slug,
                stdout=output,
            )

        self.assertEqual(Lead.objects.filter(organization=self.organization).count(), 10)
        self.assertEqual(
            set(
                Lead.objects.filter(organization=self.organization).values_list(
                    "business_direction",
                    flat=True,
                )
            ),
            {value for value, _ in Lead.BusinessDirection.choices},
        )
        self.assertEqual(
            Activity.objects.filter(organization=self.organization).count(),
            10,
        )


class LeadTenantTests(TestCase):
    def test_for_user_only_returns_own_organization_records(self):
        user = User.objects.create_user(
            email="manager@example.com",
            password="test-password",
        )
        own_org = Organization.objects.create(name="Own Textile", slug="own")
        other_org = Organization.objects.create(name="Other Textile", slug="other")
        Membership.objects.create(
            organization=own_org,
            user=user,
            role=Membership.Role.SALES,
        )
        own_lead = Lead.objects.create(
            organization=own_org,
            title="Own lead",
        )
        Lead.objects.create(organization=other_org, title="Other lead")

        self.assertQuerySetEqual(Lead.objects.for_user(user), [own_lead])


class TaskFrontendTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="tasks@example.com",
            password="test-password",
        )
        self.organization = Organization.objects.create(name="Tasks Textile", slug="tasks")
        Membership.objects.create(
            organization=self.organization,
            user=self.user,
            role=Membership.Role.SALES,
        )
        self.customer = CustomerCompany.objects.create(
            organization=self.organization,
            name="Task customer",
        )
        self.contact = Contact.objects.create(
            organization=self.organization,
            company=self.customer,
            full_name="Task contact",
        )
        self.open_stage = PipelineStage.objects.create(
            organization=self.organization,
            name="Muzokara",
            position=10,
            probability=50,
        )
        self.won_stage = PipelineStage.objects.create(
            organization=self.organization,
            name="Yutildi",
            position=20,
            probability=100,
            is_closed=True,
        )
        self.lost_stage = PipelineStage.objects.create(
            organization=self.organization,
            name="Yutqazildi",
            position=30,
            probability=0,
            is_closed=True,
        )
        self.lead = Lead.objects.create(
            organization=self.organization,
            title="New order",
            customer=self.customer,
            stage=self.open_stage,
            assigned_to=self.user,
        )
        self.task = Activity.objects.create(
            organization=self.organization,
            lead=self.lead,
            activity_type=Activity.Type.TASK,
            subject="Call customer",
            due_at=timezone.now(),
            assigned_to=self.user,
        )
        self.client.force_login(self.user)

    def test_task_can_be_completed(self):
        response = self.client.post(reverse("tasks:complete", args=[self.task.public_id]))

        self.task.refresh_from_db()
        self.assertRedirects(response, reverse("tasks:list"))
        self.assertIsNotNone(self.task.completed_at)

    def test_task_list_is_tenant_scoped(self):
        other = Organization.objects.create(name="Other Tasks", slug="other-tasks")
        other_lead = Lead.objects.create(organization=other, title="Hidden lead")
        Activity.objects.create(
            organization=other,
            lead=other_lead,
            activity_type=Activity.Type.TASK,
            subject="Hidden task",
        )

        response = self.client.get(reverse("tasks:list"))

        self.assertContains(response, "Call customer")
        self.assertNotContains(response, "Hidden task")

    def test_task_list_renders_task_without_lead_or_customer(self):
        Activity.objects.create(
            organization=self.organization,
            activity_type=Activity.Type.TASK,
            subject="Internal reminder",
        )

        response = self.client.get(reverse("tasks:list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Internal reminder")

    def test_task_search_includes_direct_customer(self):
        Activity.objects.create(
            organization=self.organization,
            customer=self.customer,
            activity_type=Activity.Type.TASK,
            subject="Direct customer task",
        )

        response = self.client.get(
            reverse("tasks:list"),
            {"q": "Task customer"},
        )

        self.assertContains(response, "Direct customer task")

    def test_lead_detail_has_logical_back_navigation(self):
        response = self.client.get(reverse("crm:detail", args=[self.lead.public_id]))

        self.assertContains(response, reverse("crm:list"))
        self.assertContains(response, "Leadlarga qaytish")
        self.assertContains(response, "Leadlar")

    def test_lead_create_form_has_back_navigation(self):
        response = self.client.get(reverse("crm:create"))

        self.assertContains(response, reverse("crm:list"))
        self.assertContains(response, "Ortga")

    def test_lead_form_has_searchable_dependent_contact_select(self):
        response = self.client.get(reverse("crm:create"))
        form = response.context["form"]
        contact_html = str(form["contact"])

        self.assertEqual(form.fields["title"].label, "Lead nomi")
        self.assertIn("data-smart-select", form.fields["customer"].widget.attrs)
        self.assertEqual(
            form.fields["contact"].widget.attrs["data-smart-select-depends-on"],
            "customer",
        )
        self.assertIn(f'data-parent-value="{self.customer.pk}"', contact_html)
        self.assertContains(response, "js/smart-select.js")

    def test_lead_form_rejects_contact_from_another_customer(self):
        other_customer = CustomerCompany.objects.create(
            organization=self.organization,
            name="Other customer",
        )
        other_contact = Contact.objects.create(
            organization=self.organization,
            company=other_customer,
            full_name="Other contact",
        )
        form = LeadForm(
            data={
                "title": "Dependent contact test",
                "business_direction": Lead.BusinessDirection.OTHER,
                "customer": self.customer.pk,
                "contact": other_contact.pk,
                "stage": self.open_stage.pk,
                "status": Lead.Status.NEW,
                "priority": Lead.Priority.MEDIUM,
                "source": "",
                "estimated_value": "0",
                "currency": "UZS",
                "lost_reason": "",
                "description": "",
            },
            organization=self.organization,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("contact", form.errors)

    def test_lead_create_accepts_stage_from_current_organization(self):
        response = self.client.post(
            reverse("crm:create"),
            {
                "title": "Stage validation regression",
                "business_direction": Lead.BusinessDirection.KNIT_FABRIC,
                "customer": self.customer.pk,
                "contact": self.contact.pk,
                "stage": self.open_stage.pk,
                "status": Lead.Status.IN_PROGRESS,
                "priority": Lead.Priority.MEDIUM,
                "source": "E2E test",
                "estimated_value": "2900",
                "currency": "USD",
                "assigned_to": self.user.pk,
                "lost_reason": "",
                "description": "Regression test",
            },
        )

        lead = Lead.objects.get(title="Stage validation regression")
        self.assertRedirects(response, reverse("crm:detail", args=[lead.public_id]))
        self.assertEqual(lead.organization, self.organization)
        self.assertEqual(lead.stage, self.open_stage)

    def test_lead_api_rejects_cross_tenant_relations(self):
        other_organization = Organization.objects.create(
            name="Other organization",
            slug="other-api-organization",
        )
        other_customer = CustomerCompany.objects.create(
            organization=other_organization,
            name="Hidden API customer",
        )
        other_stage = PipelineStage.objects.create(
            organization=other_organization,
            name="Hidden API stage",
        )

        response = self.client.post(
            "/api/v1/crm/leads/",
            data=json.dumps(
                {
                    "title": "Cross tenant API attempt",
                    "business_direction": Lead.BusinessDirection.KNIT_FABRIC,
                    "customer": other_customer.pk,
                    "stage": other_stage.pk,
                    "status": Lead.Status.NEW,
                    "priority": Lead.Priority.MEDIUM,
                    "estimated_value": "100",
                    "currency": "USD",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Lead.objects.filter(title="Cross tenant API attempt").exists())

    def test_anonymous_user_cannot_access_leads_api(self):
        self.client.logout()

        response = self.client.get("/api/v1/crm/leads/")

        self.assertIn(response.status_code, {401, 403})

    def test_lead_list_renders_reusable_kanban_component(self):
        response = self.client.get(reverse("crm:list"))

        self.assertContains(response, "data-kanban")
        self.assertContains(response, "data-kanban-dropzone")
        self.assertContains(response, "data-kanban-update-url")
        self.assertContains(response, "js/kanban.js")
        self.assertIn("no-cache", response.headers["Cache-Control"])

    def test_lead_status_can_be_updated_from_kanban(self):
        response = self.client.post(
            reverse("crm:status-update", args=[self.lead.public_id]),
            data='{"status":"in_progress","position":0}',
            content_type="application/json",
        )

        self.lead.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], Lead.Status.IN_PROGRESS)
        self.assertEqual(self.lead.status, Lead.Status.IN_PROGRESS)

    def test_kanban_rejects_invalid_status(self):
        response = self.client.post(
            reverse("crm:status-update", args=[self.lead.public_id]),
            data='{"status":"not-a-status","position":0}',
            content_type="application/json",
        )

        self.lead.refresh_from_db()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.lead.status, Lead.Status.NEW)

    def test_kanban_cannot_update_another_organizations_lead(self):
        other = Organization.objects.create(name="Other CRM", slug="other-crm")
        other_lead = Lead.objects.create(organization=other, title="Hidden lead")

        response = self.client.post(
            reverse("crm:status-update", args=[other_lead.public_id]),
            data='{"status":"won","position":0}',
            content_type="application/json",
        )

        other_lead.refresh_from_db()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(other_lead.status, Lead.Status.NEW)

    def test_kanban_position_is_persisted_within_target_column(self):
        first_won = Lead.objects.create(
            organization=self.organization,
            title="First won",
            status=Lead.Status.WON,
            kanban_position=0,
        )
        second_won = Lead.objects.create(
            organization=self.organization,
            title="Second won",
            status=Lead.Status.WON,
            kanban_position=1,
        )

        response = self.client.post(
            reverse("crm:status-update", args=[self.lead.public_id]),
            data='{"status":"won","position":1}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        ordered_ids = list(
            Lead.objects.filter(
                organization=self.organization,
                status=Lead.Status.WON,
            )
            .order_by("kanban_position", "-created_at")
            .values_list("pk", flat=True)
        )
        self.assertEqual(ordered_ids, [first_won.pk, self.lead.pk, second_won.pk])

    def test_kanban_rejects_missing_position(self):
        response = self.client.post(
            reverse("crm:status-update", args=[self.lead.public_id]),
            data='{"status":"won"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_kanban_requires_reason_and_syncs_lost_stage(self):
        rejected = self.client.post(
            reverse("crm:status-update", args=[self.lead.public_id]),
            data='{"status":"lost","position":0}',
            content_type="application/json",
        )

        self.assertEqual(rejected.status_code, 400)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, Lead.Status.NEW)

        accepted = self.client.post(
            reverse("crm:status-update", args=[self.lead.public_id]),
            data=('{"status":"lost","position":0,"lost_reason":"Yetkazish muddati mos kelmadi"}'),
            content_type="application/json",
        )

        self.assertEqual(accepted.status_code, 200)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, Lead.Status.LOST)
        self.assertEqual(self.lead.stage, self.lost_stage)
        self.assertEqual(self.lead.lost_reason, "Yetkazish muddati mos kelmadi")

        reordered = self.client.post(
            reverse("crm:status-update", args=[self.lead.public_id]),
            data='{"status":"lost","position":0}',
            content_type="application/json",
        )
        self.assertEqual(reordered.status_code, 200)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.lost_reason, "Yetkazish muddati mos kelmadi")

    def test_kanban_syncs_won_stage_and_clears_lost_reason(self):
        self.lead.status = Lead.Status.LOST
        self.lead.stage = self.lost_stage
        self.lead.lost_reason = "Old reason"
        self.lead.save()

        response = self.client.post(
            reverse("crm:status-update", args=[self.lead.public_id]),
            data='{"status":"won","position":0}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, Lead.Status.WON)
        self.assertEqual(self.lead.stage, self.won_stage)
        self.assertEqual(self.lead.lost_reason, "")

    def test_won_status_requires_customer(self):
        lead = Lead.objects.create(
            organization=self.organization,
            title="Customer missing",
            stage=self.open_stage,
            assigned_to=self.user,
        )

        response = self.client.post(
            reverse("crm:status-update", args=[lead.public_id]),
            data='{"status":"won","position":0}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        lead.refresh_from_db()
        self.assertEqual(lead.status, Lead.Status.NEW)

    def test_form_rejects_open_stage_with_terminal_status(self):
        form = LeadForm(
            data={
                "title": self.lead.title,
                "business_direction": Lead.BusinessDirection.OTHER,
                "customer": self.customer.pk,
                "stage": self.open_stage.pk,
                "status": Lead.Status.WON,
                "priority": Lead.Priority.MEDIUM,
                "source": "",
                "estimated_value": "0",
                "currency": "UZS",
                "lost_reason": "",
                "description": "",
            },
            instance=self.lead,
            organization=self.organization,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("stage", form.errors)
