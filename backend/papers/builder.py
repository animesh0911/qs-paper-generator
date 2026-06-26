"""Paper assembly coordinator.

PaperBuilder.assemble() is the single entry point. It builds a PaperTemplate
from a preset, runs the QuestionPicker, persists a Paper + PaperQuestion rows,
maps the result to PaperDocumentV1, and returns both as an AssemblyResult.

Callers (view, tests) pick `.paper` or `.document` as needed.
"""

import logging
from dataclasses import dataclass

from django.db import transaction

from .answer_document import build_answer_document
from .document import PaperDocumentBuilder
from .document_contract import PaperDocumentContractError, validate_paper_document
from .models import Paper, PaperFormat, PaperQuestion
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
        format_id: str | None = None,
    ) -> AssemblyResult:
        paper_format: PaperFormat | None = None
        if format_id:
            paper_format = PaperFormat.objects.get(format_id=format_id, is_active=True)
            preset = paper_format.preset_name

        template = TemplateBuilder().build(preset)
        opts = PaperOptions(
            template=template,
            chapter_slugs=list(chapter_slugs or []),
            weights=weights,
            difficulty=difficulty,
            # Freshness is scoped to the teacher who builds the paper.
            requesting_user=user,
            reuse_question_ids=set(reuse_question_ids or []),
            format_id=format_id,
        )
        result = QuestionPicker().select(opts)
        paper = self._persist(user, title, result)
        document = PaperDocumentBuilder().build(paper, result, opts, paper_format)
        self._guard_contract(paper, document)
        paper.document = document
        # The answer document is keyed by slot id, so it is built from the
        # finished document (which owns slot ids), not from the raw template.
        paper.answer_document = build_answer_document(paper)
        paper.save(update_fields=["document", "answer_document"])
        return AssemblyResult(paper=paper, document=document)

    @staticmethod
    def _guard_contract(paper: Paper, document: dict) -> None:
        """Fail loudly if the built document violates the v1 contract.

        The builder is meant to emit a contract-valid PaperDocument; if it does
        not, that is a server bug we want surfaced (logged + raised) here rather
        than shipped to the editor as the opaque "Unable to open paper".
        """
        errors = validate_paper_document(document)
        if errors:
            logging.getLogger(__name__).error(
                "PaperDocument contract violation for paper %s: %s",
                paper.pk,
                errors,
            )
            raise PaperDocumentContractError(errors)

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
