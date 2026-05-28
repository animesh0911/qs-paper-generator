from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bank", "0004_question_verified"),
    ]

    operations = [
        migrations.AddField(
            model_name="question",
            name="has_diagram",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="question",
            name="is_numerical",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="question",
            name="diagram",
            field=models.FileField(blank=True, null=True, upload_to="diagrams/"),
        ),
        migrations.AddField(
            model_name="question",
            name="source_hash",
            field=models.CharField(blank=True, db_index=True, max_length=32),
        ),
    ]
