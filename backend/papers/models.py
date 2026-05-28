"""Persistence for assembled papers.

``Paper`` rows are created by ``PaperAssembler._persist``. Once created they
are immutable for the lifetime of Slice 3 — the PDF cache assumes this.
``PaperQuestion`` is the ordered placement of bank Questions inside a
Paper; future teacher edits will mutate ``PaperQuestion`` so the shared
``bank.Question`` row is never touched.

``Paper.report`` holds the SelectionEngine's report verbatim
(``papers.selection.SelectionReport.to_dict()``). Its shape is owned in
one place: see ``papers.selection.SelectionReport``.
"""
from django.conf import settings
from django.db import models

from accounts.models import School
from bank.models import Question


class Paper(models.Model):
    school = models.ForeignKey(
        School, null=True, blank=True, on_delete=models.SET_NULL, related_name="papers"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="papers"
    )
    title = models.CharField(max_length=255, default="Science — Practice Paper")
    total_marks = models.PositiveSmallIntegerField(default=0)
    # Selection report. Shape owned by papers.selection.SelectionReport:
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
