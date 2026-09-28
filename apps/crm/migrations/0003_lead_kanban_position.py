from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0002_lead_business_direction"),
    ]

    operations = [
        migrations.AddField(
            model_name="lead",
            name="kanban_position",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterModelOptions(
            name="lead",
            options={"ordering": ["kanban_position", "-created_at"]},
        ),
    ]
