"""Question bank models — the source of truth for what questions exist.

Three concepts live here:

* **Section** / **QuestionType** / **CognitiveLevel** — fixed enumerations
  shared by the bank, the blueprint, and the renderer.
* **Chapter** — canonical CBSE Cl.10 Science chapter, seeded by a data
  migration (``bank/migrations/0003_seed_chapters.py``).
* **Question** — one bank item, tagged with section, qtype, marks, chapter
  and cognitive level.

Where it fits:
- Read by ``papers.selection.SelectionEngine`` to fetch candidate pools.
- Written by ``bank.management.commands.seed_questions`` and (Slice 4+) by
  ingestion of ``content/`` PDFs.
- Exposed to the API via ``bank.serializers`` and ``bank.views``.
"""
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


class CognitiveLevel(models.TextChoices):
    REMEMBER = "R", "Remember"
    UNDERSTAND = "U", "Understand"
    APPLY = "Ap", "Apply"
    ANALYSE = "An", "Analyse"


class Chapter(models.Model):
    """Canonical CBSE Class 10 Science chapter.

    Seeded as a fixed 13-row taxonomy in ``migrations/0003_seed_chapters.py``.
    The ``slug`` is the stable identifier used by API payloads and the
    ``SelectionEngine`` (chapter weights are keyed by slug, not pk).
    """

    slug = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=160)
    order = models.PositiveSmallIntegerField(unique=True)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.order}. {self.name}"


class Question(models.Model):
    """A single bank question.

    Owns enough metadata for ``SelectionEngine`` to allocate it under chapter
    weights and difficulty profiles: ``chapter`` (FK), ``cognitive_level``,
    ``section``, ``qtype``, ``marks``. ``answer`` is stored alongside but is
    only exposed through serializers gated on ``bank.policy.answer_visible``.
    """

    school = models.ForeignKey(
        School, null=True, blank=True, on_delete=models.SET_NULL, related_name="questions"
    )
    chapter = models.ForeignKey(
        Chapter, null=True, blank=True, on_delete=models.PROTECT, related_name="questions"
    )
    section = models.CharField(max_length=4, choices=Section.choices)
    qtype = models.CharField(max_length=4, choices=QuestionType.choices)
    marks = models.PositiveSmallIntegerField()
    cognitive_level = models.CharField(
        max_length=2, choices=CognitiveLevel.choices, default=CognitiveLevel.REMEMBER
    )
    text = models.TextField()
    # For MCQ: list of {"label": "A", "text": "..."} options. Empty otherwise.
    options = models.JSONField(default=list, blank=True)
    answer = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["section", "id"]

    def __str__(self):
        return f"[{self.section}/{self.marks}m] {self.text[:60]}"
