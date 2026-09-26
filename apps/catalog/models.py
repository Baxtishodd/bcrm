from django.db import models

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
    class Unit(models.TextChoices):
        PIECE = "pcs", "Dona"
        KILOGRAM = "kg", "Kilogram"
        METER = "m", "Metr"

    article = models.CharField(max_length=80)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
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
    image = models.ImageField(upload_to="products/%Y/%m/", blank=True)
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

