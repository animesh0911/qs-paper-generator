from django.db import migrations, models


def verify_existing_questions(apps, schema_editor):
    """Existing (seeded/manually-added) questions are considered verified."""
    Question = apps.get_model("bank", "Question")
    Question.objects.update(verified=True)


class Migration(migrations.Migration):

    dependencies = [
        ("bank", "0003_seed_chapters"),
    ]

    operations = [
        migrations.AddField(
            model_name="question",
            name="verified",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(verify_existing_questions, migrations.RunPython.noop),
    ]
