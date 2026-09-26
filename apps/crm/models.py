from django.conf import settings
from django.db import models

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
    currency = models.CharField(max_length=3, default="UZS")
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
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["organization", "assigned_to"]),
        ]

    def __str__(self):
        return self.title


class Activity(OrganizationScopedModel):
    class Type(models.TextChoices):
        CALL = "call", "Qo'ng'iroq"
        MEETING = "meeting", "Uchrashuv"
        EMAIL = "email", "Email"
        TASK = "task", "Vazifa"
        NOTE = "note", "Izoh"

    lead = models.ForeignKey(
        Lead,
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

