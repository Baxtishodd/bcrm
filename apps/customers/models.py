from django.conf import settings
from django.db import models

from apps.common.models import OrganizationScopedModel


class CustomerCompany(OrganizationScopedModel):
    class Type(models.TextChoices):
        LOCAL = "local", "Mahalliy"
        RETAIL = "retail", "Chakana"
        EXPORT = "export", "Eksport"
        DEALER = "dealer", "Diler"

    class RelationshipStatus(models.TextChoices):
        WORKING = "working", "Hamkorlik qilinmoqda"
        POTENTIAL = "potential", "Potensial mijoz"
        OFFER_SENT = "offer_sent", "Taklif yuborilgan"
        REJECTED = "rejected", "Rad etilgan"

    class BusinessDirection(models.TextChoices):
        KNIT_FABRIC = "knit_fabric", "Trikotaj mato"
        WEAVING = "weaving", "To'quvchilik"
        YARN = "yarn", "Ip-kalava"
        SEWING = "sewing", "Tikuvchilik va xizmatlar"
        OTHER = "other", "Boshqa"

    name = models.CharField(max_length=200)
    customer_type = models.CharField(
        max_length=20,
        choices=Type.choices,
        default=Type.LOCAL,
    )
    relationship_status = models.CharField(
        max_length=20,
        choices=RelationshipStatus.choices,
        default=RelationshipStatus.POTENTIAL,
    )
    business_direction = models.CharField(
        max_length=20,
        choices=BusinessDirection.choices,
        default=BusinessDirection.OTHER,
    )
    product_interest = models.TextField(blank=True)
    purchase_purpose = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    tax_id = models.CharField(max_length=30, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    telegram = models.CharField(max_length=80, blank=True)
    whatsapp = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    country = models.CharField(max_length=80, blank=True)
    city = models.CharField(max_length=80, blank=True)
    address = models.TextField(blank=True)
    credit_limit = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"],
                name="uniq_customer_name_per_org",
            )
        ]

    def __str__(self):
        return self.name


class Contact(OrganizationScopedModel):
    company = models.ForeignKey(
        CustomerCompany,
        on_delete=models.CASCADE,
        related_name="contacts",
    )
    full_name = models.CharField(max_length=160)
    position = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    telegram = models.CharField(max_length=80, blank=True)
    whatsapp = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name
