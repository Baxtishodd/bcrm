from django import forms

from apps.accounts.models import User
from apps.catalog.models import Product
from apps.crm.models import Lead
from apps.customers.models import CustomerCompany

from .models import Quotation, QuotationDelivery, QuotationLine, SalesOrder


class QuotationForm(forms.ModelForm):
    class Meta:
        model = Quotation
        fields = (
            "number",
            "customer",
            "lead",
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
            "lead": "Lead",
            "status": "Holat",
            "currency": "Valyuta",
            "valid_until": "Amal qilish muddati",
            "discount_percent": "Chegirma foizi",
            "tax_percent": "Soliq foizi",
            "delivery_terms": "Yetkazish sharti",
            "payment_terms": "To'lov sharti",
            "notes": "Izoh",
        }

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer"].queryset = CustomerCompany.objects.filter(
            organization=organization,
            is_active=True,
        )
        self.fields["lead"].queryset = Lead.objects.filter(
            organization=organization,
        )
        self.fields["number"].required = False

    def clean(self):
        cleaned_data = super().clean()
        lead = cleaned_data.get("lead")
        customer = cleaned_data.get("customer")
        if lead and lead.customer_id and customer and lead.customer_id != customer.id:
            self.add_error("lead", "Lead tanlangan mijozga tegishli emas.")
        return cleaned_data


class QuotationLineForm(forms.ModelForm):
    class Meta:
        model = QuotationLine
        fields = ("product", "description", "quantity", "unit_price")
        labels = {
            "product": "Mahsulot",
            "description": "Tavsif",
            "quantity": "Miqdor",
            "unit_price": "Birlik narxi",
        }

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = Product.objects.filter(
            organization=organization,
            is_active=True,
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
