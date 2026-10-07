from django.db import migrations, models

import apps.common.images


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0008_remove_pricelist_uniq_catalog_price_list_number_and_more"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="pricelistline",
            name="uniq_catalog_price_list_product",
        ),
        migrations.AddField(
            model_name="pricelistline",
            name="color",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="pricelistline",
            name="image",
            field=apps.common.images.OptimizedImageField(blank=True),
        ),
        migrations.AddField(
            model_name="pricelistline",
            name="size",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddConstraint(
            model_name="pricelistline",
            constraint=models.UniqueConstraint(
                fields=("organization", "price_list", "product", "color", "size"),
                name="uniq_catalog_price_list_product_variant",
            ),
        ),
    ]
