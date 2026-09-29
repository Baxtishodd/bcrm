from django import forms

from .models import Organization


class OrganizationSettingsForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = (
            "name",
            "legal_name",
            "short_name",
            "tax_id",
            "phone",
            "email",
            "website",
            "legal_address",
            "production_address",
            "bank_name",
            "bank_account",
            "bank_code",
            "director_name",
            "logo",
            "sidebar_logo",
            "signature_image",
            "stamp_image",
            "default_currency",
            "default_incoterm",
            "default_delivery_terms",
            "default_payment_terms",
            "quotation_number_prefix",
            "order_number_prefix",
            "quotation_validity_days",
            "document_footer",
            "email_sender_name",
            "telegram_username",
            "whatsapp_phone",
        )
        widgets = {
            "legal_address": forms.Textarea(attrs={"rows": 3}),
            "production_address": forms.Textarea(attrs={"rows": 3}),
            "default_delivery_terms": forms.Textarea(attrs={"rows": 3}),
            "default_payment_terms": forms.Textarea(attrs={"rows": 3}),
            "document_footer": forms.Textarea(attrs={"rows": 3}),
            "logo": forms.ClearableFileInput(
                attrs={"accept": "image/jpeg,image/png,image/webp"}
            ),
            "sidebar_logo": forms.ClearableFileInput(
                attrs={"accept": "image/jpeg,image/png,image/webp"}
            ),
            "signature_image": forms.ClearableFileInput(
                attrs={"accept": "image/jpeg,image/png,image/webp"}
            ),
            "stamp_image": forms.ClearableFileInput(
                attrs={"accept": "image/jpeg,image/png,image/webp"}
            ),
        }
        labels = {
            "name": "Tashkilot nomi",
            "legal_name": "To'liq yuridik nomi",
            "short_name": "Qisqa nomi",
            "tax_id": "STIR",
            "phone": "Telefon",
            "email": "Email",
            "website": "Veb-sayt",
            "legal_address": "Yuridik manzil",
            "production_address": "Ishlab chiqarish manzili",
            "bank_name": "Bank nomi",
            "bank_account": "Hisob raqami",
            "bank_code": "MFO / bank kodi",
            "director_name": "Direktor yoki mas'ul shaxs",
            "logo": "Logotip",
            "sidebar_logo": "Sidebar logotipi",
            "signature_image": "Imzo rasmi",
            "stamp_image": "Muhr rasmi",
            "default_currency": "Standart valyuta",
            "default_incoterm": "Standart Incoterm",
            "default_delivery_terms": "Standart yetkazish sharti",
            "default_payment_terms": "Standart to'lov sharti",
            "quotation_number_prefix": "Taklif raqami prefiksi",
            "order_number_prefix": "Buyurtma raqami prefiksi",
            "quotation_validity_days": "Taklif amal qilish muddati (kun)",
            "document_footer": "Hujjat pastki qismi",
            "email_sender_name": "Email jo'natuvchi nomi",
            "telegram_username": "Telegram foydalanuvchi nomi",
            "whatsapp_phone": "WhatsApp raqami",
        }
        help_texts = {
            "logo": "JPEG, PNG yoki WebP. Maksimal 1 MB; avtomatik optimallashtiriladi.",
            "sidebar_logo": (
                "To'q sidebar uchun oq yoki och rangli logo. Yuklanmasa, asosiy logo "
                "och fonda ko'rsatiladi."
            ),
            "signature_image": "JPEG, PNG yoki WebP. Maksimal 1 MB.",
            "stamp_image": "JPEG, PNG yoki WebP. Maksimal 1 MB.",
            "quotation_number_prefix": "Masalan: BT-Q. Yangi taklif raqamlarida ishlatiladi.",
            "order_number_prefix": "Masalan: BT-O. Yangi buyurtma raqamlarida ishlatiladi.",
            "telegram_username": "@ belgisisiz yoki @ bilan kiritish mumkin.",
            "whatsapp_phone": "Xalqaro format tavsiya etiladi: +998...",
        }

    def clean_quotation_number_prefix(self):
        return self._clean_prefix("quotation_number_prefix")

    def clean_order_number_prefix(self):
        return self._clean_prefix("order_number_prefix")

    def _clean_prefix(self, field_name):
        value = self.cleaned_data[field_name].strip().upper()
        if not value or not all(character.isalnum() or character == "-" for character in value):
            raise forms.ValidationError(
                "Prefiks faqat harf, raqam va chiziqchadan iborat bo'lishi kerak."
            )
        return value
