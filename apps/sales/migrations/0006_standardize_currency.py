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
    quotation_model = apps.get_model("sales", "Quotation")
    for quotation in quotation_model.objects.all().iterator():
        normalized = ALIASES.get(
            str(quotation.currency or "").strip().upper(),
            "UZS",
        )
        if quotation.currency != normalized:
            quotation.currency = normalized
            quotation.save(update_fields=["currency"])


class Migration(migrations.Migration):
    dependencies = [
        ("sales", "0005_quotation_document_fields"),
    ]

    operations = [
        migrations.RunPython(normalize_currencies, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="quotation",
            name="currency",
            field=models.CharField(
                choices=[
                    ("USD", "AQSh dollari (USD)"),
                    ("EUR", "Yevro (EUR)"),
                    ("RUB", "Rossiya rubli (RUB)"),
                    ("UZS", "O'zbekiston so'mi (UZS)"),
                ],
                default="UZS",
                max_length=3,
            ),
        ),
    ]
