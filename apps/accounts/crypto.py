import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def _fernet():
    secret = settings.EMAIL_CREDENTIAL_ENCRYPTION_KEY or settings.SECRET_KEY
    if not secret:
        raise ImproperlyConfigured(
            "Email credential encryption uchun maxfiy kalit sozlanmagan."
        )
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(value):
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value):
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except InvalidToken as error:
        raise ValueError("Saqlangan email parolini o'qib bo'lmadi.") from error
