from email.utils import getaddresses
from pathlib import Path

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from apps.accounts.models import MailboxAccount, User
from apps.common.widgets import DependentContactSelect, SearchableSelect
from apps.crm.models import Lead
from apps.customers.models import Contact, CustomerCompany

from .html import sanitize_email_html
from .models import (
    ALLOWED_ATTACHMENT_EXTENSIONS,
    MAX_ATTACHMENT_BYTES,
    Conversation,
    validate_attachment_size,
)

MAX_EMAIL_ATTACHMENTS = 10
MAX_EMAIL_ATTACHMENTS_BYTES = 25 * 1024 * 1024


class ConversationForm(forms.ModelForm):
    class Meta:
        model = Conversation
        fields = ("channel", "title", "customer", "contact", "lead", "assigned_to")
        widgets = {
            "customer": SearchableSelect(placeholder="Mijozni qidirish..."),
            "contact": DependentContactSelect(),
            "lead": SearchableSelect(placeholder="Leadni qidirish..."),
            "assigned_to": SearchableSelect(placeholder="Mas'ul xodim..."),
        }
        labels = {
            "channel": "Kanal",
            "title": "Suhbat nomi",
            "customer": "Mijoz",
            "contact": "Kontakt",
            "lead": "Lead",
            "assigned_to": "Mas'ul xodim",
        }
        help_texts = {
            "channel": (
                "Telegram suhbatini mijoz botga birinchi yozganda tizim avtomatik yaratadi. "
                "Email suhbatini kiruvchi xat yaratadi. WhatsApp keyingi integratsiyada ulanadi."
            ),
            "title": "Bo'sh qoldirilsa kontakt, mijoz yoki Lead nomi ko'rsatiladi.",
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
            is_active=True,
        ).select_related("company")
        self.fields["lead"].queryset = Lead.objects.filter(
            organization=organization,
        )
        self.fields["assigned_to"].queryset = User.objects.filter(
            memberships__organization=organization,
            memberships__is_active=True,
        ).distinct()

    def clean_channel(self):
        channel = self.cleaned_data["channel"]
        if channel != Conversation.Channel.INTERNAL:
            raise forms.ValidationError(
                "Telegram va Email suhbatlari kiruvchi xabar orqali avtomatik yaratiladi."
            )
        return channel


class MessageComposeForm(forms.Form):
    body = forms.CharField(
        required=False,
        label="Xabar",
        widget=forms.Textarea(
            attrs={
                "rows": 2,
                "placeholder": "Xabar yozing...",
                "aria-label": "Xabar matni",
            }
        ),
    )
    attachment = forms.FileField(
        required=False,
        label="Fayl",
        validators=[validate_attachment_size],
        widget=forms.ClearableFileInput(
            attrs={"accept": ".jpg,.jpeg,.png,.webp,.pdf,.doc,.docx,.xls,.xlsx,.txt,.zip"}
        ),
    )

    def clean_attachment(self):
        attachment = self.cleaned_data.get("attachment")
        if not attachment:
            return attachment
        extension = Path(attachment.name).suffix.lower().lstrip(".")
        if extension not in ALLOWED_ATTACHMENT_EXTENSIONS:
            raise forms.ValidationError("Bu turdagi faylni yuklash mumkin emas.")
        if attachment.size > MAX_ATTACHMENT_BYTES:
            raise forms.ValidationError("Fayl hajmi 10 MB dan katta bo'lmasligi kerak.")
        return attachment

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("body", "").strip() and not cleaned_data.get("attachment"):
            raise forms.ValidationError("Xabar matni yoki fayl kiriting.")
        return cleaned_data


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        clean_one = super().clean
        if isinstance(data, (list, tuple)):
            return [clean_one(item, initial) for item in data]
        if data:
            return [clean_one(data, initial)]
        return []


def _parse_email_addresses(value):
    normalized = (value or "").replace(";", ",").replace("\n", ",")
    addresses = []
    seen = set()
    for _name, address in getaddresses([normalized]):
        address = address.strip().lower()
        if not address:
            continue
        try:
            validate_email(address)
        except ValidationError as exc:
            raise forms.ValidationError(f"Noto'g'ri email manzili: {address}") from exc
        if address not in seen:
            seen.add(address)
            addresses.append(address)
    return addresses


class EmailComposeForm(forms.Form):
    class SendMode:
        INDIVIDUAL = "individual"
        GROUP = "group"

    mailbox = forms.ModelChoiceField(
        queryset=MailboxAccount.objects.none(),
        label="Qaysi emaildan",
        empty_label=None,
    )
    to = forms.CharField(
        label="Kimga",
        widget=forms.TextInput(
            attrs={
                "placeholder": "client@example.com, partner@example.com",
                "data-email-recipients": "",
                "list": "email-contact-options",
            }
        ),
        help_text="Email manzillarini vergul, nuqtali vergul yoki yangi qatordan ajrating.",
    )
    cc = forms.CharField(
        required=False,
        label="CC",
        widget=forms.TextInput(attrs={"placeholder": "Nusxa oluvchilar"}),
    )
    bcc = forms.CharField(
        required=False,
        label="BCC",
        widget=forms.TextInput(attrs={"placeholder": "Yashirin nusxa"}),
    )
    send_mode = forms.ChoiceField(
        label="Yuborish turi",
        choices=(
            (SendMode.INDIVIDUAL, "Har bir qabul qiluvchiga alohida"),
            (SendMode.GROUP, "Barchaga bitta guruh emaili"),
        ),
        initial=SendMode.INDIVIDUAL,
        widget=forms.RadioSelect,
        help_text=(
            "Alohida rejimda qabul qiluvchilar bir-birining emailini ko'rmaydi va har biri uchun "
            "alohida suhbat ochiladi."
        ),
    )
    subject = forms.CharField(
        label="Mavzu",
        max_length=500,
        widget=forms.TextInput(attrs={"placeholder": "Email mavzusi"}),
    )
    body = forms.CharField(
        label="Xabar",
        required=False,
        widget=forms.HiddenInput(attrs={"data-email-body": ""}),
    )
    body_html = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"data-email-body-html": ""}),
    )
    quotation = forms.UUIDField(
        required=False,
        widget=forms.HiddenInput(),
    )
    attachments = MultipleFileField(
        required=False,
        label="Fayllar",
        widget=MultipleFileInput(
            attrs={
                "multiple": True,
                "accept": ".jpg,.jpeg,.png,.webp,.pdf,.doc,.docx,.xls,.xlsx,.txt,.zip",
            }
        ),
        help_text="Bir nechta fayl tanlash mumkin. Har bir fayl 10 MB gacha.",
    )

    def __init__(self, *args, organization, user, **kwargs):
        super().__init__(*args, **kwargs)
        mailboxes = MailboxAccount.objects.filter(
            organization=organization,
            is_active=True,
        ).select_related("user")
        self.fields["mailbox"].queryset = mailboxes
        default_mailbox = mailboxes.filter(user=user, is_default=True).first()
        if not default_mailbox:
            default_mailbox = mailboxes.filter(user=user).first() or mailboxes.first()
        if default_mailbox:
            self.fields["mailbox"].initial = default_mailbox

    def clean_to(self):
        addresses = _parse_email_addresses(self.cleaned_data["to"])
        if not addresses:
            raise forms.ValidationError("Kamida bitta qabul qiluvchi emailini kiriting.")
        if len(addresses) > 100:
            raise forms.ValidationError("Bir yuborishda ko'pi bilan 100 ta manzil mumkin.")
        return addresses

    def clean_cc(self):
        return _parse_email_addresses(self.cleaned_data.get("cc", ""))

    def clean_bcc(self):
        return _parse_email_addresses(self.cleaned_data.get("bcc", ""))

    def clean_attachments(self):
        attachments = self.cleaned_data.get("attachments", [])
        if len(attachments) > MAX_EMAIL_ATTACHMENTS:
            raise forms.ValidationError(
                f"Ko'pi bilan {MAX_EMAIL_ATTACHMENTS} ta fayl biriktirish mumkin."
            )
        if sum(attachment.size for attachment in attachments) > MAX_EMAIL_ATTACHMENTS_BYTES:
            raise forms.ValidationError("Fayllarning umumiy hajmi 25 MB dan oshmasligi kerak.")
        for attachment in attachments:
            validate_attachment_size(attachment)
            extension = Path(attachment.name).suffix.lower().lstrip(".")
            if extension not in ALLOWED_ATTACHMENT_EXTENSIONS:
                raise forms.ValidationError(f"{attachment.name}: bu turdagi fayl mumkin emas.")
        return attachments

    def clean_body_html(self):
        return sanitize_email_html(self.cleaned_data.get("body_html", ""))

    def clean(self):
        cleaned_data = super().clean()
        body = cleaned_data.get("body", "").strip()
        body_html = cleaned_data.get("body_html", "").strip()
        if not body and not body_html:
            self.add_error("body", "Email matnini kiriting.")
        return cleaned_data
