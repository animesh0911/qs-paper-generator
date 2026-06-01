"""Persistence for assembled papers.

``Paper`` rows are created by ``PaperBuilder._persist``. ``Paper.document``
snapshots the full ``PaperDocumentV1`` JSON at assemble time so the teacher
can reload mid-review. PATCH /api/papers/{pk} overwrites ``document`` while
the paper is a draft; POST /api/papers/{pk}/approve locks it (status →
approved) and reconciles PaperQuestion rows from the final document.

``Paper.report`` holds the QuestionPicker's report verbatim
(``papers.picker.CoverageReport.to_dict()``). Its shape is owned in
one place: see ``papers.picker.CoverageReport``.
"""

from django.conf import settings
from django.db import models

from accounts.models import School
from bank.models import Question


class PaperStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    APPROVED = "approved", "Approved"


class Paper(models.Model):
    school = models.ForeignKey(
        School, null=True, blank=True, on_delete=models.SET_NULL, related_name="papers"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="papers"
    )
    title = models.CharField(max_length=255, default="Science — Practice Paper")
    total_marks = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(
        max_length=10, choices=PaperStatus.choices, default=PaperStatus.DRAFT
    )
    # Snapshot of PaperDocumentV1 at assemble time. Overwritten on PATCH,
    # frozen on approve. Null for papers assembled before this field existed.
    document = models.JSONField(null=True, blank=True)
    # Selection report. Shape owned by papers.picker.CoverageReport:
    # {coverage: {chapter_slug: int}, cog_coverage: {level: int},
    #  unfilled: [{slot_index, section, qtype, marks, reason}]}
    report = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} (#{self.pk})"


class PaperQuestion(models.Model):
    """Ordered placement of a bank question within a paper.

    Per-question teacher edits will live here in later slices so they never
    mutate the shared bank question.
    """

    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name="items")
    question = models.ForeignKey(Question, on_delete=models.PROTECT)
    order = models.PositiveSmallIntegerField()
    section = models.CharField(max_length=4)
    or_group = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["order"]
        unique_together = [("paper", "order")]
