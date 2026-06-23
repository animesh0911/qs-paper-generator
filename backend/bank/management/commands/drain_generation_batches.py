"""drain_generation_batches — drive bulk Question generation out-of-request.

The HTTP endpoint creates a ``GenerationBatch`` row and returns 202 without
calling an LLM. This command is the Postgres-backed adapter over the
``generation_batches`` workflow module.

COST (Rule 13): a real queued batch is a paid model call. ``--dry-run`` lists
work and exits without claiming rows or building the generator.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone

from bank.generation_batches import (
    GenerationBatchConflict,
    build_context_assembler,
    build_generator,
    claim_generation_batch,
    drainable_filter,
    process_generation_batch,
)
from bank.models import GenerationBatch


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
        drainable = GenerationBatch.objects.filter(
            drainable_filter(timezone.now())
        ).order_by("created_at")
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
            batch, reclaimed = claim_generation_batch(batch_id)
            if batch is not None:
                self._process(batch, reclaimed=reclaimed)

    def _process(self, batch: GenerationBatch, *, reclaimed: bool) -> None:
        """Generate and persist valid candidates, recording terminal failures."""
        try:
            result = process_generation_batch(
                batch,
                reclaimed=reclaimed,
                generator_factory=build_generator,
                context_assembler_factory=build_context_assembler,
            )
        except GenerationBatchConflict as exc:
            if reclaimed:
                self.stderr.write(
                    f"Generation batch #{batch.pk} failed (interrupted run)."
                )
            else:
                self.stderr.write(f"Generation batch #{batch.pk} failed: {exc.detail}")
            return

        self.stdout.write(
            f"Generation batch #{batch.pk} ready: "
            f"{result.candidate_count} candidate(s)."
        )
