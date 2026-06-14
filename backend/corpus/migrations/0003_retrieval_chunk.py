import django.contrib.postgres.indexes
import django.contrib.postgres.search
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("corpus", "0002_chapter_map"),
    ]

    operations = [
        migrations.CreateModel(
            name="RetrievalChunk",
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
                ("stable_chunk_id", models.CharField(max_length=64)),
                ("text", models.TextField()),
                ("source_element_ids", models.JSONField(default=list)),
                ("page_start", models.PositiveSmallIntegerField()),
                ("page_end", models.PositiveSmallIntegerField()),
                ("content_types", models.JSONField(default=list)),
                ("citation", models.JSONField(default=dict)),
                (
                    "search_vector",
                    django.contrib.postgres.search.SearchVectorField(null=True),
                ),
                (
                    "chapter",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="retrieval_chunks",
                        to="bank.chapter",
                    ),
                ),
                (
                    "chapter_map_node",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="retrieval_chunks",
                        to="corpus.chaptermapnode",
                    ),
                ),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="retrieval_chunks",
                        to="corpus.textbookdocument",
                    ),
                ),
            ],
            options={
                "ordering": ["chapter_map_node__source_start", "stable_chunk_id"],
                "indexes": [
                    django.contrib.postgres.indexes.GinIndex(
                        fields=["search_vector"], name="retrieval_chunk_search_gin"
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("document", "stable_chunk_id"),
                        name="unique_retrieval_chunk_id",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("page_end__gte", models.F("page_start"))),
                        name="retrieval_chunk_valid_page_range",
                    ),
                ],
            },
        ),
    ]
