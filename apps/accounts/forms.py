from django import forms

from .models import MailboxAccount, User


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "email",
            "phone",
            "avatar",
            "preferred_language",
        )
        labels = {
            "first_name": "Ism",
            "last_name": "Familiya",
            "email": "Email / login",
            "phone": "Telefon",
            "avatar": "Profil rasmi",
            "preferred_language": "Interfeys tili",
        }
        widgets = {
            "avatar": forms.ClearableFileInput(
                attrs={
                    "accept": "image/jpeg,image/png,image/webp",
                    "data-avatar-editor": "true",
                }
            )
        }
        help_texts = {
            "avatar": "JPEG, PNG yoki WebP. Rasm kesilib va optimallashtirib saqlanadi.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].disabled = True


class MailboxAccountForm(forms.ModelForm):
    password = forms.CharField(
        label="Email paroli yoki App Password",
        widget=forms.PasswordInput(render_value=False),
        help_text="Parol shifrlangan holda saqlanadi va qayta ko'rsatilmaydi.",
    )

    class Meta:
        model = MailboxAccount
        fields = (
            "email",
            "display_name",
            "username",
            "password",
            "smtp_host",
            "smtp_port",
            "smtp_security",
            "imap_host",
            "imap_port",
            "imap_security",
            "is_default",
            "is_active",
        )
        labels = {
            "email": "Email manzili",
            "display_name": "Yuboruvchi nomi",
            "username": "Login",
            "smtp_host": "SMTP server",
            "smtp_port": "SMTP port",
            "smtp_security": "SMTP himoyasi",
            "imap_host": "IMAP server",
            "imap_port": "IMAP port",
            "imap_security": "IMAP himoyasi",
            "is_default": "Asosiy yuboruvchi akkaunt",
            "is_active": "Faol",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["password"].required = False
            self.fields["password"].help_text = (
                "Joriy parolni saqlab qolish uchun bo'sh qoldiring. "
                "Yangi qiymat kiritilsa, u shifrlab almashtiriladi."
            )

    def save(self, commit=True):
        account = super().save(commit=False)
        password = self.cleaned_data.get("password")
        if password:
            account.set_password(password)
        if commit:
            account.save()
        return account
