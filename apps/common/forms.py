from django import forms


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
