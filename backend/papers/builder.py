"""Paper assembly coordinator.

PaperBuilder.assemble() is the single entry point. It builds a PaperTemplate
from a preset, runs the QuestionPicker, persists a Paper + PaperQuestion rows,
maps the result to PaperDocumentV1, and returns both as an AssemblyResult.

Callers (view, tests) pick `.paper` or `.document` as needed.
"""

from dataclasses import dataclass

from django.db import transaction

from .document import PaperDocumentBuilder
from .models import Paper, PaperQuestion
from .picker import DEFAULT_DIFFICULTY, FilledTemplate, PaperOptions, QuestionPicker
from .template import TemplateBuilder


@dataclass
class AssemblyResult:
    paper: Paper
    document: dict  # PaperDocumentV1


class PaperBuilder:
    def assemble(
        self,
        user,
        title: str = "Science — Practice Paper",
        preset: str = "board",
        chapter_slugs: list[str] | None = None,
        weights: dict[str, float] | None = None,
        difficulty: str = DEFAULT_DIFFICULTY,
        reuse_question_ids: list[int] | None = None,
    ) -> AssemblyResult:
        template = TemplateBuilder().build(preset)
        opts = PaperOptions(
            template=template,
            chapter_slugs=list(chapter_slugs or []),
            weights=weights,
            difficulty=difficulty,
            # Freshness is scoped to the teacher who builds the paper.
            requesting_user=user,
            reuse_question_ids=set(reuse_question_ids or []),
        )
        result = QuestionPicker().select(opts)
        paper = self._persist(user, title, result)
        document = PaperDocumentBuilder().build(paper, result, opts)
        paper.document = document
        paper.save(update_fields=["document"])
        return AssemblyResult(paper=paper, document=document)

    @transaction.atomic
    def _persist(self, user, title: str, result: FilledTemplate) -> Paper:
        template = result.template
        paper = Paper.objects.create(
            created_by=user,
            school=getattr(user, "school", None),
            title=title,
            total_marks=template.total_marks,
            report=result.report.to_dict(),
        )

        rows = []
        for i, (slot, qid) in enumerate(zip(template.slots, result.question_ids)):
            if qid is None:
                continue
            rows.append(
                PaperQuestion(
                    paper=paper,
                    question_id=qid,
                    order=i + 1,
                    section=slot.section,
                    or_group=slot.or_group,
                )
            )
        if rows:
            PaperQuestion.objects.bulk_create(rows)
        return paper
