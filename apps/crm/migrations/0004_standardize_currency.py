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
    lead_model = apps.get_model("crm", "Lead")
    for lead in lead_model.objects.all().iterator():
        normalized = ALIASES.get(str(lead.currency or "").strip().upper(), "UZS")
        if lead.currency != normalized:
            lead.currency = normalized
            lead.save(update_fields=["currency"])


class Migration(migrations.Migration):
    dependencies = [
        ("crm", "0003_lead_kanban_position"),
    ]

    operations = [
        migrations.RunPython(normalize_currencies, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="lead",
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
