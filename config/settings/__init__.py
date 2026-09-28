import os

from django.core.exceptions import ImproperlyConfigured

VALID_ENVIRONMENTS = {"local", "test", "production"}


def get_settings_module(default="local"):
    environment = os.getenv("BCRM_ENV", default).strip().lower()
    if environment not in VALID_ENVIRONMENTS:
        choices = ", ".join(sorted(VALID_ENVIRONMENTS))
        raise ImproperlyConfigured(
            f"Noto'g'ri BCRM_ENV={environment!r}. Mumkin bo'lgan qiymatlar: {choices}."
        )
    return f"config.settings.{environment}"
