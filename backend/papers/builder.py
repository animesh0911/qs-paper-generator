"""Paper assembly coordinator.

PaperBuilder.assemble() is the single entry point. It builds a PaperTemplate
from a preset, runs the QuestionPicker, persists a Paper + PaperQuestion rows,
maps the result to PaperDocumentV1, and returns both as an AssemblyResult.

Callers (view, tests) pick `.paper` or `.document` as needed.
"""

import base64
import logging
from dataclasses import dataclass

from django.db import transaction
from django.db.models import Q

from bank.models import GeneratedQuestionCandidate, IngestionJob, Question

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


def _decode_source_file_key(value: str) -> str:
    """Decode the URL-safe source_file token emitted by bank.sources."""
    try:
        padded = value + "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode(padded.encode()).decode()
    except Exception:  # noqa: BLE001 - stale/hand-edited browser state is ignored.
        return ""


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
        preferred_source_keys: list[str] | None = None,
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
            preferred_question_ids=self._preferred_question_ids(
                user, preferred_source_keys or []
            ),
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
    def _preferred_question_ids(user, source_keys: list[str]) -> set[int]:
        """Resolve generate-page source selections into bank Question ids.

        Source keys are intentionally opaque to the frontend: ``upload:<id>``
        means questions created by one teacher PDF upload, ``ai_batch:<id>``
        means accepted questions imported from one AI generation session, and
        ``source_file:<token>`` means tagged bank rows from one committed source
        file (for example a 2026 CBSE paper). Unknown or cross-school keys are
        ignored so stale browser state never breaks paper assembly.
        """
        upload_ids: list[int] = []
        ai_batch_ids: list[int] = []
        source_file_names: list[str] = []
        for key in source_keys:
            prefix, _, raw_value = key.partition(":")
            if prefix == "source_file":
                source_file_name = _decode_source_file_key(raw_value)
                if source_file_name:
                    source_file_names.append(source_file_name)
                continue
            if not raw_value.isdigit():
                continue
            if prefix == "upload":
                upload_ids.append(int(raw_value))
            elif prefix == "ai_batch":
                ai_batch_ids.append(int(raw_value))

        question_ids: set[int] = set()
        if upload_ids:
            valid_job_ids = IngestionJob.objects.filter(
                pk__in=upload_ids,
                school=getattr(user, "school", None),
            ).values_list("pk", flat=True)
            question_ids.update(
                Question.objects.filter(ingestion_job_id__in=valid_job_ids).values_list(
                    "pk", flat=True
                )
            )
        if ai_batch_ids:
            question_ids.update(
                GeneratedQuestionCandidate.objects.filter(
                    batch_id__in=ai_batch_ids,
                    batch__created_by=user,
                    batch__school=getattr(user, "school", None),
                    question_id__isnull=False,
                ).values_list("question_id", flat=True)
            )
        if source_file_names:
            question_ids.update(
                Question.objects.filter(
                    Q(school__isnull=True) | Q(school=getattr(user, "school", None)),
                    source_file_name__in=source_file_names,
                    parse_quality__in=["clean", "partial"],
                ).values_list("pk", flat=True)
            )
        return question_ids

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
