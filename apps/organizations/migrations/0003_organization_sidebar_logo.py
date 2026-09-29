from django.db import migrations

import apps.common.images


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0002_organization_settings"),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="sidebar_logo",
            field=apps.common.images.OptimizedImageField(blank=True),
        ),
    ]
