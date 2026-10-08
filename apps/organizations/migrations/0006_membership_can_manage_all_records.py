from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0005_organizationrole_membership_custom_role_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="membership",
            name="can_manage_all_records",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Xodimga boshqa xodimlarga biriktirilgan mijoz, kontakt, "
                    "lead, vazifa va savdo yozuvlarini o'zgartirish huquqini beradi."
                ),
            ),
        ),
    ]
