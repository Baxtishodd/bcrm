from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.customers.models import CustomerCompany
from apps.organizations.models import Membership, Organization

from .models import Activity, Lead


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
        self.lead = Lead.objects.create(organization=self.organization, title="New order")
        self.task = Activity.objects.create(
            organization=self.organization,
            lead=self.lead,
            activity_type=Activity.Type.TASK,
            subject="Call customer",
            due_at=timezone.now(),
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

    def test_lead_detail_has_logical_back_navigation(self):
        response = self.client.get(reverse("crm:detail", args=[self.lead.public_id]))

        self.assertContains(response, reverse("crm:list"))
        self.assertContains(response, "Leadlarga qaytish")
        self.assertContains(response, "Leadlar")

    def test_lead_create_form_has_back_navigation(self):
        response = self.client.get(reverse("crm:create"))

        self.assertContains(response, reverse("crm:list"))
        self.assertContains(response, "Ortga")

    def test_lead_list_renders_reusable_kanban_component(self):
        response = self.client.get(reverse("crm:list"))

        self.assertContains(response, "data-kanban")
        self.assertContains(response, "data-kanban-dropzone")
        self.assertContains(response, "data-kanban-update-url")
        self.assertContains(response, "js/kanban.js")

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
