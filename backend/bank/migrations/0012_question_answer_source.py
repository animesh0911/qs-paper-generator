from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bank", "0011_question_primary_form"),
    ]

    operations = [
        migrations.AddField(
            model_name="question",
            name="answer_source",
            field=models.CharField(
                blank=True,
                choices=[
                    ("human", "Human-entered"),
                    ("extracted", "Extracted from source"),
                    ("generated_unverified", "Generated (unverified)"),
                    ("generated_verified", "Generated (verified)"),
                ],
                default="",
                max_length=24,
            ),
        ),
    ]
