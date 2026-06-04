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
from django.db import models, transaction

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

    @transaction.atomic
    def approve(self) -> None:
        """Lock the paper and mark every referenced question verified (ADR-0002).

        ``verified`` means "a human saw this question in an approved paper and did
        not reject it", so the referenced set is the final document's selected
        questions (post-edit), falling back to the assembly ``PaperQuestion`` rows
        when there is no document. Idempotent: re-running flips nothing new.

        Approval is also the moment a question counts as *used* (Slice 10): the
        same referenced set is recorded as ``QuestionUsage`` so the picker can
        keep later papers fresh.
        """
        self.status = PaperStatus.APPROVED
        self.save(update_fields=["status"])
        qids = self._referenced_question_ids()
        if qids:
            Question.objects.filter(pk__in=qids).update(verified=True)
            self._record_usage(qids)

    def _record_usage(self, qids: set[int]) -> None:
        """Record one QuestionUsage per referenced question for this paper.

        Scoped to the paper's teacher (``created_by``) so freshness is per the
        teacher who builds the papers. ``ignore_conflicts`` keeps approval
        idempotent: re-approving the same paper adds no duplicate usage."""
        QuestionUsage.objects.bulk_create(
            [
                QuestionUsage(
                    question_id=qid,
                    paper=self,
                    used_by=self.created_by,
                    school=self.school,
                )
                for qid in qids
            ],
            ignore_conflicts=True,
        )

    def _referenced_question_ids(self) -> set[int]:
        """PKs of the questions selected into this paper (not alternates)."""
        document = self.document
        if isinstance(document, dict):
            ids: set[int] = set()
            for section in document.get("paper", {}).get("sections", []):
                for slot in section.get("slots", []):
                    pk = _pk_from_question_id(slot.get("selectedQuestionId"))
                    if pk is not None:
                        ids.add(pk)
            if ids:
                return ids
        return set(self.items.values_list("question_id", flat=True))


def _pk_from_question_id(question_id) -> int | None:
    """Parse a contract ``selectedQuestionId`` (``"q_{pk}"``) back to a PK."""
    if isinstance(question_id, str) and question_id.startswith("q_"):
        try:
            return int(question_id[2:])
        except ValueError:
            return None
    return None


class PaperFormat(models.Model):
    """Canonical paper format definition owned and seeded by the backend.

    Maps a stable ``format_id`` slug (used in ``paper_document.v1``) to the
    internal ``preset_name`` that drives slot layout, plus the page/layout data
    the doc builder copies verbatim into the contract ``format`` object.
    Frontend never invents format rules — it picks from this table.
    """

    format_id = models.SlugField(unique=True, max_length=100)
    name = models.CharField(max_length=255)
    preset_name = models.CharField(max_length=50)
    page = models.JSONField()
    layout = models.JSONField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def format_data(self) -> dict:
        return {"id": self.format_id, "page": self.page, "layout": self.layout}


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


class QuestionUsage(models.Model):
    """One record that a question was used in an approved paper (Slice 10).

    Written by ``Paper.approve`` for every referenced question. The picker
    counts these per teacher to deprioritise recently-used questions, keeping
    successive papers fresh against the finite bank. ``school`` mirrors the
    paper's tenant for parity with the other models; freshness is scoped by
    ``used_by`` today.
    """

    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="usages"
    )
    paper = models.ForeignKey(
        Paper, on_delete=models.CASCADE, related_name="question_usages"
    )
    used_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="question_usages",
    )
    school = models.ForeignKey(
        School, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # A question is used at most once per paper; re-approving is a no-op.
        unique_together = [("question", "paper")]
        indexes = [models.Index(fields=["used_by", "question"])]
