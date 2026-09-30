import decimal
import uuid

import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("organizations", "0004_standardize_currency"),
        ("sales", "0009_quotationdelivery_sender"),
    ]

    operations = [
        migrations.CreateModel(
            name="PaymentPlan",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("due_date", models.DateField()),
                (
                    "amount",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=18,
                        validators=[
                            django.core.validators.MinValueValidator(decimal.Decimal("0.01"))
                        ],
                    ),
                ),
                ("notes", models.CharField(blank=True, max_length=255)),
                (
                    "order",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payment_plans",
                        to="sales.salesorder",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="organizations.organization",
                    ),
                ),
            ],
            options={
                "ordering": ["due_date", "created_at"],
                "indexes": [
                    models.Index(
                        fields=["organization", "due_date"],
                        name="sales_plan_org_due_idx",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="Payment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("received_on", models.DateField(default=django.utils.timezone.localdate)),
                (
                    "amount",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=18,
                        validators=[
                            django.core.validators.MinValueValidator(decimal.Decimal("0.01"))
                        ],
                    ),
                ),
                (
                    "method",
                    models.CharField(
                        choices=[
                            ("bank", "Bank o'tkazmasi"),
                            ("cash", "Naqd"),
                            ("card", "Karta"),
                            ("other", "Boshqa"),
                        ],
                        default="bank",
                        max_length=20,
                    ),
                ),
                ("reference", models.CharField(blank=True, max_length=100)),
                ("notes", models.CharField(blank=True, max_length=255)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "order",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payments",
                        to="sales.salesorder",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="organizations.organization",
                    ),
                ),
                (
                    "plan",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="payments",
                        to="sales.paymentplan",
                    ),
                ),
            ],
            options={
                "ordering": ["-received_on", "-created_at"],
                "indexes": [
                    models.Index(
                        fields=["organization", "received_on"],
                        name="sales_pay_org_date_idx",
                    )
                ],
            },
        ),
    ]
