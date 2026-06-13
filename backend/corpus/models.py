"""Persistence for the developer-populated NCERT corpus.

The corpus module owns canonical textbook extraction provenance and
source-addressable elements. It references ``bank.Chapter`` as the shared
closed syllabus taxonomy but does not participate in Question ingestion.
"""

from django.db import models

from bank.models import Chapter


class TextbookDocument(models.Model):
    """One canonical extraction of an NCERT Chapter."""

    chapter = models.ForeignKey(
        Chapter, on_delete=models.PROTECT, related_name="textbook_documents"
    )
    source_file_name = models.CharField(max_length=255)
    source_hash = models.CharField(max_length=64)
    extractor_name = models.CharField(max_length=80)
    extractor_version = models.CharField(max_length=40)
    canonical_json_path = models.CharField(max_length=500)
    canonical_json_hash = models.CharField(max_length=64)
    page_count = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "chapter",
                    "source_hash",
                    "extractor_name",
                    "extractor_version",
                    "canonical_json_hash",
                ],
                name="unique_textbook_extraction",
            )
        ]

    def __str__(self):
        return (
            f"{self.chapter.slug}: {self.source_file_name} ({self.extractor_version})"
        )


class TextbookElement(models.Model):
    """One stable source-addressable element from a TextbookDocument."""

    document = models.ForeignKey(
        TextbookDocument, on_delete=models.CASCADE, related_name="elements"
    )
    stable_element_id = models.CharField(max_length=64)
    element_type = models.CharField(max_length=40)
    source_order = models.PositiveIntegerField()
    page_number = models.PositiveSmallIntegerField()
    bbox = models.JSONField(default=dict)
    heading_path = models.JSONField(default=list)
    text = models.TextField(blank=True)
    structured_data = models.JSONField(default=dict)
    asset_path = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["source_order"]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "stable_element_id"],
                name="unique_textbook_element_id",
            ),
        ]
        indexes = [models.Index(fields=["document", "source_order"])]

    def __str__(self):
        return f"{self.document.chapter.slug} #{self.source_order}: {self.element_type}"


class ChapterMapNode(models.Model):
    """One deterministic navigational subdivision or source landmark."""

    class NodeType(models.TextChoices):
        DOCUMENT = "document", "Document"
        SECTION = "section", "Section"
        ACTIVITY = "activity", "Activity"
        FIGURE = "figure", "Figure"
        TABLE = "table", "Table"
        QUESTIONS = "questions", "Questions"
        EXERCISES = "exercises", "Exercises"

    document = models.ForeignKey(
        TextbookDocument, on_delete=models.CASCADE, related_name="chapter_map_nodes"
    )
    stable_node_id = models.CharField(max_length=64)
    node_type = models.CharField(max_length=20, choices=NodeType.choices)
    title = models.CharField(max_length=500)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="children",
    )
    source_element = models.ForeignKey(
        TextbookElement,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="chapter_map_evidence",
    )
    source_start = models.PositiveIntegerField()
    source_end = models.PositiveIntegerField()
    page_start = models.PositiveSmallIntegerField()
    page_end = models.PositiveSmallIntegerField()
    element_count = models.PositiveIntegerField()
    preview = models.TextField(blank=True)

    class Meta:
        ordering = ["source_start", "node_type", "stable_node_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "stable_node_id"],
                name="unique_chapter_map_node_id",
            ),
            models.CheckConstraint(
                condition=models.Q(source_end__gte=models.F("source_start")),
                name="chapter_map_node_valid_range",
            ),
        ]


class ChapterMapEdge(models.Model):
    """One deterministic or explicitly evidenced relationship between nodes."""

    class EdgeType(models.TextChoices):
        CONTAINS = "contains", "Contains"
        NEXT = "next", "Next"
        REFERENCES = "references", "References"

    document = models.ForeignKey(
        TextbookDocument, on_delete=models.CASCADE, related_name="chapter_map_edges"
    )
    stable_edge_id = models.CharField(max_length=64)
    edge_type = models.CharField(max_length=20, choices=EdgeType.choices)
    source = models.ForeignKey(
        ChapterMapNode, on_delete=models.CASCADE, related_name="outgoing_edges"
    )
    target = models.ForeignKey(
        ChapterMapNode, on_delete=models.CASCADE, related_name="incoming_edges"
    )
    evidence_element = models.ForeignKey(
        TextbookElement,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="chapter_map_edge_evidence",
    )

    class Meta:
        ordering = ["edge_type", "stable_edge_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "stable_edge_id"],
                name="unique_chapter_map_edge_id",
            )
        ]
