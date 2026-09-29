from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0004_quotation_lead_workflow"),
    ]

    operations = [
        migrations.AddField(
            model_name="quotation",
            name="document_footer",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="quotation",
            name="document_intro",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="quotation",
            name="document_language",
            field=models.CharField(
                choices=[("uz", "O'zbekcha"), ("ru", "Ruscha"), ("en", "Inglizcha")],
                default="uz",
                max_length=2,
            ),
        ),
        migrations.AddField(
            model_name="quotation",
            name="document_title",
            field=models.CharField(default="TIJORAT TAKLIFI", max_length=200),
        ),
    ]
