from django.db import migrations, models

ALIASES = {
    "$": "USD",
    "DOLLAR": "USD",
    "USD": "USD",
    "€": "EUR",
    "EURO": "EUR",
    "EUR": "EUR",
    "₽": "RUB",
    "RUR": "RUB",
    "RUB": "RUB",
    "SUM": "UZS",
    "SO'M": "UZS",
    "UZS": "UZS",
    "СУМ": "UZS",
}


def normalize_currencies(apps, schema_editor):
    organization_model = apps.get_model("organizations", "Organization")
    for organization in organization_model.objects.all().iterator():
        normalized = ALIASES.get(
            str(organization.default_currency or "").strip().upper(),
            "USD",
        )
        if organization.default_currency != normalized:
            organization.default_currency = normalized
            organization.save(update_fields=["default_currency"])


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0003_organization_sidebar_logo"),
    ]

    operations = [
        migrations.RunPython(normalize_currencies, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="organization",
            name="default_currency",
            field=models.CharField(
                choices=[
                    ("USD", "AQSh dollari (USD)"),
                    ("EUR", "Yevro (EUR)"),
                    ("RUB", "Rossiya rubli (RUB)"),
                    ("UZS", "O'zbekiston so'mi (UZS)"),
                ],
                default="USD",
                max_length=3,
            ),
        ),
    ]
