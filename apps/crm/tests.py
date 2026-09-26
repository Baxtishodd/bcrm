from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations.models import Membership, Organization

from .models import Activity, Lead


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
