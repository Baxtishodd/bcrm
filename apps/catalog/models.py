from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.common.choices import Currency
from apps.common.images import OptimizedImageField
from apps.common.models import OrganizationScopedModel


class Fabric(OrganizationScopedModel):
    name = models.CharField(max_length=150)
    composition = models.CharField(max_length=200, blank=True)
    gsm = models.PositiveIntegerField(null=True, blank=True)
    width_cm = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Color(OrganizationScopedModel):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=40, blank=True)
    hex_value = models.CharField(max_length=7, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Size(OrganizationScopedModel):
    name = models.CharField(max_length=40)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "name"]

    def __str__(self):
        return self.name


class Product(OrganizationScopedModel):
    class Category(models.TextChoices):
        KNITTED_FABRIC = "knitted_fabric", "Trikotaj mato"
        WOVEN_FABRIC = "woven_fabric", "To'quv mato"
        YARN = "yarn", "Ip-kalava"
        APPAREL = "apparel", "Tayyor kiyim"
        OTHER = "other", "Boshqa"

    class Unit(models.TextChoices):
        PIECE = "pcs", "Dona"
        KILOGRAM = "kg", "Kilogram"
        METER = "m", "Metr"

    class Availability(models.TextChoices):
        STOCK = "stock", "Omborda"
        MADE_TO_ORDER = "made_to_order", "Buyurtma asosida"
        STOCK_AND_ORDER = "stock_and_order", "Ombor va buyurtma"

    class FabricForm(models.TextChoices):
        TUBE = "tube", "Tub/yopiq"
        OPEN = "open", "Ochiq"
        OTHER = "other", "Boshqa"

    class Finish(models.TextChoices):
        RAW = "raw", "Xom"
        PFD = "pfd", "Bo'yashga tayyor (PFD)"
        DYED = "dyed", "Bo'yalgan"

    article = models.CharField(max_length=80)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(
        max_length=30,
        choices=Category.choices,
        default=Category.KNITTED_FABRIC,
    )
    fabric = models.ForeignKey(
        Fabric,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    unit = models.CharField(
        max_length=10,
        choices=Unit.choices,
        default=Unit.PIECE,
    )
    yarn_count = models.CharField(max_length=50, blank=True)
    knitting_machine = models.CharField(max_length=100, blank=True)
    fabric_form = models.CharField(
        max_length=20,
        choices=FabricForm.choices,
        blank=True,
    )
    finish = models.CharField(
        max_length=20,
        choices=Finish.choices,
        blank=True,
    )
    availability = models.CharField(
        max_length=30,
        choices=Availability.choices,
        default=Availability.STOCK,
    )
    stock_quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=0,
        validators=[MinValueValidator(Decimal("0"))],
    )
    list_price = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    price_currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        default=Currency.USD,
    )
    delivery_basis = models.CharField(max_length=100, blank=True, default="FCA Koson")
    price_valid_until = models.DateField(null=True, blank=True)
    image = OptimizedImageField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["article"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "article"],
                name="uniq_product_article",
            )
        ]

    def __str__(self):
        return f"{self.article} — {self.name}"

    @property
    def price_is_expired(self):
        return bool(
            self.price_valid_until and self.price_valid_until < timezone.localdate()
        )


class YarnSpecification(OrganizationScopedModel):
    class SpinningMethod(models.TextChoices):
        RING = "ring", "Ring"
        OPEN_END = "open_end", "Open-end (OE)"
        OTHER = "other", "Boshqa"

    class Preparation(models.TextChoices):
        CARDED = "carded", "Carded"
        COMBED = "combed", "Combed"
        OTHER = "other", "Boshqa"

    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name="yarn_specification",
    )
    yarn_count = models.CharField(max_length=50)
    composition = models.CharField(max_length=200, default="100% cotton")
    spinning_method = models.CharField(
        max_length=20,
        choices=SpinningMethod.choices,
        default=SpinningMethod.RING,
    )
    preparation = models.CharField(
        max_length=20,
        choices=Preparation.choices,
        default=Preparation.CARDED,
    )
    is_compact = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.product.article} / {self.yarn_count}"


class WovenFabricSpecification(OrganizationScopedModel):
    class Selvedge(models.TextChoices):
        CLOSED = "closed", "Yopiq"
        OPEN = "open", "Ochiq"
        OTHER = "other", "Boshqa"

    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name="woven_specification",
    )
    composition = models.CharField(max_length=200, default="100% cotton")
    width_cm = models.DecimalField(max_digits=8, decimal_places=2)
    gsm = models.PositiveIntegerField()
    weave = models.CharField(max_length=30, blank=True)
    warp_yarn = models.CharField(max_length=100, blank=True)
    weft_yarn = models.CharField(max_length=100, blank=True)
    selvedge = models.CharField(
        max_length=20,
        choices=Selvedge.choices,
        blank=True,
    )
    warp_threads = models.PositiveIntegerField(null=True, blank=True)
    weft_threads = models.PositiveIntegerField(null=True, blank=True)
    roll_length_min = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    roll_length_max = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    construction_notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.product.article} / {self.width_cm} cm / {self.gsm} gsm"


class PriceList(OrganizationScopedModel):
    class DocumentType(models.TextChoices):
        PRICE_LIST = "price_list", "Narxlar ro'yxati"
        PRODUCT_LIST = "product_list", "Mahsulotlar ro'yxati"

    class Status(models.TextChoices):
        DRAFT = "draft", "Qoralama"
        ACTIVE = "active", "Amalda"
        EXPIRED = "expired", "Muddati tugagan"
        ARCHIVED = "archived", "Arxivlangan"

    class Language(models.TextChoices):
        UZ = "uz", "O'zbekcha"
        RU = "ru", "Ruscha"
        EN = "en", "Inglizcha"

    number = models.CharField(max_length=50)
    document_type = models.CharField(
        max_length=20,
        choices=DocumentType.choices,
        default=DocumentType.PRICE_LIST,
    )
    title = models.CharField(max_length=200, blank=True)
    category = models.CharField(
        max_length=30,
        choices=Product.Category.choices,
        blank=True,
    )
    issue_date = models.DateField(default=timezone.localdate)
    valid_until = models.DateField(null=True, blank=True)
    currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        default=Currency.USD,
    )
    incoterm = models.CharField(max_length=10, default="FCA")
    delivery_place = models.CharField(max_length=100, default="Koson, UZB")
    incoterms_version = models.CharField(max_length=4, blank=True, default="2020")
    payment_terms = models.CharField(max_length=255, blank=True)
    alternative_delivery_terms = models.CharField(max_length=255, blank=True)
    language = models.CharField(
        max_length=5,
        choices=Language.choices,
        default=Language.RU,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    notes = models.TextField(blank=True)
    document_intro = models.TextField(blank=True)
    document_footer = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        ordering = ["-issue_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "document_type", "number"],
                name="uniq_catalog_price_list_number",
            )
        ]

    def __str__(self):
        return f"{self.number} — {self.get_document_type_display()}"

    @property
    def is_expired(self):
        return bool(self.valid_until and self.valid_until < timezone.localdate())

    @property
    def delivery_basis(self):
        return " ".join(
            value for value in (self.incoterm, self.delivery_place) if value
        )


class PriceListLine(OrganizationScopedModel):
    price_list = models.ForeignKey(
        PriceList,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="price_list_lines",
    )
    description_snapshot = models.TextField(blank=True)
    available_quantity = models.DecimalField(
        max_digits=16,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    unit = models.CharField(max_length=10, choices=Product.Unit.choices)
    unit_price = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    planned_loading_date = models.DateField(null=True, blank=True)
    minimum_order_quantity = models.DecimalField(
        max_digits=16,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "price_list", "product"],
                name="uniq_catalog_price_list_product",
            )
        ]

    def clean(self):
        super().clean()
        if self.price_list_id and self.organization_id != self.price_list.organization_id:
            raise ValidationError("Price-list boshqa tashkilotga tegishli.")
        if self.product_id and self.organization_id != self.product.organization_id:
            raise ValidationError("Mahsulot boshqa tashkilotga tegishli.")

    def __str__(self):
        return f"{self.price_list.number} / {self.product.article}"


class ProductVariant(OrganizationScopedModel):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="variants",
    )
    color = models.ForeignKey(Color, on_delete=models.PROTECT)
    size = models.ForeignKey(Size, on_delete=models.PROTECT)
    sku = models.CharField(max_length=120, blank=True)
    customer_article = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["product", "color", "size"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "product", "color", "size"],
                name="uniq_product_variant",
            )
        ]

    def __str__(self):
        return f"{self.product.article} / {self.color} / {self.size}"
