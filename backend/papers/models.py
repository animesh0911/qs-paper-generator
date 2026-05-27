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

    class Meta:
        ordering = ["order"]
        unique_together = [("paper", "order")]
