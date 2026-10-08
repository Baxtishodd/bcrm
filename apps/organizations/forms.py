from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from apps.accounts.models import User

from .models import (
    Branch,
    Membership,
    Organization,
    OrganizationRole,
    RolePermission,
)


def employee_role_choices(organization, *, include_owner=False):
    builtin = [
        choice
        for choice in Membership.Role.choices
        if include_owner or choice[0] != Membership.Role.OWNER
    ]
    custom = [
        (f"custom:{role.public_id}", role.name)
        for role in organization.custom_roles.order_by("name")
    ]
    choices = [("Standart rollar", builtin)]
    if custom:
        choices.append(("Maxsus rollar", custom))
    return choices


class OrganizationRoleForm(forms.ModelForm):
    class Meta:
        model = OrganizationRole
        fields = ("name", "description")
        labels = {
            "name": "Rol nomi",
            "description": "Tavsifi",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, organization, **kwargs):
        self.organization = organization
        super().__init__(*args, **kwargs)
        selected = set()
        if self.instance.pk:
            selected = set(
                self.instance.permission_entries.values_list("module", "action")
            )
        for module, _module_label in RolePermission.Module.choices:
            for action, action_label in RolePermission.Action.choices:
                key = self.permission_field_name(module, action)
                self.fields[key] = forms.BooleanField(
                    required=False,
                    label=action_label,
                    initial=(module, action) in selected,
                )

    @staticmethod
    def permission_field_name(module, action):
        return f"permission_{module}_{action}"

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        duplicate = self.organization.custom_roles.filter(name__iexact=name)
        if self.instance.pk:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise forms.ValidationError("Bu nomdagi rol avval yaratilgan.")
        return name

    def save(self, commit=True):
        role = super().save(commit=False)
        role.organization = self.organization
        if not commit:
            return role
        role.save()
        selected = []
        for module in RolePermission.Module.values:
            module_actions = {
                action
                for action in RolePermission.Action.values
                if self.cleaned_data.get(self.permission_field_name(module, action))
            }
            if module_actions:
                module_actions.add(RolePermission.Action.VIEW)
            for action in module_actions:
                selected.append(
                    RolePermission(role=role, module=module, action=action)
                )
        role.permission_entries.all().delete()
        RolePermission.objects.bulk_create(selected)
        return role


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


class EmployeeCreateForm(forms.Form):
    first_name = forms.CharField(label="Ismi", max_length=150)
    last_name = forms.CharField(label="Familiyasi", max_length=150, required=False)
    email = forms.EmailField(label="Email / login")
    phone = forms.CharField(label="Telefon", max_length=30, required=False)
    avatar = forms.ImageField(
        label="Xodim avatari",
        required=False,
        widget=forms.ClearableFileInput(
            attrs={
                "accept": "image/jpeg,image/png,image/webp",
                "data-avatar-editor": "true",
            }
        ),
        help_text="JPEG, PNG yoki WebP. Maksimal 1 MB; rasm tahrirlanib optimallashtiriladi.",
    )
    role = forms.ChoiceField(label="Lavozim")
    branch = forms.ModelChoiceField(
        label="Filial",
        queryset=Branch.objects.none(),
        required=False,
        empty_label="Filial biriktirilmagan",
    )
    can_manage_all_records = forms.BooleanField(
        label="Barcha xodimlarning yozuvlarini boshqarish",
        required=False,
        help_text=(
            "Yoqilsa, xodim boshqa xodimlarga tegishli mijoz, kontakt, lead, "
            "vazifa, savdo va tushumlarni ham o'zgartira oladi."
        ),
    )
    password1 = forms.CharField(
        label="Vaqtinchalik parol",
        required=False,
        strip=False,
        widget=forms.PasswordInput,
        help_text="Yangi login uchun majburiy. Mavjud foydalanuvchi uchun bo'sh qoldiring.",
    )
    password2 = forms.CharField(
        label="Parolni takrorlang",
        required=False,
        strip=False,
        widget=forms.PasswordInput,
    )

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        self.fields["role"].choices = employee_role_choices(organization)
        self.fields["branch"].queryset = organization.branches.filter(is_active=True)

    def clean_role(self):
        value = self.cleaned_data["role"]
        if not value.startswith("custom:"):
            return value
        public_id = value.removeprefix("custom:")
        if not self.organization.custom_roles.filter(public_id=public_id).exists():
            raise forms.ValidationError("Tanlangan rol mavjud emas.")
        return value

    def clean_email(self):
        email = User.objects.normalize_email(self.cleaned_data["email"]).lower()
        if Membership.objects.filter(
            organization=self.organization,
            user__email__iexact=email,
        ).exists():
            raise forms.ValidationError("Bu xodim tashkilotga avval qo'shilgan.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if not email:
            return cleaned_data

        existing_user = User.objects.filter(email__iexact=email).first()
        if not existing_user and not password1:
            self.add_error("password1", "Yangi login uchun vaqtinchalik parol kiriting.")
        if password1 != password2:
            self.add_error("password2", "Parollar bir xil emas.")
        if password1 and not existing_user:
            candidate = User(email=email)
            try:
                validate_password(password1, user=candidate)
            except ValidationError as error:
                self.add_error("password1", error)
        return cleaned_data

    def save(self):
        email = self.cleaned_data["email"]
        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            user = User.objects.create_user(
                email=email,
                password=self.cleaned_data["password1"],
                first_name=self.cleaned_data["first_name"],
                last_name=self.cleaned_data["last_name"],
                phone=self.cleaned_data["phone"],
                avatar=self.cleaned_data["avatar"],
                must_change_password=True,
            )
        elif self.cleaned_data["avatar"]:
            user.avatar = self.cleaned_data["avatar"]
            user.save(update_fields=["avatar"])
        selected_role = self.cleaned_data["role"]
        custom_role = None
        builtin_role = selected_role
        if selected_role.startswith("custom:"):
            custom_role = self.organization.custom_roles.get(
                public_id=selected_role.removeprefix("custom:")
            )
            builtin_role = Membership.Role.VIEWER
        return Membership.objects.create(
            organization=self.organization,
            user=user,
            role=builtin_role,
            custom_role=custom_role,
            branch=self.cleaned_data["branch"],
            can_manage_all_records=self.cleaned_data["can_manage_all_records"],
        )


class EmployeeUpdateForm(forms.Form):
    first_name = forms.CharField(label="Ismi", max_length=150)
    last_name = forms.CharField(label="Familiyasi", max_length=150, required=False)
    email = forms.EmailField(label="Email / login", disabled=True)
    phone = forms.CharField(label="Telefon", max_length=30, required=False)
    avatar = forms.ImageField(
        label="Xodim avatari",
        required=False,
        widget=forms.ClearableFileInput(
            attrs={
                "accept": "image/jpeg,image/png,image/webp",
                "data-avatar-editor": "true",
            }
        ),
        help_text="Yangi rasm tanlansa, avval kesish va tahrirlash oynasi ochiladi.",
    )
    role = forms.ChoiceField(label="Lavozim")
    branch = forms.ModelChoiceField(
        label="Filial",
        queryset=Branch.objects.none(),
        required=False,
        empty_label="Filial biriktirilmagan",
    )
    can_manage_all_records = forms.BooleanField(
        label="Barcha xodimlarning yozuvlarini boshqarish",
        required=False,
        help_text=(
            "Yoqilsa, xodim boshqa xodimlarga tegishli mijoz, kontakt, lead, "
            "vazifa, savdo va tushumlarni ham o'zgartira oladi."
        ),
    )
    is_active = forms.BooleanField(label="Faol xodim", required=False)

    def __init__(self, *args, membership, actor_membership, **kwargs):
        self.membership = membership
        self.actor_membership = actor_membership
        initial = kwargs.setdefault("initial", {})
        initial.update(
            {
                "first_name": membership.user.first_name,
                "last_name": membership.user.last_name,
                "email": membership.user.email,
                "phone": membership.user.phone,
                "role": (
                    f"custom:{membership.custom_role.public_id}"
                    if membership.custom_role_id
                    else membership.role
                ),
                "branch": membership.branch,
                "can_manage_all_records": membership.can_manage_all_records,
                "is_active": membership.is_active,
            }
        )
        super().__init__(*args, **kwargs)
        if membership.role == Membership.Role.OWNER:
            self.fields["role"].choices = [
                (Membership.Role.OWNER, Membership.Role.OWNER.label)
            ]
            self.fields["role"].disabled = True
        else:
            self.fields["role"].choices = employee_role_choices(
                membership.organization
            )
        self.fields["branch"].queryset = membership.organization.branches.filter(
            is_active=True
        )

    def clean_is_active(self):
        is_active = self.cleaned_data["is_active"]
        if self.membership == self.actor_membership and not is_active:
            raise forms.ValidationError("O'zingizni bloklay olmaysiz.")
        if self.membership.role == Membership.Role.OWNER and not is_active:
            raise forms.ValidationError("Tashkilot egasini bloklab bo'lmaydi.")
        return is_active

    def clean_role(self):
        value = self.cleaned_data["role"]
        if self.membership.role == Membership.Role.OWNER:
            return Membership.Role.OWNER
        if not value.startswith("custom:"):
            return value
        public_id = value.removeprefix("custom:")
        if not self.membership.organization.custom_roles.filter(
            public_id=public_id
        ).exists():
            raise forms.ValidationError("Tanlangan rol mavjud emas.")
        return value

    def save(self):
        user = self.membership.user
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.phone = self.cleaned_data["phone"]
        update_fields = ["first_name", "last_name", "phone"]
        if self.cleaned_data["avatar"]:
            user.avatar = self.cleaned_data["avatar"]
            update_fields.append("avatar")
        user.save(update_fields=update_fields)
        selected_role = self.cleaned_data["role"]
        if selected_role.startswith("custom:"):
            self.membership.custom_role = self.membership.organization.custom_roles.get(
                public_id=selected_role.removeprefix("custom:")
            )
            self.membership.role = Membership.Role.VIEWER
        else:
            self.membership.custom_role = None
            self.membership.role = selected_role
        self.membership.branch = self.cleaned_data["branch"]
        self.membership.can_manage_all_records = self.cleaned_data[
            "can_manage_all_records"
        ]
        self.membership.is_active = self.cleaned_data["is_active"]
        self.membership.save(
            update_fields=[
                "role",
                "custom_role",
                "branch",
                "can_manage_all_records",
                "is_active",
                "updated_at",
            ]
        )
        return self.membership
