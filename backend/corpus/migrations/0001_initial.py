import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("bank", "0015_ingestionjob_thread_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="TextbookDocument",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("source_file_name", models.CharField(max_length=255)),
                ("source_hash", models.CharField(max_length=64)),
                ("extractor_name", models.CharField(max_length=80)),
                ("extractor_version", models.CharField(max_length=40)),
                ("canonical_json_path", models.CharField(max_length=500)),
                ("canonical_json_hash", models.CharField(max_length=64)),
                ("page_count", models.PositiveSmallIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "chapter",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="textbook_documents",
                        to="bank.chapter",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="TextbookElement",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("stable_element_id", models.CharField(max_length=64)),
                ("element_type", models.CharField(max_length=40)),
                ("source_order", models.PositiveIntegerField()),
                ("page_number", models.PositiveSmallIntegerField()),
                ("bbox", models.JSONField(default=dict)),
                ("heading_path", models.JSONField(default=list)),
                ("text", models.TextField(blank=True)),
                ("structured_data", models.JSONField(default=dict)),
                ("asset_path", models.CharField(blank=True, max_length=500)),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="elements",
                        to="corpus.textbookdocument",
                    ),
                ),
            ],
            options={"ordering": ["source_order"]},
        ),
        migrations.AddConstraint(
            model_name="textbookdocument",
            constraint=models.UniqueConstraint(
                fields=(
                    "chapter",
                    "source_hash",
                    "extractor_name",
                    "extractor_version",
                    "canonical_json_hash",
                ),
                name="unique_textbook_extraction",
            ),
        ),
        migrations.AddConstraint(
            model_name="textbookelement",
            constraint=models.UniqueConstraint(
                fields=("document", "stable_element_id"),
                name="unique_textbook_element_id",
            ),
        ),
        migrations.AddIndex(
            model_name="textbookelement",
            index=models.Index(
                fields=["document", "source_order"],
                name="corpus_text_documen_c6b272_idx",
            ),
        ),
    ]
