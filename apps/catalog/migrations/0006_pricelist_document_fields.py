from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0005_alter_pricelist_incoterms_version_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="pricelist",
            name="document_footer",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="pricelist",
            name="document_intro",
            field=models.TextField(blank=True),
        ),
    ]
