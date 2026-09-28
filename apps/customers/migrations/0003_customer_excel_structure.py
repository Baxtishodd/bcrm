from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0002_customercompany_credit_limit_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="customercompany",
            name="business_direction",
            field=models.CharField(
                choices=[
                    ("knit_fabric", "Trikotaj mato"),
                    ("weaving", "To'quvchilik"),
                    ("yarn", "Ip-kalava"),
                    ("sewing", "Tikuvchilik va xizmatlar"),
                    ("other", "Boshqa"),
                ],
                default="other",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="customercompany",
            name="notes",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="customercompany",
            name="product_interest",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="customercompany",
            name="purchase_purpose",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="customercompany",
            name="relationship_status",
            field=models.CharField(
                choices=[
                    ("working", "Hamkorlik qilinmoqda"),
                    ("potential", "Potensial mijoz"),
                    ("offer_sent", "Taklif yuborilgan"),
                    ("rejected", "Rad etilgan"),
                ],
                default="potential",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="customercompany",
            name="whatsapp",
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddField(
            model_name="contact",
            name="whatsapp",
            field=models.CharField(blank=True, max_length=30),
        ),
    ]
