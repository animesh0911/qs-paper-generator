"""GenerationBatch workflow module.

This module owns the lifecycle rules for bulk AI Question generation. HTTP views
and cron commands are adapters: they validate/serialize transport data, then call
this module for state transitions, locking, paid-call guards, candidate
persistence, and GeneratedQuestionCandidate import into the Question bank.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from ai_services.errors import friendly_llm_error
from corpus.retrieval import ChapterMapContextAssembler, TextbookRetrievalRequest
from workflows.checkpointer import get_checkpointer

from .extraction import _fingerprint
from .generation import (
    DIFFICULTY_TARGETS_BY_PRESET,
    LangChainQuestionGenerator,
    QuestionGenerationRequest,
)
from .models import (
    ACTIVE_GENERATION_BATCH_STATUSES,
    DISCARDABLE_GENERATION_BATCH_STATUSES,
    MAX_ACTIVE_GENERATION_BATCHES_PER_TEACHER,
    AnswerSource,
    Chapter,
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
    """Enqueue one teacher-owned GenerationBatch into the FIFO queue.

    Multiple batches may queue at once; the sequential drain worker processes
    them one at a time in ``created_at`` order. A per-teacher cap on
    simultaneously non-terminal batches bounds paid model-call runaway (Rule 13).
    """
    GenerationBatch.expire_ready_batches()
    with transaction.atomic():
        locked_user = type(user).objects.select_for_update().get(pk=user.pk)
        active_count = GenerationBatch.objects.filter(
            created_by=locked_user,
            status__in=ACTIVE_GENERATION_BATCH_STATUSES,
        ).count()
        if active_count >= MAX_ACTIVE_GENERATION_BATCHES_PER_TEACHER:
            raise GenerationBatchConflict(
                "Generation queue is full; review or discard a batch first."
            )

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
    reclaimed: bool = False,
    generator_factory: Callable[[], object] = build_generator,
    context_assembler_factory: Callable[[], object] = build_context_assembler,
    checkpointer_cm: Callable[[], AbstractContextManager] = get_checkpointer,
) -> ProcessedGenerationBatch:
    """Drive the batch's LangGraph thread to completion and persist candidates.

    The checkpoint — not the ledger — is the truth about how far the thread
    got: a batch reclaimed after an interrupted run *resumes* from its last
    checkpoint (the post-``generate`` snapshot) instead of re-billing the model,
    so ``reclaimed`` no longer fails the batch. Terminal generator/validation
    errors flip the batch to ``FAILED``.
    """
    del reclaimed  # Resume is checkpoint-driven; no special-casing needed.
    if not batch.thread_id:
        batch.thread_id = uuid4().hex
        batch.save(update_fields=["thread_id", "updated_at"])

    try:
        final = _run_generation_graph(
            batch,
            generator_factory=generator_factory,
            context_assembler_factory=context_assembler_factory,
            checkpointer_cm=checkpointer_cm,
        )
    except Exception as exc:
        batch.status = GenerationBatchStatus.FAILED
        # Sanitise: a raw provider error (e.g. a 402 credits JSON dump) must not
        # be persisted onto the teacher-visible batch — see ai_services.errors.
        batch.error = friendly_llm_error(exc)
        batch.save(update_fields=["status", "error", "updated_at"])
        raise GenerationBatchConflict(batch.error) from exc

    batch.status = GenerationBatchStatus.READY_FOR_REVIEW
    batch.error = ""
    batch.ready_at = timezone.now()
    batch.save(update_fields=["status", "error", "ready_at", "updated_at"])
    return ProcessedGenerationBatch(
        batch=batch,
        candidate_count=final["valid_count"],
    )


def _run_generation_graph(
    batch: GenerationBatch,
    *,
    generator_factory: Callable[[], object],
    context_assembler_factory: Callable[[], object],
    checkpointer_cm: Callable[[], AbstractContextManager],
) -> dict:
    """Run the batch's thread fresh, resume it, or read back a finished thread.

    No checkpoint means a fresh invoke with the initial state; pending tasks
    mean a resume (``input=None`` continues from the last checkpoint); a
    finished thread (a crash landed between the graph completing and the ledger
    update) only needs its values read back — re-invoking would re-bill the
    model. ``durability="sync"`` makes the post-``generate`` checkpoint a
    synchronous write, so a kill can never lose a paid call.
    """
    # Imported here to break the import cycle with ``workflows.generation``,
    # which imports this module's request/grounding helpers.
    from workflows.generation import build_generation_graph

    with checkpointer_cm() as checkpointer:
        graph = build_generation_graph(
            checkpointer,
            generator_factory=generator_factory,
            context_assembler_factory=context_assembler_factory,
        )
        config = {"configurable": {"thread_id": batch.thread_id}}
        snapshot = graph.get_state(config)
        if snapshot.values and not snapshot.next:
            return snapshot.values
        state = None if snapshot.values else {"batch_id": batch.pk}
        return graph.invoke(state, config, durability="sync")


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


def discard_generation_batch(user, batch_id) -> GenerationBatch | None:
    """Discard a teacher-owned batch so a fresh one can take its place.

    Allowed from queued/ready/failed/expired only — discarding while the drain
    worker is mid-run would race it, so in-flight batches are rejected. Ready
    candidates are marked discarded; no Question rows are created.
    """
    with transaction.atomic():
        batch = get_owned_generation_batch(user, batch_id, lock=True)
        if batch is None:
            return None
        batch.expire_if_stale()
        if batch.status not in DISCARDABLE_GENERATION_BATCH_STATUSES:
            raise GenerationBatchConflict(
                "Generation batch cannot be discarded while it is in progress."
            )

        now = timezone.now()
        batch.candidates.filter(
            status=GeneratedQuestionCandidateStatus.READY_FOR_REVIEW
        ).update(
            status=GeneratedQuestionCandidateStatus.DISCARDED,
            updated_at=now,
        )
        batch.status = GenerationBatchStatus.DISCARDED
        batch.discarded_at = now
        batch.error = ""
        batch.save(update_fields=["status", "discarded_at", "error", "updated_at"])
        return batch


def requeue_generation_batch(user, batch_id) -> GenerationBatch | None:
    """Re-queue a failed teacher-owned batch so the drainer runs it again.

    Only a ``FAILED`` batch is retryable: an in-flight or ready batch has no
    business being reset, and re-queueing a successful one would re-bill for no
    reason (Rule 13). The graph ``thread_id`` is preserved, so a batch that
    failed *after* the model already produced candidates resumes from that
    checkpoint instead of paying for a second generation. The paid work happens
    out-of-request in ``drain_generation_batches`` — this only flips the row.
    """
    with transaction.atomic():
        batch = get_owned_generation_batch(user, batch_id, lock=True)
        if batch is None:
            return None
        if batch.status != GenerationBatchStatus.FAILED:
            raise GenerationBatchConflict(
                "Only a failed generation batch can be retried."
            )
        batch.status = GenerationBatchStatus.QUEUED
        batch.error = ""
        batch.save(update_fields=["status", "error", "updated_at"])
        return batch


def list_generation_batches(user, *, limit: int = 20):
    """Return a teacher's batches, FIFO-ordered, for the queue view."""
    return list(
        GenerationBatch.objects.filter(created_by=user, school=user.school)
        .prefetch_related("chapters")
        .annotate(candidate_count_annotation=Count("candidates"))
        .order_by("created_at")[:limit]
    )


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
        content=content_from_generated_candidate(candidate, batch),
        topic_names=list(payload["topic_names"]),
        answer=payload["answer"],
        answer_source=AnswerSource.GENERATED_UNVERIFIED,
        verified=False,
        parse_quality=ParseQuality.CLEAN,
        source_type=SourceType.AI_GENERATED,
        source_name=payload.get("source", {}).get("name", ""),
        source_hash=_fingerprint(payload["raw_text"]),
    )


def content_from_generated_candidate(candidate, batch) -> dict:
    """Preserve generated-question grounding/audit data with the bank row."""
    content = copy.deepcopy(candidate.payload["content"])
    if not isinstance(content, dict):
        return {}

    provenance = generated_candidate_provenance(candidate, batch)
    if provenance:
        content["__provenance"] = provenance
    return content


def generated_candidate_provenance(candidate, batch) -> dict:
    """Return serializable provenance for an accepted AI candidate."""
    payload = candidate.payload
    manifest = candidate.grounding_manifest or {}
    question_citation_ids = [
        item
        for item in payload.get("question_citation_ids", [])
        if isinstance(item, str)
    ]
    answer_citation_ids = [
        item for item in payload.get("answer_citation_ids", []) if isinstance(item, str)
    ]
    citation_ids = set(question_citation_ids) | set(answer_citation_ids)
    excerpts = [
        excerpt
        for excerpt in manifest.get("excerpts", [])
        if isinstance(excerpt, dict) and excerpt.get("citation_id") in citation_ids
    ]
    provenance = {
        "kind": "ai_generated",
        "batchId": batch.pk,
        "candidateId": candidate.pk,
        "questionCitationIds": question_citation_ids,
        "answerCitationIds": answer_citation_ids,
    }
    if excerpts:
        provenance["groundingExcerpts"] = excerpts
    return provenance


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
        content = option.get("content") or []
        if not isinstance(content, list):
            content = []
        text = " ".join(
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        ).strip()
        flattened.append({"label": option.get("label", ""), "text": text})
    return flattened
