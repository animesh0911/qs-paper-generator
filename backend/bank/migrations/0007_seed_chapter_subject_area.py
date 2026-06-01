"""Data migration: populate Chapter.subject_area for the 13 NCERT chapters.

Mapping derived from CBSE Cl.10 Science chapter taxonomy:
- Chemistry (1-4): chemical reactions, acids/bases/salts, metals/non-metals, carbon
- Biology (5-8, 13): life processes, control & coordination, reproduction, heredity, our environment
- Physics (9-12): light, human eye, electricity, magnetic effects

Reversible. Forward sets subject_area on every seeded chapter; reverse clears
subject_area but leaves the chapters themselves intact (0003_seed_chapters owns them).
"""

from django.db import migrations

CHAPTER_SUBJECT_AREA = {
    "chemical-reactions-and-equations": "Chemistry",
    "acids-bases-and-salts": "Chemistry",
    "metals-and-non-metals": "Chemistry",
    "carbon-and-its-compounds": "Chemistry",
    "life-processes": "Biology",
    "control-and-coordination": "Biology",
    "how-do-organisms-reproduce": "Biology",
    "heredity": "Biology",
    "light-reflection-and-refraction": "Physics",
    "human-eye-and-the-colourful-world": "Physics",
    "electricity": "Physics",
    "magnetic-effects-of-electric-current": "Physics",
    "our-environment": "Biology",
}


def seed(apps, schema_editor):
    Chapter = apps.get_model("bank", "Chapter")
    for slug, subject_area in CHAPTER_SUBJECT_AREA.items():
        Chapter.objects.filter(slug=slug).update(subject_area=subject_area)


def unseed(apps, schema_editor):
    Chapter = apps.get_model("bank", "Chapter")
    Chapter.objects.filter(slug__in=CHAPTER_SUBJECT_AREA.keys()).update(subject_area="")


class Migration(migrations.Migration):

    dependencies = [
        ("bank", "0006_v1_contract_fields"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
