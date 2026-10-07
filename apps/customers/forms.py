from django import forms

from apps.accounts.models import User
from apps.common.countries import COUNTRY_CHOICES
from apps.common.forms import ListFilterForm
from apps.common.widgets import SearchableSelect

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
    country = forms.ChoiceField(
        required=False,
        label="Mamlakat",
        choices=(("", "Mamlakatni tanlang"), *COUNTRY_CHOICES),
        widget=SearchableSelect(placeholder="Mamlakat nomini yozing..."),
    )

    class Meta:
        model = Contact
        fields = (
            "company",
            "contact_type",
            "full_name",
            "avatar",
            "position",
            "phone",
            "telegram",
            "whatsapp",
            "email",
            "country",
            "city",
            "source",
            "tags",
            "notes",
            "is_primary",
            "is_active",
        )
        widgets = {
            "avatar": forms.ClearableFileInput(
                attrs={
                    "accept": "image/jpeg,image/png,image/webp",
                    "data-avatar-editor": "true",
                }
            ),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }
        help_texts = {
            "avatar": (
                "JPEG, PNG yoki WebP. Maksimal hajm 1 MB, maksimal o'lcham "
                "4096x4096 px. Rasm avtomatik optimallashtiriladi."
            )
        }
        labels = {
            "company": "Bog'langan mijoz yoki kompaniya",
            "contact_type": "Kontakt turi",
            "full_name": "F.I.Sh.",
            "avatar": "Kontakt avatari",
            "position": "Lavozimi yoki roli",
            "phone": "Telefon",
            "email": "Email manzili",
            "telegram": "Telegram",
            "whatsapp": "WhatsApp",
            "country": "Mamlakat",
            "city": "Shahar / hudud",
            "source": "Kontakt manbasi",
            "tags": "Teglar",
            "notes": "Izohlar",
            "is_primary": "Asosiy kontakt",
            "is_active": "Faol kontakt",
        }

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        current_country = (getattr(self.instance, "country", "") or "").strip()
        available_values = {value for value, _label in self.fields["country"].choices}
        if current_country and current_country not in available_values:
            self.fields["country"].choices = (
                ("", "Mamlakatni tanlang"),
                (current_country, current_country),
                *COUNTRY_CHOICES,
            )
        self.fields["company"].queryset = CustomerCompany.objects.filter(
            organization=organization,
            is_active=True,
        )
    def clean(self):
        cleaned_data = super().clean()
        company = cleaned_data.get("company")
        if cleaned_data.get("is_primary") and not company:
            self.add_error("is_primary", "Asosiy kontakt uchun kompaniyani tanlang.")

        duplicate_query = Contact.objects.filter(organization=self.organization)
        if self.instance.pk:
            duplicate_query = duplicate_query.exclude(pk=self.instance.pk)
        email = (cleaned_data.get("email") or "").strip()
        phone = (cleaned_data.get("phone") or "").strip()
        if email and duplicate_query.filter(email__iexact=email).exists():
            self.add_error("email", "Bu email bilan kontakt allaqachon mavjud.")
        if phone and duplicate_query.filter(phone=phone).exists():
            self.add_error("phone", "Bu telefon bilan kontakt allaqachon mavjud.")
        return cleaned_data


class ContactListFilterForm(ListFilterForm):
    contact_type = forms.ChoiceField(
        required=False,
        label="Turi",
        choices=(("", "Barcha turlar"), *Contact.Type.choices),
    )
    company = forms.ModelChoiceField(
        required=False,
        label="Kompaniya",
        queryset=CustomerCompany.objects.none(),
        empty_label="Barcha kompaniyalar",
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
        super().__init__(*args, search_placeholder="F.I.Sh., telefon, email yoki teg", **kwargs)
        self.fields["company"].queryset = CustomerCompany.objects.filter(
            organization=organization,
            is_active=True,
        )
        self.fields["country"].choices = (
            ("", "Barcha hududlar"),
            *((value, value) for value in Contact.objects.filter(
                organization=organization,
            ).exclude(country="").order_by("country").values_list("country", flat=True).distinct()),
        )
        self.fields["owner"].queryset = User.objects.filter(
            memberships__organization=organization,
            memberships__is_active=True,
        ).distinct()
        self.order_fields(("q", "contact_type", "company", "country", "owner", "per_page"))
