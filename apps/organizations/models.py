from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.common.choices import Currency
from apps.common.images import OptimizedImageField
from apps.common.models import TimeStampedModel


class Organization(TimeStampedModel):
    name = models.CharField(max_length=200)
    legal_name = models.CharField(max_length=250, blank=True)
    short_name = models.CharField(max_length=100, blank=True)
    slug = models.SlugField(max_length=80, unique=True)
    tax_id = models.CharField(max_length=30, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    legal_address = models.TextField(blank=True)
    production_address = models.TextField(blank=True)
    bank_name = models.CharField(max_length=200, blank=True)
    bank_account = models.CharField(max_length=50, blank=True)
    bank_code = models.CharField(max_length=30, blank=True)
    director_name = models.CharField(max_length=150, blank=True)
    logo = OptimizedImageField(blank=True)
    sidebar_logo = OptimizedImageField(blank=True)
    signature_image = OptimizedImageField(blank=True)
    stamp_image = OptimizedImageField(blank=True)
    default_currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        default=Currency.USD,
    )
    default_incoterm = models.CharField(max_length=40, blank=True)
    default_delivery_terms = models.TextField(blank=True)
    default_payment_terms = models.TextField(blank=True)
    quotation_number_prefix = models.CharField(max_length=12, default="QT")
    order_number_prefix = models.CharField(max_length=12, default="SO")
    quotation_validity_days = models.PositiveSmallIntegerField(
        default=14,
        validators=[MinValueValidator(1), MaxValueValidator(365)],
    )
    document_footer = models.TextField(blank=True)
    email_sender_name = models.CharField(max_length=150, blank=True)
    telegram_username = models.CharField(max_length=100, blank=True)
    whatsapp_phone = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def document_name(self):
        return self.legal_name or self.name


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


class OrganizationRole(TimeStampedModel):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="custom_roles",
    )
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=250, blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"],
                name="uniq_organization_role_name",
            )
        ]

    def __str__(self):
        return self.name


class RolePermission(TimeStampedModel):
    class Module(models.TextChoices):
        ORGANIZATION = "organization", "Tashkilot va xodimlar"
        CUSTOMERS = "customers", "Mijozlar va kontaktlar"
        LEADS = "leads", "Leadlar"
        TASKS = "tasks", "Vazifalar"
        CATALOG = "catalog", "Mahsulotlar"
        SALES = "sales", "Savdo"
        REPORTS = "reports", "Hisobotlar"
        MAILBOX = "mailbox", "Mijozlar xabarlari"

    class Action(models.TextChoices):
        VIEW = "view", "Ko‘rish"
        CREATE = "create", "Yaratish"
        UPDATE = "update", "Tahrirlash"
        DELETE = "delete", "O‘chirish"

    role = models.ForeignKey(
        OrganizationRole,
        on_delete=models.CASCADE,
        related_name="permission_entries",
    )
    module = models.CharField(max_length=30, choices=Module.choices)
    action = models.CharField(max_length=20, choices=Action.choices)

    class Meta:
        ordering = ["module", "action"]
        constraints = [
            models.UniqueConstraint(
                fields=["role", "module", "action"],
                name="uniq_role_module_action",
            )
        ]

    def __str__(self):
        return f"{self.role}: {self.module}.{self.action}"


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
    custom_role = models.ForeignKey(
        OrganizationRole,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="memberships",
    )
    can_manage_all_records = models.BooleanField(
        default=False,
        help_text=(
            "Xodimga boshqa xodimlarga biriktirilgan mijoz, kontakt, lead, "
            "vazifa va savdo yozuvlarini o'zgartirish huquqini beradi."
        ),
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "user"],
                name="uniq_org_user",
            )
        ]

    @property
    def role_name(self):
        if self.custom_role_id:
            return self.custom_role.name
        return self.get_role_display()

    def clean(self):
        super().clean()
        if (
            self.custom_role_id
            and self.custom_role.organization_id != self.organization_id
        ):
            raise ValidationError(
                {"custom_role": "Rol xodim bilan bir tashkilotga tegishli bo‘lishi kerak."}
            )
