"""GenerationBatch workflow module.

This module owns the lifecycle rules for bulk AI Question generation. HTTP views
and cron commands are adapters: they validate/serialize transport data, then call
this module for state transitions, locking, paid-call guards, candidate
persistence, and GeneratedQuestionCandidate import into the Question bank.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from corpus.retrieval import ChapterMapContextAssembler, TextbookRetrievalRequest

from .generation import (
    DIFFICULTY_TARGETS_BY_PRESET,
    LangChainQuestionGenerator,
    QuestionGenerationRequest,
    validate_generated_questions,
)
from .models import (
    ACTIVE_GENERATION_BATCH_STATUSES,
    AnswerSource,
    Chapter,
    GeneratedQuestionCandidate,
    GeneratedQuestionCandidateStatus,
    GenerationBatch,
    GenerationBatchStatus,
    ParseQuality,
    Question,
    QuestionType,
    Section,
    SourceType,
)

RECLAIM_RUNNING_AFTER = timedelta(minutes=10)


class GenerationBatchWorkflowError(Exception):
    """Base class for lifecycle errors callers can map to transport responses."""

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


class ActiveGenerationBatchError(GenerationBatchWorkflowError):
    def __init__(self, batch: GenerationBatch):
        self.batch = batch
        super().__init__(f"Teacher already has active generation batch #{batch.pk}.")


class GenerationBatchConflict(GenerationBatchWorkflowError):
    pass


class GenerationBatchBadSelection(GenerationBatchWorkflowError):
    pass


@dataclass(frozen=True)
class ProcessedGenerationBatch:
    batch: GenerationBatch
    candidate_count: int


def build_generator():
    """Return the production generator; tests may inject another factory."""
    return LangChainQuestionGenerator()


def build_context_assembler():
    """Return corpus-owned selected-topic context assembler."""
    return ChapterMapContextAssembler()


def drainable_filter(now) -> Q:
    return Q(status=GenerationBatchStatus.QUEUED) | Q(
        status__in=(
            GenerationBatchStatus.GENERATING_QUESTIONS,
            GenerationBatchStatus.VALIDATING,
        ),
        updated_at__lt=now - RECLAIM_RUNNING_AFTER,
    )


def queue_generation_batch(user, data: dict) -> GenerationBatch:
    """Create one teacher-owned queued GenerationBatch, enforcing active-batch rules."""
    GenerationBatch.expire_ready_batches()
    with transaction.atomic():
        locked_user = type(user).objects.select_for_update().get(pk=user.pk)
        active = GenerationBatch.objects.filter(
            created_by=locked_user,
            status__in=ACTIVE_GENERATION_BATCH_STATUSES,
        ).first()
        if active:
            raise ActiveGenerationBatchError(active)

        chapters_for_request = list(
            Chapter.objects.filter(slug__in=data["chapter_slugs"]).order_by("order")
        )
        batch = GenerationBatch.objects.create(
            school=locked_user.school,
            created_by=locked_user,
            chapter_map_node_ids=list(data["chapter_map_node_ids"]),
            topic_names=list(data["topic_names"]),
            difficulty_preset=data["difficulty_preset"],
            requested_count=data["count"],
        )
        batch.chapters.set(chapters_for_request)
        return batch


def get_owned_generation_batch(user, batch_id, *, lock=False):
    """Return a teacher-owned GenerationBatch, or None without leaking existence."""
    queryset = GenerationBatch.objects.filter(
        pk=batch_id,
        created_by=user,
        school=user.school,
    ).prefetch_related("chapters")
    if lock:
        queryset = queryset.select_for_update()
    return queryset.first()


def claim_generation_batch(batch_id: int) -> tuple[GenerationBatch | None, bool]:
    """Atomically claim a queued batch, or flag stale in-flight work as reclaimed."""
    with transaction.atomic():
        batch = (
            GenerationBatch.objects.select_for_update(skip_locked=True)
            .filter(drainable_filter(timezone.now()), pk=batch_id)
            .first()
        )
        if batch is None:
            return None, False
        reclaimed = batch.status != GenerationBatchStatus.QUEUED
        batch.status = GenerationBatchStatus.GENERATING_QUESTIONS
        batch.save(update_fields=["status", "updated_at"])
        return batch, reclaimed


def process_generation_batch(
    batch: GenerationBatch,
    *,
    reclaimed: bool,
    generator_factory: Callable[[], object] = build_generator,
    context_assembler_factory: Callable[[], object] = build_context_assembler,
) -> ProcessedGenerationBatch:
    """Generate and persist valid candidates, or mark the batch failed."""
    if reclaimed:
        batch.status = GenerationBatchStatus.FAILED
        batch.error = "Reclaimed after an interrupted drain run; not retried."
        batch.save(update_fields=["status", "error", "updated_at"])
        raise GenerationBatchConflict(batch.error)

    try:
        request = request_from_batch(batch)
        grounding_manifest = grounding_manifest_from_batch(
            batch,
            context_assembler=(
                context_assembler_factory() if batch.chapter_map_node_ids else None
            ),
        )
        if grounding_manifest:
            request = request_from_batch(batch, grounding_manifest)
        generated = generator_factory().generate(request)
        batch.status = GenerationBatchStatus.VALIDATING
        batch.save(update_fields=["status", "updated_at"])

        result = validate_generated_questions({"questions": generated}, request)
        if not result.valid_questions:
            raise ValueError("No valid generated candidates.")

        GeneratedQuestionCandidate.objects.bulk_create(
            [
                GeneratedQuestionCandidate(
                    batch=batch,
                    payload=payload,
                    grounding_manifest=grounding_manifest or {},
                )
                for payload in result.valid_questions
            ]
        )
    except Exception as exc:
        batch.status = GenerationBatchStatus.FAILED
        batch.error = f"{type(exc).__name__}: {exc}"
        batch.save(update_fields=["status", "error", "updated_at"])
        raise GenerationBatchConflict(batch.error) from exc

    batch.status = GenerationBatchStatus.READY_FOR_REVIEW
    batch.error = ""
    batch.ready_at = timezone.now()
    batch.save(update_fields=["status", "error", "ready_at", "updated_at"])
    return ProcessedGenerationBatch(
        batch=batch,
        candidate_count=len(result.valid_questions),
    )


def request_from_batch(
    batch: GenerationBatch,
    grounding_manifest: dict[str, object] | None = None,
) -> QuestionGenerationRequest:
    chapter_slugs = tuple(
        batch.chapters.order_by("order").values_list("slug", flat=True)
    )
    return QuestionGenerationRequest(
        chapter_slugs=chapter_slugs,
        chapter_map_node_ids=tuple(batch.chapter_map_node_ids),
        topic_names=tuple(batch.topic_names),
        difficulty_targets=DIFFICULTY_TARGETS_BY_PRESET.get(batch.difficulty_preset),
        grounding_manifest=grounding_manifest,
        count=batch.requested_count,
    )


def grounding_manifest_from_batch(
    batch: GenerationBatch,
    *,
    context_assembler=None,
) -> dict[str, object] | None:
    node_ids = tuple(batch.chapter_map_node_ids or [])
    if not node_ids:
        return None
    chapters = list(batch.chapters.order_by("order"))
    if len(chapters) != 1:
        raise ValueError("Grounded generation requires exactly one Chapter.")
    assembler = context_assembler or build_context_assembler()
    context = assembler.retrieve(
        TextbookRetrievalRequest(
            chapter=chapters[0],
            chapter_map_node_ids=node_ids,
        )
    )
    if not context.results:
        raise ValueError("No grounded NCERT context exists for selected topic.")
    return context.to_generation_manifest()


def accept_generation_batch_selection(
    user,
    batch_id,
    accepted_candidate_ids: set[int],
) -> GenerationBatch | None:
    """Import selected ready candidates and reject the rest of the batch."""
    with transaction.atomic():
        batch = get_owned_generation_batch(user, batch_id, lock=True)
        if batch is None:
            return None
        if batch.expire_if_stale():
            raise GenerationBatchConflict("Generation batch has expired.")
        if batch.status != GenerationBatchStatus.READY_FOR_REVIEW:
            raise GenerationBatchConflict("Generation batch is not ready for review.")

        candidates = list(
            batch.candidates.select_for_update().filter(
                status=GeneratedQuestionCandidateStatus.READY_FOR_REVIEW
            )
        )
        if not candidates:
            raise GenerationBatchConflict(
                "Generation batch has no candidates to accept."
            )

        ready_candidate_ids = {candidate.pk for candidate in candidates}
        unknown_ids = accepted_candidate_ids - ready_candidate_ids
        if unknown_ids:
            raise GenerationBatchBadSelection(
                "Selection includes candidates outside this review batch."
            )

        now = timezone.now()
        for candidate in candidates:
            if candidate.pk in accepted_candidate_ids:
                candidate.question = question_from_candidate(candidate, batch)
                candidate.status = GeneratedQuestionCandidateStatus.ACCEPTED
                candidate.accepted_at = now
                candidate.save(
                    update_fields=["question", "status", "accepted_at", "updated_at"]
                )
            else:
                candidate.status = GeneratedQuestionCandidateStatus.REJECTED
                candidate.rejected_at = now
                candidate.save(update_fields=["status", "rejected_at", "updated_at"])

        batch.status = GenerationBatchStatus.ACCEPTED
        batch.accepted_at = now
        batch.error = ""
        batch.save(update_fields=["status", "accepted_at", "error", "updated_at"])
        return batch


def question_from_candidate(candidate, batch):
    """Convert one accepted GeneratedQuestionCandidate payload into a bank Question."""
    payload = candidate.payload
    chapter = Chapter.objects.get(slug=payload["chapter_slug"])
    return Question.objects.create(
        school=batch.school,
        chapter=chapter,
        section=section_for_generated_qtype(payload["qtype"]),
        qtype=payload["qtype"],
        marks=payload["marks"],
        cognitive_level=payload["cognitive_level"],
        text=payload["raw_text"],
        options=options_from_generated_content(payload),
        content=payload["content"],
        topic_names=list(payload["topic_names"]),
        answer=payload["answer"],
        answer_source=AnswerSource.GENERATED_UNVERIFIED,
        verified=False,
        parse_quality=ParseQuality.CLEAN,
        source_type=SourceType.AI_GENERATED,
        source_name=payload.get("source", {}).get("name", ""),
    )


def section_for_generated_qtype(qtype):
    return {
        QuestionType.MCQ: Section.A,
        QuestionType.VSA: Section.B,
        QuestionType.SA: Section.C,
        QuestionType.LA: Section.D,
    }[qtype]


def options_from_generated_content(payload):
    if payload["qtype"] != QuestionType.MCQ:
        return []
    options = payload.get("content", {}).get("options", [])
    flattened = []
    for option in options:
        if not isinstance(option, dict):
            continue
        content = option.get("content", [])
        text = " ".join(
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        ).strip()
        flattened.append({"label": option.get("label", ""), "text": text})
    return flattened
