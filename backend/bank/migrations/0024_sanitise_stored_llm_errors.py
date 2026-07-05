"""Sanitise LLM-provider errors already stored on failed rows.

Before ``ai_services.errors.friendly_llm_error`` guarded the write path, a raw
provider error (a 402 credits JSON dump carrying an account ``user_id`` and
billing URLs) could be persisted onto ``GenerationBatch.error`` /
``IngestionJob.error`` / ``AnswerGenerationJob.error`` and shown to teachers.
This one-off scrub rewrites those existing values to the same teacher-safe copy
new failures now get. Idempotent: a message with no ``Error code:`` is returned
unchanged, so re-running is a no-op.
"""

from __future__ import annotations

from django.db import migrations

from ai_services.errors import friendly_llm_error


def _scrub(apps, schema_editor):
    for model_name in ("GenerationBatch", "IngestionJob", "AnswerGenerationJob"):
        model = apps.get_model("bank", model_name)
        for row in model.objects.exclude(error="").iterator():
            cleaned = friendly_llm_error(row.error)
            if cleaned != row.error:
                row.error = cleaned
                row.save(update_fields=["error"])


class Migration(migrations.Migration):
    dependencies = [
        ("bank", "0023_answergenerationjob"),
    ]

    operations = [
        migrations.RunPython(_scrub, migrations.RunPython.noop),
    ]
