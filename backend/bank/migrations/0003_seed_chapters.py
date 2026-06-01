from django.db import migrations

# Canonical CBSE Class 10 Science chapters (NCERT, 2024-25 onward).
CHAPTERS = [
    (1, "chemical-reactions-and-equations", "Chemical Reactions and Equations"),
    (2, "acids-bases-and-salts", "Acids, Bases and Salts"),
    (3, "metals-and-non-metals", "Metals and Non-metals"),
    (4, "carbon-and-its-compounds", "Carbon and its Compounds"),
    (5, "life-processes", "Life Processes"),
    (6, "control-and-coordination", "Control and Coordination"),
    (7, "how-do-organisms-reproduce", "How do Organisms Reproduce?"),
    (8, "heredity", "Heredity"),
    (9, "light-reflection-and-refraction", "Light – Reflection and Refraction"),
    (10, "human-eye-and-the-colourful-world", "The Human Eye and the Colourful World"),
    (11, "electricity", "Electricity"),
    (
        12,
        "magnetic-effects-of-electric-current",
        "Magnetic Effects of Electric Current",
    ),
    (13, "our-environment", "Our Environment"),
]


def seed(apps, schema_editor):
    Chapter = apps.get_model("bank", "Chapter")
    for order, slug, name in CHAPTERS:
        Chapter.objects.update_or_create(
            slug=slug, defaults={"name": name, "order": order}
        )


def unseed(apps, schema_editor):
    Chapter = apps.get_model("bank", "Chapter")
    Chapter.objects.filter(slug__in=[s for _, s, _ in CHAPTERS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("bank", "0002_chapter_question_cognitive_level_question_chapter"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
