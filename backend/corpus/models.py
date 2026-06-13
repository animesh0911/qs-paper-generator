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
