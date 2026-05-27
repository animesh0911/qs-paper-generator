from django.db import models

from accounts.models import School


class Section(models.TextChoices):
    A = "A", "Section A — MCQ"
    B = "B", "Section B — Very Short Answer"
    C = "C", "Section C — Short Answer"
    D = "D", "Section D — Long Answer"
    E = "E", "Section E — Case-based"


class QuestionType(models.TextChoices):
    MCQ = "MCQ", "Multiple Choice"
    VSA = "VSA", "Very Short Answer"
    SA = "SA", "Short Answer"
    LA = "LA", "Long Answer"
    CASE = "CASE", "Case-based"


class Question(models.Model):
    """A single bank question.

    Slice 1 keeps this minimal; later slices add chapter, cognitive level,
    diagrams, verification status, etc.
    """

    school = models.ForeignKey(
        School, null=True, blank=True, on_delete=models.SET_NULL, related_name="questions"
    )
    section = models.CharField(max_length=4, choices=Section.choices)
    qtype = models.CharField(max_length=4, choices=QuestionType.choices)
    marks = models.PositiveSmallIntegerField()
    text = models.TextField()
    # For MCQ: list of {"label": "A", "text": "..."} options. Empty otherwise.
    options = models.JSONField(default=list, blank=True)
    answer = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["section", "id"]

    def __str__(self):
        return f"[{self.section}/{self.marks}m] {self.text[:60]}"
