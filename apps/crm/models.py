from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.common.choices import Currency
from apps.common.models import OrganizationScopedModel


class PipelineStage(OrganizationScopedModel):
    name = models.CharField(max_length=100)
    position = models.PositiveSmallIntegerField(default=0)
    probability = models.PositiveSmallIntegerField(default=0)
    color = models.CharField(max_length=7, default="#64748b")
    is_closed = models.BooleanField(default=False)

    class Meta:
        ordering = ["position", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"],
                name="uniq_pipeline_stage",
            )
        ]

    def __str__(self):
        return self.name


class Lead(OrganizationScopedModel):
    class BusinessDirection(models.TextChoices):
        KNIT_FABRIC = "knit_fabric", "Trikotaj mato"
        WEAVING = "weaving", "To'quvchilik"
        YARN = "yarn", "Ip-kalava"
        SEWING = "sewing", "Tikuvchilik va xizmatlar"
        OTHER = "other", "Boshqa"

    class Status(models.TextChoices):
        NEW = "new", "Yangi"
        IN_PROGRESS = "in_progress", "Jarayonda"
        WON = "won", "Yutildi"
        LOST = "lost", "Yutqazildi"

    class Priority(models.TextChoices):
        LOW = "low", "Past"
        MEDIUM = "medium", "O'rta"
        HIGH = "high", "Yuqori"

    title = models.CharField(max_length=220)
    business_direction = models.CharField(
        max_length=20,
        choices=BusinessDirection.choices,
        default=BusinessDirection.OTHER,
    )
    customer = models.ForeignKey(
        "customers.CustomerCompany",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="leads",
    )
    contact = models.ForeignKey(
        "customers.Contact",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    stage = models.ForeignKey(
        PipelineStage,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
    )
    kanban_position = models.PositiveIntegerField(default=0)
    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.MEDIUM,
    )
    source = models.CharField(max_length=100, blank=True)
    estimated_value = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
    )
    currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        default=Currency.UZS,
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_leads",
    )
    next_action_at = models.DateTimeField(null=True, blank=True)
    lost_reason = models.TextField(blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["kanban_position", "-created_at"]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["organization", "assigned_to"]),
        ]

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        errors = {}

        if self.stage_id:
            if self.stage.organization_id != self.organization_id:
                errors["stage"] = "Bosqich ushbu tashkilotga tegishli emas."
            elif self.stage.is_closed:
                expected_status = None
                if self.stage.probability == 100:
                    expected_status = self.Status.WON
                elif self.stage.probability == 0:
                    expected_status = self.Status.LOST
                if expected_status is None:
                    errors["stage"] = (
                        "Yopiq bosqich ehtimoli yutilgan uchun 100%, "
                        "yutqazilgan uchun 0% bo'lishi kerak."
                    )
                elif self.status != expected_status:
                    errors["status"] = (
                        f"«{self.stage.name}» bosqichi faqat "
                        f"«{self.Status(expected_status).label}» holatiga mos."
                    )
            elif self.status in {self.Status.WON, self.Status.LOST}:
                errors["stage"] = "Yakuniy holat uchun yopiq bosqichni tanlang."

        if self.status == self.Status.LOST and not self.lost_reason.strip():
            errors["lost_reason"] = "Yutqazilgan Lead uchun sababni kiriting."
        if self.status != self.Status.LOST:
            self.lost_reason = ""

        if self.status == self.Status.WON and not self.customer_id:
            errors["customer"] = "Yutilgan Lead uchun mijozni biriktiring."

        if (
            self.pk
            and self.status != self.Status.WON
            and self.quotations.filter(salesorder__isnull=False).exists()
        ):
            errors["status"] = "Buyurtmasi mavjud Lead faqat «Yutildi» holatida bo'ladi."

        if errors:
            raise ValidationError(errors)


class Activity(OrganizationScopedModel):
    class Type(models.TextChoices):
        CALL = "call", "Qo'ng'iroq"
        MEETING = "meeting", "Uchrashuv"
        EMAIL = "email", "Email"
        TASK = "task", "Vazifa"
        NOTE = "note", "Izoh"

    lead = models.ForeignKey(
        Lead,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="activities",
    )
    customer = models.ForeignKey(
        "customers.CustomerCompany",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="activities",
    )
    activity_type = models.CharField(max_length=20, choices=Type.choices)
    subject = models.CharField(max_length=220)
    details = models.TextField(blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        ordering = ["completed_at", "due_at", "-created_at"]
