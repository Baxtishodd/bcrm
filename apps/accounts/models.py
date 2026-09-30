from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.common.models import TimeStampedModel

from .crypto import decrypt_secret, encrypt_secret


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Email kiritilishi shart")
        email = self.normalize_email(email)
        user = self.model(email=email, username=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    class Language(models.TextChoices):
        UZ = "uz", "O'zbek"
        RU = "ru", "Русский"
        EN = "en", "English"

    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=30, blank=True)
    preferred_language = models.CharField(
        max_length=2,
        choices=Language.choices,
        default=Language.UZ,
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UserManager()

    def save(self, *args, **kwargs):
        self.username = self.email
        super().save(*args, **kwargs)


class MailboxAccount(TimeStampedModel):
    class Security(models.TextChoices):
        STARTTLS = "starttls", "STARTTLS"
        SSL = "ssl", "SSL/TLS"
        NONE = "none", "Shifrlanmagan"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="mailbox_accounts",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="mailbox_accounts",
    )
    email = models.EmailField()
    display_name = models.CharField(max_length=150, blank=True)
    username = models.CharField(max_length=254)
    encrypted_password = models.TextField()
    smtp_host = models.CharField(max_length=255)
    smtp_port = models.PositiveIntegerField(
        default=587,
        validators=[MinValueValidator(1), MaxValueValidator(65535)],
    )
    smtp_security = models.CharField(
        max_length=10,
        choices=Security.choices,
        default=Security.STARTTLS,
    )
    imap_host = models.CharField(max_length=255)
    imap_port = models.PositiveIntegerField(
        default=993,
        validators=[MinValueValidator(1), MaxValueValidator(65535)],
    )
    imap_security = models.CharField(
        max_length=10,
        choices=Security.choices,
        default=Security.SSL,
    )
    is_default = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    last_tested_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    smtp_is_verified = models.BooleanField(default=False)
    imap_is_verified = models.BooleanField(default=False)

    class Meta:
        ordering = ["-is_default", "email"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "user", "email"],
                name="uniq_user_mailbox_email",
            )
        ]

    def __str__(self):
        return self.email

    def set_password(self, raw_password):
        self.encrypted_password = encrypt_secret(raw_password)

    def get_password(self):
        return decrypt_secret(self.encrypted_password)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_default:
            type(self).objects.filter(
                organization=self.organization,
                user=self.user,
            ).exclude(pk=self.pk).update(is_default=False)
