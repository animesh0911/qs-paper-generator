import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("corpus", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ChapterMapNode",
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
                ("stable_node_id", models.CharField(max_length=64)),
                (
                    "node_type",
                    models.CharField(
                        choices=[
                            ("document", "Document"),
                            ("section", "Section"),
                            ("activity", "Activity"),
                            ("figure", "Figure"),
                            ("table", "Table"),
                            ("questions", "Questions"),
                            ("exercises", "Exercises"),
                        ],
                        max_length=20,
                    ),
                ),
                ("title", models.CharField(max_length=500)),
                ("source_start", models.PositiveIntegerField()),
                ("source_end", models.PositiveIntegerField()),
                ("page_start", models.PositiveSmallIntegerField()),
                ("page_end", models.PositiveSmallIntegerField()),
                ("element_count", models.PositiveIntegerField()),
                ("preview", models.TextField(blank=True)),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chapter_map_nodes",
                        to="corpus.textbookdocument",
                    ),
                ),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="children",
                        to="corpus.chaptermapnode",
                    ),
                ),
                (
                    "source_element",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="chapter_map_evidence",
                        to="corpus.textbookelement",
                    ),
                ),
            ],
            options={"ordering": ["source_start", "node_type", "stable_node_id"]},
        ),
        migrations.CreateModel(
            name="ChapterMapEdge",
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
                ("stable_edge_id", models.CharField(max_length=64)),
                (
                    "edge_type",
                    models.CharField(
                        choices=[
                            ("contains", "Contains"),
                            ("next", "Next"),
                            ("references", "References"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chapter_map_edges",
                        to="corpus.textbookdocument",
                    ),
                ),
                (
                    "evidence_element",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="chapter_map_edge_evidence",
                        to="corpus.textbookelement",
                    ),
                ),
                (
                    "source",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="outgoing_edges",
                        to="corpus.chaptermapnode",
                    ),
                ),
                (
                    "target",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="incoming_edges",
                        to="corpus.chaptermapnode",
                    ),
                ),
            ],
            options={"ordering": ["edge_type", "stable_edge_id"]},
        ),
        migrations.AddConstraint(
            model_name="chaptermapnode",
            constraint=models.UniqueConstraint(
                fields=("document", "stable_node_id"),
                name="unique_chapter_map_node_id",
            ),
        ),
        migrations.AddConstraint(
            model_name="chaptermapnode",
            constraint=models.CheckConstraint(
                condition=models.Q(("source_end__gte", models.F("source_start"))),
                name="chapter_map_node_valid_range",
            ),
        ),
        migrations.AddConstraint(
            model_name="chaptermapedge",
            constraint=models.UniqueConstraint(
                fields=("document", "stable_edge_id"),
                name="unique_chapter_map_edge_id",
            ),
        ),
    ]
