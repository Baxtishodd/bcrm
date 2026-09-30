from django import forms


class SearchableSelect(forms.Select):
    """Native select enhanced by the shared searchable-select JavaScript."""

    def __init__(self, attrs=None, *, placeholder="Qidirish..."):
        default_attrs = {
            "data-smart-select": "",
            "data-smart-select-placeholder": placeholder,
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)


class DependentContactSelect(SearchableSelect):
    def __init__(self, attrs=None):
        dependent_attrs = {
            "data-smart-select-depends-on": "customer",
            "data-smart-select-empty": "Avval mijozni tanlang",
            "data-smart-select-no-results": "Bu mijoz uchun kontakt topilmadi",
        }
        if attrs:
            dependent_attrs.update(attrs)
        super().__init__(dependent_attrs, placeholder="Kontaktni qidirish...")

    def create_option(
        self,
        name,
        value,
        label,
        selected,
        index,
        subindex=None,
        attrs=None,
    ):
        option = super().create_option(
            name,
            value,
            label,
            selected,
            index,
            subindex=subindex,
            attrs=attrs,
        )
        instance = getattr(value, "instance", None)
        if instance is not None:
            option["attrs"]["data-parent-value"] = str(instance.company_id)
        return option
