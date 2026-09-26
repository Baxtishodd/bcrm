from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.organizations.models import Membership, Organization

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
                "customer_type": CustomerCompany.Type.LOCAL,
                "is_active": "on",
            },
        )

        customer = CustomerCompany.objects.get(name="Visible Customer")
        self.assertRedirects(
            response,
            reverse("customers:detail", args=[customer.public_id]),
        )
        self.assertEqual(customer.organization, self.organization)

