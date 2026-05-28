from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("papers", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="paperquestion",
            name="or_group",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
    ]
