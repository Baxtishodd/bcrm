from django import forms
from django.db import models
from django.forms import inlineformset_factory

from apps.accounts.models import MailboxAccount, User
from apps.catalog.models import Product, ProductVariant
from apps.catalog.pricing import find_active_price
from apps.common.widgets import DependentContactSelect, SearchableSelect
from apps.crm.models import Lead
from apps.customers.models import Contact, CustomerCompany

from .models import (
    Payment,
    PaymentPlan,
    Quotation,
    QuotationDelivery,
    QuotationLine,
    SalesOrder,
)


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
            "customer": SearchableSelect(placeholder="Mijozni qidirish..."),
            "contact": DependentContactSelect(),
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
        if (
            assigned_to
            and not assigned_to.memberships.filter(
                organization=self.organization,
                is_active=True,
            ).exists()
        ):
            self.add_error("assigned_to", "Xodim bu korxonaga tegishli emas.")
        return cleaned_data


class QuotationLineForm(forms.ModelForm):
    class Meta:
        model = QuotationLine
        fields = (
            "product",
            "variant",
            "description",
            "quantity",
            "unit_price",
            "price_override_reason",
        )
        widgets = {
            "price_override_reason": forms.TextInput(
                attrs={"placeholder": "Faqat avtomatik narx o'zgartirilsa..."}
            )
        }
        labels = {
            "product": "Mahsulot",
            "variant": "Rang-o'lcham varianti",
            "description": "Tavsif",
            "quantity": "Miqdor",
            "unit_price": "Birlik narxi",
            "price_override_reason": "Narxni o'zgartirish sababi",
        }

    def __init__(self, *args, organization, quotation=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
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
            "Bo'sh qoldirilsa, faol price-list yoki mahsulot katalogidagi narx olinadi."
        )
        self._resolved_price_line = None
        self._resolved_source_price = None
        self._resolved_price_source = None

    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get("product")
        variant = cleaned_data.get("variant")
        quantity = cleaned_data.get("quantity")
        unit_price = cleaned_data.get("unit_price")
        override_reason = cleaned_data.get("price_override_reason", "").strip()
        if variant and product and variant.product_id != product.id:
            self.add_error("variant", "Variant tanlangan mahsulotga tegishli emas.")
        if variant and quantity is not None and quantity != quantity.to_integral_value():
            self.add_error("quantity", "Variantli mahsulot miqdori butun son bo'lishi kerak.")
        if product:
            currency = self.quotation.currency if self.quotation else product.price_currency
            price_line = find_active_price(
                organization=self.organization,
                product=product,
                currency=currency,
                quantity=quantity,
            )
            automatic_price = None
            automatic_source = None
            if price_line:
                automatic_price = price_line.unit_price
                automatic_source = QuotationLine.PriceSource.PRICE_LIST
            elif product.list_price is not None and product.price_currency == currency:
                automatic_price = product.list_price
                automatic_source = QuotationLine.PriceSource.CATALOG

            if unit_price is None:
                if automatic_price is None:
                    self.add_error(
                        "unit_price",
                        f"{currency} valyutasida amaldagi narx mavjud emas.",
                    )
                else:
                    cleaned_data["unit_price"] = automatic_price
                    unit_price = automatic_price

            if automatic_price is not None and unit_price != automatic_price:
                if not override_reason:
                    self.add_error(
                        "price_override_reason",
                        "Avtomatik narx o'zgartirilsa, sababini kiriting.",
                    )
                self._resolved_price_source = QuotationLine.PriceSource.MANUAL
            else:
                self._resolved_price_source = automatic_source or QuotationLine.PriceSource.MANUAL
            self._resolved_price_line = price_line
            self._resolved_source_price = automatic_price
        if not cleaned_data.get("description") and product:
            cleaned_data["description"] = product.description or product.name
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.price_source = self._resolved_price_source or QuotationLine.PriceSource.MANUAL
        instance.source_unit_price = self._resolved_source_price
        instance.source_price_list = (
            self._resolved_price_line.price_list if self._resolved_price_line else None
        )
        if commit:
            instance.save()
            self.save_m2m()
        return instance


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
    fields=(
        "product",
        "variant",
        "description",
        "quantity",
        "unit_price",
        "price_override_reason",
    ),
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


class QuotationEmailForm(forms.Form):
    account = forms.ModelChoiceField(
        label="Yuboruvchi email akkaunti",
        queryset=MailboxAccount.objects.none(),
    )
    recipient = forms.EmailField(label="Qabul qiluvchi email")
    subject = forms.CharField(label="Email mavzusi", max_length=255)
    message = forms.CharField(
        label="Email matni",
        widget=forms.Textarea(attrs={"rows": 8}),
    )
    follow_up_at = forms.DateTimeField(
        label="Keyingi bog'lanish vaqti",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        help_text="Email yuborilgach ushbu vaqtga avtomatik vazifa yaratiladi.",
    )

    def __init__(self, *args, accounts, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = accounts


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


class PaymentPlanForm(forms.ModelForm):
    class Meta:
        model = PaymentPlan
        fields = ("due_date", "amount", "notes")
        widgets = {"due_date": forms.DateInput(attrs={"type": "date"})}
        labels = {
            "due_date": "Rejalashtirilgan sana",
            "amount": "Rejalashtirilgan summa",
            "notes": "Izoh",
        }

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if self.instance.pk and amount < self.instance.received_amount:
            raise forms.ValidationError(
                "Reja summasi unga bog'langan tushumlar summasidan kam bo'lishi mumkin emas."
            )
        return amount


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ("plan", "received_on", "amount", "method", "reference", "notes")
        widgets = {"received_on": forms.DateInput(attrs={"type": "date"})}
        labels = {
            "plan": "To'lov rejasi",
            "received_on": "Tushum sanasi",
            "amount": "Tushgan summa",
            "method": "To'lov usuli",
            "reference": "To'lov hujjati raqami",
            "notes": "Izoh",
        }

    def __init__(self, *args, order, **kwargs):
        super().__init__(*args, **kwargs)
        self.order = order
        available_plans = order.payment_plans.filter(is_cancelled=False)
        if self.instance.pk and self.instance.plan_id:
            available_plans = order.payment_plans.filter(
                models.Q(is_cancelled=False) | models.Q(pk=self.instance.plan_id)
            )
        self.fields["plan"].queryset = available_plans
        self.fields["plan"].required = False
        self.fields["plan"].empty_label = "Rejaga bog'lanmagan tushum"

    def clean_plan(self):
        plan = self.cleaned_data.get("plan")
        if plan and plan.order_id != self.order.id:
            raise forms.ValidationError("Reja ushbu buyurtmaga tegishli emas.")
        return plan


class PaymentCancellationForm(forms.Form):
    reason = forms.CharField(
        label="Bekor qilish sababi",
        max_length=255,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
