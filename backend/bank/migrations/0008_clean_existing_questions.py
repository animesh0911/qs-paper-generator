"""Data migration: mark all pre-existing Question rows as parse_quality='clean'.

These rows were hand-seeded by `seed_questions` (Slice 1), known-good. They
were previously gated only by `verified` (manually flipped to True post-seed
in dev). Per ADR-0002 the picker now gates on `parse_quality`; existing rows
default to `partial` from the column default, so we promote them to `clean`
here so the existing test/dev workflow doesn't degrade.

New ingested rows will be tagged by the parser at write time.
"""
from django.db import migrations


def promote(apps, schema_editor):
    Question = apps.get_model("bank", "Question")
    Question.objects.update(parse_quality="clean")


def reverse(apps, schema_editor):
    Question = apps.get_model("bank", "Question")
    Question.objects.update(parse_quality="partial")


class Migration(migrations.Migration):

    dependencies = [
        ("bank", "0007_seed_chapter_subject_area"),
    ]

    operations = [
        migrations.RunPython(promote, reverse),
    ]
