from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.common.choices import Currency
from apps.common.models import OrganizationScopedModel


class Quotation(OrganizationScopedModel):
    class DocumentLanguage(models.TextChoices):
        UZ = "uz", "O'zbekcha"
        RU = "ru", "Ruscha"
        EN = "en", "Inglizcha"

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
    contact = models.ForeignKey(
        "customers.Contact",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="quotations",
    )
    lead = models.ForeignKey(
        "crm.Lead",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="quotations",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        default=Currency.UZS,
    )
    valid_until = models.DateField(null=True, blank=True)
    discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    tax_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    delivery_terms = models.CharField(max_length=255, blank=True)
    payment_terms = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    document_language = models.CharField(
        max_length=2,
        choices=DocumentLanguage.choices,
        default=DocumentLanguage.UZ,
    )
    document_title = models.CharField(max_length=200, default="TIJORAT TAKLIFI")
    document_intro = models.TextField(blank=True)
    document_footer = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="created_quotations",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_quotations",
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
        return sum(line.quantity * line.unit_price for line in self.lines.all())

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
    class PriceSource(models.TextChoices):
        CATALOG = "catalog", "Mahsulot katalogi"
        PRICE_LIST = "price_list", "Price-list"
        MANUAL = "manual", "Qo'lda kiritilgan"

    quotation = models.ForeignKey(
        Quotation,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT)
    variant = models.ForeignKey(
        "catalog.ProductVariant",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    description = models.CharField(max_length=255, blank=True)
    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
    )
    unit_price = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0"))],
    )
    price_source = models.CharField(
        max_length=20,
        choices=PriceSource.choices,
        default=PriceSource.MANUAL,
    )
    source_price_list = models.ForeignKey(
        "catalog.PriceList",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="quotation_lines",
    )
    source_unit_price = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    price_override_reason = models.CharField(max_length=255, blank=True)

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
    sender = models.EmailField(blank=True)
    subject = models.CharField(max_length=255, blank=True)
    message = models.TextField(blank=True)
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
    advance_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal("0"))],
    )
    paid_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal("0"))],
    )
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
    def payment_status_code(self):
        if self.total and self.paid_amount >= self.total:
            return "paid"
        if self.paid_amount > 0:
            return "partial"
        return "unpaid"

    @property
    def payment_status(self):
        return {
            "paid": "To'langan",
            "partial": "Qisman to'langan",
            "unpaid": "To'lanmagan",
        }[self.payment_status_code]

    @property
    def currency(self):
        if self.quotation_id:
            return self.quotation.currency
        return self.organization.default_currency


class PaymentPlan(OrganizationScopedModel):
    order = models.ForeignKey(
        SalesOrder,
        on_delete=models.CASCADE,
        related_name="payment_plans",
    )
    due_date = models.DateField()
    amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    notes = models.CharField(max_length=255, blank=True)
    is_cancelled = models.BooleanField(default=False)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cancelled_payment_plans",
    )
    cancellation_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["due_date", "created_at"]
        indexes = [
            models.Index(
                fields=["organization", "due_date"],
                name="sales_plan_org_due_idx",
            )
        ]

    def __str__(self):
        return f"{self.order.number} — {self.due_date}"

    @property
    def received_amount(self):
        return sum(
            (
                payment.amount
                for payment in self.payments.all()
                if not payment.is_cancelled
            ),
            Decimal("0"),
        )

    @property
    def balance(self):
        return max(self.amount - self.received_amount, Decimal("0"))

    @property
    def payment_status_code(self):
        if self.is_cancelled:
            return "cancelled"
        if self.received_amount >= self.amount:
            return "paid"
        if self.received_amount > 0:
            return "partial"
        if self.due_date < timezone.localdate():
            return "overdue"
        return "planned"

    @property
    def payment_status(self):
        return {
            "cancelled": "Bekor qilingan",
            "paid": "To'langan",
            "partial": "Qisman to'langan",
            "overdue": "Muddati o'tgan",
            "planned": "Rejada",
        }[self.payment_status_code]

    def clean(self):
        super().clean()
        if self.order_id and self.order.organization_id != self.organization_id:
            raise ValidationError({"order": "To'lov rejasi boshqa tashkilotga tegishli."})


class Payment(OrganizationScopedModel):
    class Method(models.TextChoices):
        BANK = "bank", "Bank o'tkazmasi"
        CASH = "cash", "Naqd"
        CARD = "card", "Karta"
        OTHER = "other", "Boshqa"

    order = models.ForeignKey(
        SalesOrder,
        on_delete=models.CASCADE,
        related_name="payments",
    )
    plan = models.ForeignKey(
        PaymentPlan,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="payments",
    )
    received_on = models.DateField(default=timezone.localdate)
    amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    method = models.CharField(max_length=20, choices=Method.choices, default=Method.BANK)
    reference = models.CharField(max_length=100, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    is_cancelled = models.BooleanField(default=False)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cancelled_payments",
    )
    cancellation_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-received_on", "-created_at"]
        indexes = [
            models.Index(
                fields=["organization", "received_on"],
                name="sales_pay_org_date_idx",
            )
        ]

    def __str__(self):
        return f"{self.order.number} — {self.amount}"

    def clean(self):
        super().clean()
        errors = {}
        if self.order_id and self.order.organization_id != self.organization_id:
            errors["order"] = "To'lov boshqa tashkilotga tegishli."
        if self.plan_id and self.order_id and self.plan.order_id != self.order_id:
            errors["plan"] = "Reja ushbu buyurtmaga tegishli emas."
        if (
            self.plan_id
            and self.organization_id
            and self.plan.organization_id != self.organization_id
        ):
            errors["plan"] = "Reja boshqa tashkilotga tegishli."
        if errors:
            raise ValidationError(errors)


class OrderLine(OrganizationScopedModel):
    order = models.ForeignKey(
        SalesOrder,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT)
    unit_price = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=0,
        validators=[MinValueValidator(Decimal("0"))],
    )
    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=0,
        validators=[MinValueValidator(Decimal("0.001"))],
    )

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
