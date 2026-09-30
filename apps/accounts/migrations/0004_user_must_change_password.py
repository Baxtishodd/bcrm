from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0003_mailboxaccount_imap_is_verified_and_more")]

    operations = [
        migrations.AddField(
            model_name="user",
            name="must_change_password",
            field=models.BooleanField(default=False),
        ),
    ]
