from django import forms
from django.forms import inlineformset_factory

from .models import (
    Color,
    Fabric,
    PriceList,
    PriceListLine,
    Product,
    ProductVariant,
    Size,
    WovenFabricSpecification,
    YarnSpecification,
)


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = (
            "article",
            "name",
            "description",
            "category",
            "fabric",
            "unit",
            "yarn_count",
            "knitting_machine",
            "fabric_form",
            "finish",
            "availability",
            "stock_quantity",
            "list_price",
            "price_currency",
            "delivery_basis",
            "price_valid_until",
            "image",
            "is_active",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "price_valid_until": forms.DateInput(attrs={"type": "date"}),
            "image": forms.ClearableFileInput(
                attrs={"accept": "image/jpeg,image/png,image/webp"}
            ),
        }
        help_texts = {
            "image": (
                "JPEG, PNG yoki WebP. Maksimal hajm 1 MB, maksimal o'lcham "
                "4096x4096 px. Rasm avtomatik optimallashtiriladi."
            )
        }
        labels = {
            "article": "Artikul",
            "name": "Mahsulot nomi",
            "description": "Tavsif",
            "category": "Mahsulot kategoriyasi",
            "fabric": "Mato turi",
            "unit": "O'lchov birligi",
            "yarn_count": "Ip raqami",
            "knitting_machine": "To'quv uskunasi",
            "fabric_form": "Mato ko'rinishi",
            "finish": "Pardoz holati",
            "availability": "Ta'minot turi",
            "stock_quantity": "Ombordagi miqdor",
            "list_price": "Narx",
            "price_currency": "Valyuta",
            "delivery_basis": "Yetkazish bazisi",
            "price_valid_until": "Narx amal qilish muddati",
            "image": "Rasm",
            "is_active": "Faol",
        }

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


class YarnSpecificationForm(forms.ModelForm):
    class Meta:
        model = YarnSpecification
        fields = (
            "yarn_count",
            "composition",
            "spinning_method",
            "preparation",
            "is_compact",
        )
        labels = {
            "yarn_count": "Ip raqami",
            "composition": "Tarkibi",
            "spinning_method": "Yigirish usuli",
            "preparation": "Tayyorlash turi",
            "is_compact": "Compact ip",
        }


class WovenFabricSpecificationForm(forms.ModelForm):
    class Meta:
        model = WovenFabricSpecification
        fields = (
            "composition",
            "width_cm",
            "gsm",
            "weave",
            "warp_yarn",
            "weft_yarn",
            "selvedge",
            "warp_threads",
            "weft_threads",
            "roll_length_min",
            "roll_length_max",
            "construction_notes",
        )
        widgets = {"construction_notes": forms.Textarea(attrs={"rows": 4})}
        labels = {
            "composition": "Tarkibi",
            "width_cm": "Eni (sm)",
            "gsm": "Zichligi (GSM)",
            "weave": "To'qilish turi",
            "warp_yarn": "Tanda ipi",
            "weft_yarn": "Arqoq ipi",
            "selvedge": "Qirg'oq turi",
            "warp_threads": "Tanda iplari soni",
            "weft_threads": "Arqoq iplari soni",
            "roll_length_min": "O'ramdagi minimal metr",
            "roll_length_max": "O'ramdagi maksimal metr",
            "construction_notes": "Qo'shimcha texnik izoh",
        }


class PriceListForm(forms.ModelForm):
    class Meta:
        model = PriceList
        fields = (
            "number",
            "document_type",
            "title",
            "category",
            "issue_date",
            "valid_until",
            "currency",
            "incoterm",
            "delivery_place",
            "incoterms_version",
            "payment_terms",
            "alternative_delivery_terms",
            "language",
            "status",
            "notes",
            "document_intro",
            "document_footer",
        )
        widgets = {
            "issue_date": forms.DateInput(attrs={"type": "date"}),
            "valid_until": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 4}),
            "payment_terms": forms.Textarea(attrs={"rows": 3}),
            "alternative_delivery_terms": forms.Textarea(attrs={"rows": 3}),
            "document_intro": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Hamkorlarga kirish matni..."}
            ),
            "document_footer": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Hujjat uchun alohida footer..."}
            ),
        }
        labels = {
            "number": "Hujjat raqami",
            "document_type": "Hujjat turi",
            "title": "Sarlavha",
            "category": "Mahsulot yo'nalishi",
            "issue_date": "Hujjat sanasi",
            "valid_until": "Amal qilish muddati",
            "currency": "Valyuta",
            "incoterm": "Incoterm",
            "delivery_place": "Yetkazish joyi",
            "incoterms_version": "Incoterms versiyasi",
            "payment_terms": "To'lov sharti",
            "alternative_delivery_terms": "Muqobil yetkazish sharti",
            "language": "Hujjat tili",
            "status": "Holati",
            "notes": "Izoh",
            "document_intro": "Kirish matni",
            "document_footer": "Hujjat footeri",
        }

    def clean(self):
        cleaned_data = super().clean()
        issue_date = cleaned_data.get("issue_date")
        valid_until = cleaned_data.get("valid_until")
        if issue_date and valid_until and valid_until < issue_date:
            self.add_error(
                "valid_until",
                "Amal qilish muddati hujjat sanasidan oldin bo'lishi mumkin emas.",
            )
        return cleaned_data


class PriceListLineForm(forms.ModelForm):
    class Meta:
        model = PriceListLine
        fields = (
            "product",
            "description_snapshot",
            "available_quantity",
            "unit",
            "unit_price",
            "planned_loading_date",
            "minimum_order_quantity",
            "sort_order",
        )
        widgets = {
            "description_snapshot": forms.Textarea(attrs={"rows": 5}),
            "planned_loading_date": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "product": "Mahsulot",
            "description_snapshot": "Taklifdagi texnik tavsif",
            "available_quantity": "Taklif qilinadigan miqdor",
            "unit": "O'lchov birligi",
            "unit_price": "Birlik narxi",
            "planned_loading_date": "Rejalashtirilgan yuklash sanasi",
            "minimum_order_quantity": "Minimal buyurtma",
            "sort_order": "Qator tartibi",
        }

    def __init__(self, *args, organization, price_list=None, **kwargs):
        super().__init__(*args, **kwargs)
        products = Product.objects.filter(organization=organization, is_active=True)
        if price_list and price_list.category:
            products = products.filter(category=price_list.category)
        self.fields["product"].queryset = products

    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get("product")
        if product and not cleaned_data.get("description_snapshot"):
            cleaned_data["description_snapshot"] = product.description or product.name
        if product and cleaned_data.get("unit_price") is None:
            cleaned_data["unit_price"] = product.list_price
        return cleaned_data


PriceListDocumentLineFormSet = inlineformset_factory(
    PriceList,
    PriceListLine,
    form=PriceListLineForm,
    fields=(
        "product",
        "description_snapshot",
        "available_quantity",
        "unit",
        "unit_price",
        "planned_loading_date",
        "minimum_order_quantity",
        "sort_order",
    ),
    extra=1,
    can_delete=True,
)
