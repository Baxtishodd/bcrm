from django import forms
from django.forms import inlineformset_factory

from apps.accounts.models import User
from apps.catalog.models import Product, ProductVariant
from apps.crm.models import Lead
from apps.customers.models import Contact, CustomerCompany

from .models import Quotation, QuotationDelivery, QuotationLine, SalesOrder


class QuotationForm(forms.ModelForm):
    class Meta:
        model = Quotation
        fields = (
            "number",
            "customer",
            "contact",
            "lead",
            "assigned_to",
            "status",
            "currency",
            "valid_until",
            "discount_percent",
            "tax_percent",
            "delivery_terms",
            "payment_terms",
            "notes",
        )
        widgets = {
            "valid_until": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }
        labels = {
            "number": "Taklif raqami",
            "customer": "Mijoz",
            "contact": "Kontakt",
            "lead": "Lead",
            "assigned_to": "Mas'ul xodim",
            "status": "Holat",
            "currency": "Valyuta",
            "valid_until": "Amal qilish muddati",
            "discount_percent": "Chegirma foizi",
            "tax_percent": "Soliq foizi",
            "delivery_terms": "Yetkazish sharti",
            "payment_terms": "To'lov sharti",
            "notes": "Izoh",
        }

    def __init__(self, *args, organization, source_lead=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        self.source_lead = source_lead
        self.fields["customer"].queryset = CustomerCompany.objects.filter(
            organization=organization,
            is_active=True,
        )
        self.fields["contact"].queryset = Contact.objects.filter(
            organization=organization,
        ).select_related("company")
        self.fields["lead"].queryset = Lead.objects.filter(
            organization=organization,
        )
        self.fields["assigned_to"].queryset = User.objects.filter(
            memberships__organization=organization,
            memberships__is_active=True,
        ).distinct()
        self.fields["number"].required = False
        if source_lead:
            self.fields["customer"].disabled = True
            self.fields["lead"].disabled = True
            self.fields["customer"].help_text = "Lead'dan avtomatik olindi."
            self.fields["lead"].help_text = "Ushbu taklif joriy Lead bilan bog'lanadi."

    def clean(self):
        cleaned_data = super().clean()
        lead = cleaned_data.get("lead")
        customer = cleaned_data.get("customer")
        contact = cleaned_data.get("contact")
        assigned_to = cleaned_data.get("assigned_to")
        if self.source_lead and lead != self.source_lead:
            self.add_error("lead", "Taklif boshqa Lead bilan bog'lanishi mumkin emas.")
        if self.source_lead and customer != self.source_lead.customer:
            self.add_error("customer", "Mijoz Lead'dan avtomatik olinadi.")
        if lead and lead.customer_id and customer and lead.customer_id != customer.id:
            self.add_error("lead", "Lead tanlangan mijozga tegishli emas.")
        if contact and customer and contact.company_id != customer.id:
            self.add_error("contact", "Kontakt tanlangan mijozga tegishli emas.")
        if assigned_to and not assigned_to.memberships.filter(
            organization=self.organization,
            is_active=True,
        ).exists():
            self.add_error("assigned_to", "Xodim bu korxonaga tegishli emas.")
        return cleaned_data


class QuotationLineForm(forms.ModelForm):
    class Meta:
        model = QuotationLine
        fields = ("product", "variant", "description", "quantity", "unit_price")
        labels = {
            "product": "Mahsulot",
            "variant": "Rang-o'lcham varianti",
            "description": "Tavsif",
            "quantity": "Miqdor",
            "unit_price": "Birlik narxi",
        }

    def __init__(self, *args, organization, quotation=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.quotation = quotation
        self.fields["product"].queryset = Product.objects.filter(
            organization=organization,
            is_active=True,
        )
        self.fields["variant"].queryset = ProductVariant.objects.filter(
            organization=organization,
            product__is_active=True,
        ).select_related("product", "color", "size")
        self.fields["unit_price"].required = False
        self.fields["unit_price"].help_text = (
            "Bo'sh qoldirilsa, mahsulot katalogidagi amaldagi narx olinadi."
        )

    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get("product")
        variant = cleaned_data.get("variant")
        quantity = cleaned_data.get("quantity")
        unit_price = cleaned_data.get("unit_price")
        if variant and product and variant.product_id != product.id:
            self.add_error("variant", "Variant tanlangan mahsulotga tegishli emas.")
        if variant and quantity is not None and quantity != quantity.to_integral_value():
            self.add_error("quantity", "Variantli mahsulot miqdori butun son bo'lishi kerak.")
        if unit_price is None and product:
            if product.list_price is None:
                self.add_error("unit_price", "Mahsulot katalogida narx mavjud emas.")
            else:
                cleaned_data["unit_price"] = product.list_price
        if not cleaned_data.get("description") and product:
            cleaned_data["description"] = product.description or product.name
        return cleaned_data


class QuotationDocumentForm(forms.ModelForm):
    class Meta:
        model = Quotation
        fields = (
            "document_language",
            "document_title",
            "document_intro",
            "currency",
            "valid_until",
            "discount_percent",
            "tax_percent",
            "delivery_terms",
            "payment_terms",
            "notes",
            "document_footer",
        )
        widgets = {
            "valid_until": forms.DateInput(attrs={"type": "date"}),
            "document_title": forms.TextInput(attrs={"class": "document-title-input"}),
            "document_intro": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Mijozga kirish matni..."}
            ),
            "delivery_terms": forms.Textarea(attrs={"rows": 3}),
            "payment_terms": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 3}),
            "document_footer": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Hujjat uchun alohida footer..."}
            ),
        }
        labels = {
            "document_language": "Hujjat tili",
            "document_title": "Hujjat sarlavhasi",
            "document_intro": "Kirish matni",
            "currency": "Valyuta",
            "valid_until": "Amal qilish muddati",
            "discount_percent": "Chegirma foizi",
            "tax_percent": "Soliq foizi",
            "delivery_terms": "Yetkazish sharti",
            "payment_terms": "To'lov sharti",
            "notes": "Izoh",
            "document_footer": "Hujjat footeri",
        }


QuotationDocumentLineFormSet = inlineformset_factory(
    Quotation,
    QuotationLine,
    form=QuotationLineForm,
    fields=("product", "variant", "description", "quantity", "unit_price"),
    extra=1,
    can_delete=True,
)


class QuotationDeliveryForm(forms.ModelForm):
    class Meta:
        model = QuotationDelivery
        fields = ("channel", "recipient", "status", "notes")
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}
        labels = {
            "channel": "Yuborish kanali",
            "recipient": "Qabul qiluvchi",
            "status": "Yetkazish holati",
            "notes": "Izoh yoki mijoz javobi",
        }


class SalesOrderForm(forms.ModelForm):
    class Meta:
        model = SalesOrder
        fields = (
            "number",
            "customer",
            "quotation",
            "status",
            "order_date",
            "delivery_date",
            "advance_amount",
            "paid_amount",
            "assigned_to",
            "notes",
        )
        widgets = {
            "order_date": forms.DateInput(attrs={"type": "date"}),
            "delivery_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }
        labels = {
            "number": "Buyurtma raqami",
            "customer": "Mijoz",
            "quotation": "Asos bo'lgan taklif",
            "status": "Holat",
            "order_date": "Buyurtma sanasi",
            "delivery_date": "Yetkazish sanasi",
            "advance_amount": "Avans",
            "paid_amount": "Jami to'langan",
            "assigned_to": "Mas'ul xodim",
            "notes": "Izoh",
        }

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["number"].required = False
        self.fields["customer"].queryset = CustomerCompany.objects.filter(
            organization=organization,
            is_active=True,
        )
        self.fields["quotation"].queryset = Quotation.objects.filter(
            organization=organization,
            salesorder__isnull=True,
        )
        if self.instance.pk and self.instance.quotation_id:
            self.fields["quotation"].queryset = Quotation.objects.filter(
                organization=organization,
            ).filter(pk=self.instance.quotation_id)
        self.fields["assigned_to"].queryset = User.objects.filter(
            memberships__organization=organization,
            memberships__is_active=True,
        ).distinct()

    def clean(self):
        cleaned_data = super().clean()
        quotation = cleaned_data.get("quotation")
        customer = cleaned_data.get("customer")
        if quotation and customer and quotation.customer_id != customer.id:
            self.add_error("quotation", "Taklif tanlangan mijozga tegishli emas.")
        return cleaned_data
