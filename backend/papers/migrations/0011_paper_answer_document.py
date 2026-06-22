from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("papers", "0010_paper_revision"),
    ]

    operations = [
        migrations.AddField(
            model_name="paper",
            name="answer_document",
            field=models.JSONField(blank=True, null=True),
        ),
    ]
