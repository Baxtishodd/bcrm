from django import forms

from apps.accounts.models import User

from .models import Contact, CustomerCompany


class CustomerCompanyForm(forms.ModelForm):
    class Meta:
        model = CustomerCompany
        fields = (
            "name",
            "customer_type",
            "tax_id",
            "phone",
            "telegram",
            "email",
            "country",
            "city",
            "address",
            "credit_limit",
            "owner",
            "is_active",
        )
        widgets = {"address": forms.Textarea(attrs={"rows": 3})}
        labels = {
            "telegram": "Telegram",
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
            "email",
            "is_primary",
        )
