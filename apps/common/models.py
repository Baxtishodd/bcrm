import uuid

from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class OrganizationQuerySet(models.QuerySet):
    def for_user(self, user):
        if not user.is_authenticated:
            return self.none()
        return self.filter(
            organization__memberships__user=user,
            organization__memberships__is_active=True,
        )


class OrganizationScopedModel(TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
    )

    objects = OrganizationQuerySet.as_manager()

    class Meta:
        abstract = True


class AuditLog(TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    action = models.CharField(max_length=50)
    object_type = models.CharField(max_length=100)
    object_public_id = models.UUIDField()
    changes = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

