from django import forms

from apps.accounts.models import User
from apps.crm.models import Lead


class ListFilterForm(forms.Form):
    PER_PAGE_CHOICES = (
        ("25", "25 ta"),
        ("50", "50 ta"),
        ("100", "100 ta"),
    )

    q = forms.CharField(
        required=False,
        label="Qidirish",
        widget=forms.SearchInput(attrs={"placeholder": "Qidirish"}),
    )
    per_page = forms.ChoiceField(
        required=False,
        label="Sahifada",
        choices=PER_PAGE_CHOICES,
        initial="25",
    )

    def __init__(self, *args, search_placeholder=None, **kwargs):
        super().__init__(*args, **kwargs)
        if search_placeholder:
            self.fields["q"].widget.attrs["placeholder"] = search_placeholder


class SalesReportFilterForm(forms.Form):
    date_from = forms.DateField(
        label="Boshlanish sanasi",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    date_to = forms.DateField(
        label="Tugash sanasi",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    assigned_to = forms.ModelChoiceField(
        label="Menejer",
        queryset=User.objects.none(),
        required=False,
        empty_label="Barcha menejerlar",
    )
    business_direction = forms.ChoiceField(
        label="Yo'nalish",
        required=False,
    )

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = User.objects.filter(
            memberships__organization=organization,
            memberships__is_active=True,
        ).distinct()
        self.fields["business_direction"].choices = [
            ("", "Barcha yo'nalishlar"),
            *Lead.BusinessDirection.choices,
        ]

    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get("date_from")
        date_to = cleaned_data.get("date_to")
        if date_from and date_to and date_from > date_to:
            self.add_error("date_to", "Tugash sanasi boshlanish sanasidan oldin bo'lmaydi.")
        return cleaned_data
