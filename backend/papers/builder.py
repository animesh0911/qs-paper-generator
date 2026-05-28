"""Paper assembly coordinator.

The view calls PaperBuilder().assemble_document(), which persists a Paper
and returns the PaperDocumentV1 dict. assemble() is the lower-level entry
point used by tests and internal callers that only need the Paper.

_build_template() returns the PaperTemplate; _select() runs the QuestionPicker;
_persist() writes the Paper + PaperQuestion rows; PaperDocumentBuilder
maps the domain objects to the contract JSON.
"""
from django.db import transaction

from .template import PaperTemplate, TemplateBuilder
from .document import PaperDocumentBuilder
from .models import Paper, PaperQuestion
from .picker import DEFAULT_DIFFICULTY, FilledTemplate, PaperOptions, QuestionPicker


class PaperBuilder:
    def assemble(
        self,
        user,
        title: str = "Science — Practice Paper",
        preset: str = "board",
        chapter_slugs: list[str] | None = None,
        weights: dict[str, float] | None = None,
        difficulty: str = DEFAULT_DIFFICULTY,
    ) -> Paper:
        template = self._build_template(preset)
        result = self._select(template, chapter_slugs, weights, difficulty)
        return self._persist(user, title, result)

    def _build_template(self, preset: str) -> PaperTemplate:
        return TemplateBuilder().build(preset)

    def assemble_document(
        self,
        user,
        title: str = "Science — Practice Paper",
        preset: str = "board",
        chapter_slugs: list[str] | None = None,
        weights: dict[str, float] | None = None,
        difficulty: str = DEFAULT_DIFFICULTY,
    ) -> tuple[Paper, dict]:
        template = self._build_template(preset)
        opts = PaperOptions(
            template=template,
            chapter_slugs=list(chapter_slugs or []),
            weights=weights,
            difficulty=difficulty,
        )
        result = QuestionPicker().select(opts)
        paper = self._persist(user, title, result)
        document = PaperDocumentBuilder().build(paper, result, opts)
        paper.document = document
        paper.save(update_fields=["document"])
        return paper, document

    def _select(
        self,
        template: PaperTemplate,
        chapter_slugs: list[str] | None,
        weights: dict[str, float] | None,
        difficulty: str,
    ) -> FilledTemplate:
        return QuestionPicker().select(
            PaperOptions(
                template=template,
                chapter_slugs=list(chapter_slugs or []),
                weights=weights,
                difficulty=difficulty,
            )
        )

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
