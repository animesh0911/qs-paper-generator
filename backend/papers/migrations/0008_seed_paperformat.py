from django.db import migrations


def seed_formats(apps, schema_editor):
    PaperFormat = apps.get_model("papers", "PaperFormat")
    PaperFormat.objects.get_or_create(
        format_id="cbse_science_class_10_board_compact_2026_v1",
        defaults={
            "name": "CBSE End Term Exam",
            "preset_name": "board",
            "page": {
                "size": "CBSE_COMPACT",
                "orientation": "portrait",
                "widthPt": 523.44,
                "heightPt": 693.36,
                "marginPt": {"top": 28, "right": 36, "bottom": 34, "left": 36},
            },
            "layout": {
                "marks": "right_column",
                "questionNumbers": "left_column",
                "mcqOptions": "two_column",
                "instructions": "note_table_then_general",
                "masthead": "cbse_compact",
                "footer": "code_page_pto",
            },
            "is_active": True,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("papers", "0007_paperformat"),
    ]

    operations = [
        migrations.RunPython(seed_formats, migrations.RunPython.noop),
    ]
