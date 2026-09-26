from django import forms

from .models import Color, Fabric, Product, ProductVariant, Size


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = (
            "article",
            "name",
            "description",
            "fabric",
            "unit",
            "image",
            "is_active",
        )
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fabric"].queryset = Fabric.objects.filter(
            organization=organization,
        )


class ProductVariantForm(forms.ModelForm):
    class Meta:
        model = ProductVariant
        fields = ("color", "size", "sku", "customer_article")

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["color"].queryset = Color.objects.filter(
            organization=organization,
        )
        self.fields["size"].queryset = Size.objects.filter(
            organization=organization,
        )

