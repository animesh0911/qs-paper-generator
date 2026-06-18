"""Add ai_generated source provenance for accepted generated Questions."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bank", "0015_ingestionjob_thread_id"),
    ]

    operations = [
        migrations.AlterField(
            model_name="question",
            name="source_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("previous_year_paper", "Previous-year paper"),
                    ("sample_paper", "Sample paper"),
                    ("question_bank", "Question bank"),
                    ("ai_generated", "AI-generated"),
                ],
                default="previous_year_paper",
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="ingestionjob",
            name="source_type",
            field=models.CharField(
                choices=[
                    ("previous_year_paper", "Previous-year paper"),
                    ("sample_paper", "Sample paper"),
                    ("question_bank", "Question bank"),
                    ("ai_generated", "AI-generated"),
                ],
                default="previous_year_paper",
                max_length=32,
            ),
        ),
    ]
