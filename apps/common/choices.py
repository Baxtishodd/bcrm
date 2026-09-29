from django.db import models


class Currency(models.TextChoices):
    USD = "USD", "AQSh dollari (USD)"
    EUR = "EUR", "Yevro (EUR)"
    RUB = "RUB", "Rossiya rubli (RUB)"
    UZS = "UZS", "O'zbekiston so'mi (UZS)"


CURRENCY_ALIASES = {
    "$": Currency.USD,
    "DOLLAR": Currency.USD,
    "USD": Currency.USD,
    "€": Currency.EUR,
    "EURO": Currency.EUR,
    "EUR": Currency.EUR,
    "₽": Currency.RUB,
    "RUR": Currency.RUB,
    "RUB": Currency.RUB,
    "SUM": Currency.UZS,
    "SO'M": Currency.UZS,
    "UZS": Currency.UZS,
    "СУМ": Currency.UZS,
}


def normalize_currency_code(value, default=Currency.USD):
    normalized = str(value or "").strip().upper()
    return CURRENCY_ALIASES.get(normalized, default)
