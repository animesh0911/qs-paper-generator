"""Question bank models — the source of truth for what questions exist.

Three concepts live here:

* **Section** / **QuestionType** / **CognitiveLevel** — fixed enumerations
  shared by the bank, the template builder, and the renderer.
* **Chapter** — canonical CBSE Cl.10 Science chapter, seeded by a data
  migration (``bank/migrations/0003_seed_chapters.py``).
* **Question** — one bank item, tagged with section, qtype, marks, chapter
  and cognitive level.

Where it fits:
- Read by ``papers.picker.QuestionPicker`` to fetch candidate pools.
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
    """Question type — values are identical to PaperDocumentV1 `questionType`
    strings in `contracts/v1_contract.md`. No mapping layer exists between DB
    and API. See ADR-0001."""

    MCQ = "mcq", "Multiple Choice"
    ASSERTION_REASON = "assertion_reason", "Assertion-Reason"
    VSA = "very_short_answer", "Very Short Answer"
    SA = "short_answer", "Short Answer"
    LA = "long_answer", "Long Answer"
    CASE = "case_based", "Case-based"
    INTERNAL_CHOICE = "internal_choice", "Internal Choice"
    DIAGRAM_BASED = "diagram_based", "Diagram-based"
    TABLE_BASED = "table_based", "Table-based"
    CUSTOM = "custom", "Custom"


class CognitiveLevel(models.TextChoices):
    REMEMBER = "R", "Remember"
    UNDERSTAND = "U", "Understand"
    APPLY = "Ap", "Apply"
    ANALYSE = "An", "Analyse"


class SubjectArea(models.TextChoices):
    BIOLOGY = "Biology", "Biology"
    CHEMISTRY = "Chemistry", "Chemistry"
    PHYSICS = "Physics", "Physics"


class ParseQuality(models.TextChoices):
    CLEAN = "clean", "Clean"
    PARTIAL = "partial", "Partial"
    BROKEN = "broken", "Broken"


class Chapter(models.Model):
    """Canonical CBSE Class 10 Science chapter.

    Seeded as a fixed 13-row taxonomy in ``migrations/0003_seed_chapters.py``.
    The ``slug`` is the stable identifier used by API payloads and the
    ``QuestionPicker`` (chapter weights are keyed by slug, not pk).
    """

    slug = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=160)
    order = models.PositiveSmallIntegerField(unique=True)
    subject_area = models.CharField(
        max_length=16, choices=SubjectArea.choices, blank=True
    )

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.order}. {self.name}"


class Question(models.Model):
    """A single bank question.

    Owns enough metadata for ``QuestionPicker`` to allocate it under chapter
    weights and difficulty profiles: ``chapter`` (FK), ``cognitive_level``,
    ``section``, ``qtype``, ``marks``. ``answer`` is stored alongside but is
    omitted by ``QuestionSerializer``; an answer-revealing serializer + its
    access rule will land with the answer-key endpoint (Slice 9).
    """

    school = models.ForeignKey(
        School,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="questions",
    )
    chapter = models.ForeignKey(
        Chapter,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="questions",
    )
    section = models.CharField(max_length=4, choices=Section.choices)
    qtype = models.CharField(max_length=20, choices=QuestionType.choices)
    marks = models.PositiveSmallIntegerField()
    cognitive_level = models.CharField(
        max_length=2, choices=CognitiveLevel.choices, default=CognitiveLevel.REMEMBER
    )
    text = models.TextField()
    # For MCQ: list of {"label": "A", "text": "..."} options. Empty otherwise.
    options = models.JSONField(default=list, blank=True)
    # Full PaperDocumentV1 `content` shape (stem, assertion/reason, passage/subparts,
    # choices, options, assets). Empty dict means "no structured content yet";
    # PaperDocumentBuilder falls back to building {stem: [text]} from `text`.
    content = models.JSONField(default=dict, blank=True)
    # Freeform LLM-emitted topic strings. No Topic model in V1.
    topic_names = models.JSONField(default=list, blank=True)
    answer = models.TextField(blank=True)
    # Set True automatically by Paper.approve for every referenced question.
    # See ADR-0002. NOT a picker gate — parse_quality is.
    verified = models.BooleanField(default=False)
    # Parser self-assessment. Picker draws from clean+partial; broken is excluded.
    # See ADR-0002.
    parse_quality = models.CharField(
        max_length=8, choices=ParseQuality.choices, default=ParseQuality.PARTIAL
    )
    # Slice 5 — ingestion enrichment flags
    has_diagram = models.BooleanField(default=False)
    is_numerical = models.BooleanField(default=False)
    diagram = models.FileField(upload_to="diagrams/", null=True, blank=True)
    # MD5 of normalised question text — used for de-duplication on re-ingest.
    source_hash = models.CharField(max_length=32, blank=True, db_index=True)
    # Source provenance — maps to PaperDocumentV1 `source` object.
    source_type = models.CharField(
        max_length=32, blank=True, default="previous_year_paper"
    )
    source_name = models.CharField(max_length=160, blank=True)
    source_file_name = models.CharField(max_length=160, blank=True)
    source_page_number = models.PositiveSmallIntegerField(null=True, blank=True)
    source_original_qnum = models.CharField(max_length=16, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["section", "id"]

    def __str__(self):
        return f"[{self.section}/{self.marks}m] {self.text[:60]}"
