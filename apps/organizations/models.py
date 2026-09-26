from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel


class Organization(TimeStampedModel):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=80, unique=True)
    tax_id = models.CharField(max_length=30, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Branch(TimeStampedModel):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="branches",
    )
    name = models.CharField(max_length=150)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"],
                name="uniq_branch_name",
            )
        ]

    def __str__(self):
        return f"{self.organization} — {self.name}"


class Membership(TimeStampedModel):
    class Role(models.TextChoices):
        OWNER = "owner", "Egasi"
        DIRECTOR = "director", "Direktor"
        SALES = "sales", "Savdo menejeri"
        TECHNOLOGIST = "technologist", "Texnolog"
        PRODUCTION = "production", "Ishlab chiqarish menejeri"
        WAREHOUSE = "warehouse", "Omborchi"
        ACCOUNTANT = "accountant", "Buxgalter"
        VIEWER = "viewer", "Kuzatuvchi"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    branch = models.ForeignKey(
        Branch,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    role = models.CharField(max_length=30, choices=Role.choices)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "user"],
                name="uniq_org_user",
            )
        ]

