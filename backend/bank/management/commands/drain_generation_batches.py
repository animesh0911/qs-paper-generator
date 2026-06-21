"""drain_generation_batches — drive bulk Question generation out-of-request.

The HTTP endpoint creates a ``GenerationBatch`` row and returns 202 without
calling an LLM. This command is the Postgres-backed drainer: cron claims queued
batches, asks the ``QuestionGenerator`` seam for payloads, validates the output
with ``generated_question_gate``, and stores only valid
``GeneratedQuestionCandidate`` rows.

COST (Rule 13): a real queued batch is a paid model call. ``--dry-run`` lists
work and exits without claiming rows or building the generator.
"""

from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from bank.generation import (
    DIFFICULTY_TARGETS_BY_PRESET,
    LangChainQuestionGenerator,
    QuestionGenerationRequest,
    validate_generated_questions,
)
from bank.models import (
    GeneratedQuestionCandidate,
    GenerationBatch,
    GenerationBatchStatus,
)
from corpus.retrieval import ChapterMapContextAssembler, TextbookRetrievalRequest

RECLAIM_RUNNING_AFTER = timedelta(minutes=10)


def build_generator():
    """Return the production generator; tests monkeypatch this seam."""
    return LangChainQuestionGenerator()


def build_context_assembler():
    """Return corpus-owned selected-topic context assembler."""
    return ChapterMapContextAssembler()


def _drainable_filter(now) -> Q:
    return Q(status=GenerationBatchStatus.QUEUED) | Q(
        status__in=(
            GenerationBatchStatus.GENERATING_QUESTIONS,
            GenerationBatchStatus.VALIDATING,
        ),
        updated_at__lt=now - RECLAIM_RUNNING_AFTER,
    )


class Command(BaseCommand):
    help = (
        "Drive queued GenerationBatch rows: claim, generate, validate, persist "
        "valid candidates. Run on cron."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Max number of batches to process this run (default: all).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List queued batches and exit WITHOUT calling a model.",
        )

    def handle(self, *args, **options):
        GenerationBatch.expire_ready_batches()
        now = timezone.now()
        drainable = GenerationBatch.objects.filter(_drainable_filter(now)).order_by(
            "created_at"
        )
        if options["limit"]:
            drainable = drainable[: options["limit"]]
        batch_ids = list(drainable.values_list("pk", flat=True))

        if not batch_ids:
            self.stdout.write("No drainable generation batches.")
            return

        if options["dry_run"]:
            self.stdout.write(
                f"[dry-run] {len(batch_ids)} drainable generation batch(es) — "
                "each queued batch is a PAID model call. Not processing:"
            )
            for batch in GenerationBatch.objects.filter(pk__in=batch_ids):
                self.stdout.write(
                    f"  #{batch.pk} [{batch.status}] teacher={batch.created_by_id} "
                    f"count={batch.requested_count}"
                )
            return

        for batch_id in batch_ids:
            batch, reclaimed = self._claim(batch_id)
            if batch is not None:
                self._process(batch, reclaimed=reclaimed)

    @staticmethod
    def _claim(batch_id: int) -> tuple[GenerationBatch | None, bool]:
        """Atomically claim a queued batch, or fail stale in-flight work."""
        with transaction.atomic():
            batch = (
                GenerationBatch.objects.select_for_update(skip_locked=True)
                .filter(_drainable_filter(timezone.now()), pk=batch_id)
                .first()
            )
            if batch is None:
                return None, False
            reclaimed = batch.status != GenerationBatchStatus.QUEUED
            batch.status = GenerationBatchStatus.GENERATING_QUESTIONS
            batch.save(update_fields=["status", "updated_at"])
            return batch, reclaimed

    def _process(self, batch: GenerationBatch, *, reclaimed: bool) -> None:
        """Generate and persist valid candidates, recording terminal failures."""
        if reclaimed:
            batch.status = GenerationBatchStatus.FAILED
            batch.error = "Reclaimed after an interrupted drain run; not retried."
            batch.save(update_fields=["status", "error", "updated_at"])
            self.stderr.write(f"Generation batch #{batch.pk} failed (interrupted run).")
            return

        try:
            request = _request_from_batch(batch)
            grounding_manifest = _grounding_manifest_from_batch(batch)
            if grounding_manifest:
                request = _request_from_batch(batch, grounding_manifest)
            generated = build_generator().generate(request)
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
        except Exception as exc:  # noqa: BLE001 — record failure, keep draining
            batch.status = GenerationBatchStatus.FAILED
            batch.error = f"{type(exc).__name__}: {exc}"
            batch.save(update_fields=["status", "error", "updated_at"])
            self.stderr.write(f"Generation batch #{batch.pk} failed: {batch.error}")
            return

        batch.status = GenerationBatchStatus.READY_FOR_REVIEW
        batch.error = ""
        batch.ready_at = timezone.now()
        batch.save(update_fields=["status", "error", "ready_at", "updated_at"])
        self.stdout.write(
            f"Generation batch #{batch.pk} ready: "
            f"{len(result.valid_questions)} candidate(s)."
        )


def _request_from_batch(
    batch: GenerationBatch,
    grounding_manifest: dict[str, object] | None = None,
) -> QuestionGenerationRequest:
    chapter_slugs = tuple(
        batch.chapters.order_by("order").values_list("slug", flat=True)
    )
    return QuestionGenerationRequest(
        chapter_slugs=chapter_slugs,
        topic_names=tuple(batch.topic_names),
        difficulty_targets=DIFFICULTY_TARGETS_BY_PRESET.get(batch.difficulty_preset),
        grounding_manifest=grounding_manifest,
        count=batch.requested_count,
    )


def _grounding_manifest_from_batch(batch: GenerationBatch) -> dict[str, object] | None:
    node_ids = tuple(batch.chapter_map_node_ids or [])
    if not node_ids:
        return None
    chapters = list(batch.chapters.order_by("order"))
    if len(chapters) != 1:
        raise ValueError("Grounded generation requires exactly one Chapter.")
    context = build_context_assembler().retrieve(
        TextbookRetrievalRequest(
            chapter=chapters[0],
            chapter_map_node_ids=node_ids,
        )
    )
    if not context.results:
        raise ValueError("No grounded NCERT context exists for selected topic.")
    excerpts = []
    for result in context.results:
        chunk = result.chunk
        excerpts.append(
            {
                "citation_id": chunk.stable_chunk_id,
                "chapter_map_node_id": chunk.chapter_map_node.stable_node_id,
                "pages": list(
                    chunk.citation.get(
                        "pages", range(chunk.page_start, chunk.page_end + 1)
                    )
                ),
                "source_element_ids": list(
                    chunk.citation.get("source_element_ids", chunk.source_element_ids)
                ),
                "content_types": list(chunk.content_types),
                "text": chunk.text,
            }
        )
    return {
        "chapter_slug": chapters[0].slug,
        "requested_chapter_map_node_ids": list(node_ids),
        "included_chapter_map_node_ids": context.diagnostics.get(
            "included_chapter_map_node_ids", []
        ),
        "excerpts": excerpts,
        "unsupported_content_policy": (
            "Excluded by default: existing NCERT question/exercise chunks, "
            "picture-only chunks without captions, formula-only chunks, "
            "numerical/formula-only generation, and diagram-image generation."
        ),
        "diagnostics": dict(context.diagnostics),
    }
