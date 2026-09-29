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
CHOICES = [
    ("USD", "AQSh dollari (USD)"),
    ("EUR", "Yevro (EUR)"),
    ("RUB", "Rossiya rubli (RUB)"),
    ("UZS", "O'zbekiston so'mi (UZS)"),
]


def normalize_currencies(apps, schema_editor):
    for model_name, field_name in (("Product", "price_currency"), ("PriceList", "currency")):
        model = apps.get_model("catalog", model_name)
        for instance in model.objects.all().iterator():
            current = getattr(instance, field_name)
            normalized = ALIASES.get(str(current or "").strip().upper(), "USD")
            if current != normalized:
                setattr(instance, field_name, normalized)
                instance.save(update_fields=[field_name])


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0006_pricelist_document_fields"),
    ]

    operations = [
        migrations.RunPython(normalize_currencies, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="product",
            name="price_currency",
            field=models.CharField(choices=CHOICES, default="USD", max_length=3),
        ),
        migrations.AlterField(
            model_name="pricelist",
            name="currency",
            field=models.CharField(choices=CHOICES, default="USD", max_length=3),
        ),
    ]
