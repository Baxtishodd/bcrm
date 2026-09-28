from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.models import OrganizationScopedModel


class Quotation(OrganizationScopedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Qoralama"
        SENT = "sent", "Yuborildi"
        ACCEPTED = "accepted", "Qabul qilindi"
        REJECTED = "rejected", "Rad etildi"
        EXPIRED = "expired", "Muddati tugadi"

    number = models.CharField(max_length=40)
    customer = models.ForeignKey(
        "customers.CustomerCompany",
        on_delete=models.PROTECT,
    )
    lead = models.ForeignKey(
        "crm.Lead",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    currency = models.CharField(max_length=3, default="UZS")
    valid_until = models.DateField(null=True, blank=True)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    delivery_terms = models.CharField(max_length=255, blank=True)
    payment_terms = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "number"],
                name="uniq_quotation_number",
            )
        ]

    def __str__(self):
        return self.number

    @property
    def subtotal(self):
        return sum(
            line.quantity * line.unit_price
            for line in self.lines.all()
        )

    @property
    def discount_amount(self):
        return self.subtotal * self.discount_percent / Decimal("100")

    @property
    def tax_amount(self):
        taxable = self.subtotal - self.discount_amount
        return taxable * self.tax_percent / Decimal("100")

    @property
    def total(self):
        return self.subtotal - self.discount_amount + self.tax_amount


class QuotationLine(OrganizationScopedModel):
    quotation = models.ForeignKey(
        Quotation,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT)
    description = models.CharField(max_length=255, blank=True)
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    unit_price = models.DecimalField(max_digits=18, decimal_places=2)

    @property
    def line_total(self):
        return self.quantity * self.unit_price


class QuotationDelivery(OrganizationScopedModel):
    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        TELEGRAM = "telegram", "Telegram"
        WHATSAPP = "whatsapp", "WhatsApp"
        OTHER = "other", "Boshqa"

    class Status(models.TextChoices):
        SENT = "sent", "Yuborildi"
        DELIVERED = "delivered", "Yetkazildi"
        READ = "read", "O'qildi"
        REPLIED = "replied", "Javob berdi"
        FAILED = "failed", "Yuborilmadi"

    quotation = models.ForeignKey(
        Quotation,
        on_delete=models.CASCADE,
        related_name="deliveries",
    )
    channel = models.CharField(max_length=20, choices=Channel.choices)
    recipient = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SENT,
    )
    sent_at = models.DateTimeField(default=timezone.now)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-sent_at", "-created_at"]

    def __str__(self):
        return f"{self.quotation.number} / {self.get_channel_display()}"


class SalesOrder(OrganizationScopedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Qoralama"
        CONFIRMED = "confirmed", "Tasdiqlangan"
        IN_PRODUCTION = "in_production", "Ishlab chiqarishda"
        READY = "ready", "Tayyor"
        SHIPPED = "shipped", "Jo'natildi"
        CANCELLED = "cancelled", "Bekor qilindi"

    number = models.CharField(max_length=40)
    customer = models.ForeignKey(
        "customers.CustomerCompany",
        on_delete=models.PROTECT,
    )
    quotation = models.OneToOneField(
        Quotation,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    order_date = models.DateField()
    delivery_date = models.DateField(null=True, blank=True)
    advance_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_orders",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_orders",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-order_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "number"],
                name="uniq_order_number",
            )
        ]

    def __str__(self):
        return self.number

    @property
    def total(self):
        if self.quotation_id:
            return self.quotation.total
        return sum(line.line_total for line in self.lines.all())

    @property
    def balance(self):
        return max(self.total - self.paid_amount, Decimal("0"))

    @property
    def payment_status(self):
        if self.total and self.paid_amount >= self.total:
            return "To'langan"
        if self.paid_amount > 0:
            return "Qisman to'langan"
        return "To'lanmagan"


class OrderLine(OrganizationScopedModel):
    order = models.ForeignKey(
        SalesOrder,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT)
    unit_price = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
    )
    quantity = models.DecimalField(max_digits=14, decimal_places=3, default=0)

    @property
    def line_total(self):
        return self.quantity * self.unit_price


class OrderLineVariant(OrganizationScopedModel):
    order_line = models.ForeignKey(
        OrderLine,
        on_delete=models.CASCADE,
        related_name="variant_quantities",
    )
    variant = models.ForeignKey(
        "catalog.ProductVariant",
        on_delete=models.PROTECT,
    )
    quantity = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "order_line", "variant"],
                name="uniq_order_line_variant",
            )
        ]
