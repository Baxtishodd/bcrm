from django import forms

from apps.accounts.models import User
from apps.common.forms import ListFilterForm

from .models import Contact, CustomerCompany


class CustomerListFilterForm(ListFilterForm):
    relationship_status = forms.ChoiceField(
        required=False,
        label="Holati",
        choices=(("", "Barcha holatlar"), *CustomerCompany.RelationshipStatus.choices),
    )
    business_direction = forms.ChoiceField(
        required=False,
        label="Yo'nalish",
        choices=(("", "Barcha yo'nalishlar"), *CustomerCompany.BusinessDirection.choices),
    )
    country = forms.ChoiceField(
        required=False,
        label="Mamlakat / hudud",
        choices=(("", "Barcha hududlar"),),
    )
    owner = forms.ModelChoiceField(
        required=False,
        label="Mas'ul",
        queryset=User.objects.none(),
        empty_label="Barcha mas'ullar",
    )

    def __init__(self, *args, organization, **kwargs):
        super().__init__(
            *args,
            search_placeholder="Nomi, kontakt, mahsulot yoki izoh",
            **kwargs,
        )
        self.fields["country"].choices = (
            ("", "Barcha hududlar"),
            *(
                (country, country)
                for country in CustomerCompany.objects.filter(
                    organization=organization,
                )
                .exclude(country="")
                .order_by("country")
                .values_list("country", flat=True)
                .distinct()
            ),
        )
        self.fields["owner"].queryset = User.objects.filter(
            memberships__organization=organization,
            memberships__is_active=True,
        ).distinct()
        self.order_fields(
            (
                "q",
                "relationship_status",
                "business_direction",
                "country",
                "owner",
                "per_page",
            )
        )


class CustomerCompanyForm(forms.ModelForm):
    class Meta:
        model = CustomerCompany
        fields = (
            "name",
            "relationship_status",
            "business_direction",
            "customer_type",
            "product_interest",
            "purchase_purpose",
            "tax_id",
            "phone",
            "telegram",
            "whatsapp",
            "email",
            "country",
            "city",
            "address",
            "notes",
            "credit_limit",
            "owner",
            "is_active",
        )
        widgets = {
            "product_interest": forms.Textarea(attrs={"rows": 3}),
            "purchase_purpose": forms.Textarea(attrs={"rows": 3}),
            "address": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }
        labels = {
            "name": "Mijoz yoki kompaniya nomi",
            "relationship_status": "Mijoz holati",
            "business_direction": "Biznes yo'nalishi",
            "customer_type": "Mijoz turi / bozor",
            "product_interest": "Qiziqayotgan mahsulot yoki xizmat",
            "purchase_purpose": "Xarid maqsadi",
            "telegram": "Telegram",
            "whatsapp": "WhatsApp",
            "notes": "Izohlar",
            "credit_limit": "Kredit limiti (UZS)",
        }

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["owner"].queryset = User.objects.filter(
            memberships__organization=organization,
            memberships__is_active=True,
        ).distinct()
        self.fields["credit_limit"].required = False


class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = (
            "full_name",
            "position",
            "phone",
            "telegram",
            "whatsapp",
            "email",
            "is_primary",
        )
        labels = {
            "full_name": "F.I.Sh.",
            "position": "Lavozimi yoki roli",
            "telegram": "Telegram",
            "whatsapp": "WhatsApp",
            "is_primary": "Asosiy kontakt",
        }
