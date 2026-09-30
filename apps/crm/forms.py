from django import forms

from apps.accounts.models import User
from apps.common.widgets import DependentContactSelect, SearchableSelect
from apps.customers.models import Contact, CustomerCompany

from .models import Activity, Lead, PipelineStage


class LeadForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = (
            "title",
            "business_direction",
            "customer",
            "contact",
            "stage",
            "status",
            "priority",
            "source",
            "estimated_value",
            "currency",
            "assigned_to",
            "next_action_at",
            "lost_reason",
            "description",
        )
        widgets = {
            "customer": SearchableSelect(placeholder="Mijozni qidirish..."),
            "contact": DependentContactSelect(),
            "next_action_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "description": forms.Textarea(attrs={"rows": 4}),
            "lost_reason": forms.Textarea(attrs={"rows": 2}),
        }
        labels = {
            "title": "Lead nomi",
            "business_direction": "Savdo yo'nalishi",
            "customer": "Mijoz",
            "contact": "Kontakt",
            "stage": "Bosqich",
            "status": "Holat",
            "priority": "Ustuvorlik",
            "source": "Manba",
            "estimated_value": "Taxminiy qiymat",
            "currency": "Valyuta",
            "assigned_to": "Mas'ul xodim",
            "next_action_at": "Keyingi harakat",
            "lost_reason": "Yutqazish sababi",
            "description": "Izoh",
        }
        help_texts = {
            "lost_reason": "Lead «Yutqazildi» bo'lsa, ushbu maydon majburiy.",
        }

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        self.instance.organization = organization
        self.fields["customer"].queryset = CustomerCompany.objects.filter(
            organization=organization,
            is_active=True,
        )
        self.fields["contact"].queryset = Contact.objects.filter(
            organization=organization,
        ).select_related("company")
        self.fields["stage"].queryset = PipelineStage.objects.filter(
            organization=organization,
        )
        self.fields["assigned_to"].queryset = User.objects.filter(
            memberships__organization=organization,
            memberships__is_active=True,
        ).distinct()

    def clean(self):
        cleaned_data = super().clean()
        customer = cleaned_data.get("customer")
        contact = cleaned_data.get("contact")
        if contact and customer and contact.company_id != customer.id:
            self.add_error("contact", "Kontakt tanlangan mijozga tegishli emas.")
        return cleaned_data


class ActivityForm(forms.ModelForm):
    class Meta:
        model = Activity
        fields = (
            "activity_type",
            "subject",
            "details",
            "due_at",
            "assigned_to",
        )
        widgets = {
            "due_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "details": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "activity_type": "Faoliyat turi",
            "subject": "Vazifa nomi",
            "details": "Tafsilotlar",
            "due_at": "Bajarish muddati",
            "assigned_to": "Mas'ul xodim",
        }

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        self.fields["assigned_to"].queryset = User.objects.filter(
            memberships__organization=organization,
            memberships__is_active=True,
        ).distinct()


class TaskForm(ActivityForm):
    class Meta(ActivityForm.Meta):
        fields = ("lead", "customer") + ActivityForm.Meta.fields
        labels = {
            **ActivityForm.Meta.labels,
            "lead": "Lead",
            "customer": "Mijoz",
        }

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, organization=organization, **kwargs)
        self.fields["lead"].queryset = Lead.objects.filter(
            organization=organization,
        ).select_related("customer")
        self.fields["customer"].queryset = CustomerCompany.objects.filter(
            organization=organization,
            is_active=True,
        )
        self.fields["lead"].required = False
        self.fields["customer"].required = False

    def clean(self):
        cleaned_data = super().clean()
        lead = cleaned_data.get("lead")
        customer = cleaned_data.get("customer")
        if not lead and not customer:
            raise forms.ValidationError("Lead yoki mijozdan birini tanlang.")
        if lead and customer and lead.customer_id != customer.id:
            self.add_error("customer", "Mijoz tanlangan Lead'ga tegishli emas.")
        if lead and not customer:
            cleaned_data["customer"] = lead.customer
        return cleaned_data
