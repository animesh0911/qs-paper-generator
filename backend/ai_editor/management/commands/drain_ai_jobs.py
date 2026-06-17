"""drain_ai_jobs — drive queued editor AI jobs out-of-request.

The job-creating endpoints (``ai_editor.views``) only persist a ``pending``
``AIJob`` row and return 202 — they make no model call inside the request. This
command is the drainer: run it on the platform's cron (no Celery, no Redis, no
always-on worker), the same Redis/Celery-free pattern as ``drain_ingestion_jobs``
(#104). Unlike ingestion's ~1-minute cadence, the editor drain is expected on a
short (few-second) interval because a teacher is waiting; V1 surfaces the
``pending`` state rather than promising sub-second replies.

Per job the drain:
1. **Claims** it atomically — ``select_for_update(skip_locked=True)`` flips
   ``pending``→``running`` so two overlapping drains can never both work (and
   double-bill, Rule 13) the same row.
2. **Cost-guards on revision** — if the job's ``base_revision`` no longer matches
   the paper's current ``revision``, the paper was edited while the job sat
   queued, so any proposal would be rejected on apply; the job is ``cancelled``
   with **no model call** (Rule 13).
3. **Dispatches** to the per-kind handler. The handlers are stubbed until #32
   (guardrail validators) and #34 (summary/review/edit flows) implement them —
   a stubbed kind fails its own job with a clear message and the drain keeps
   going. ``handlers`` is injectable so tests drive the full lifecycle without a
   model.

COST (Rule 13): a real handler is a PAID model call. ``--dry-run`` lists what
would run and exits without claiming or calling anything.
"""

from __future__ import annotations

from collections.abc import Callable

from django.core.management.base import BaseCommand
from django.db import transaction

from ai_editor.models import AIJob, AIJobKind, AIJobStatus


def _not_implemented(kind: str) -> Callable[[AIJob], dict]:
    def handler(_job: AIJob) -> dict:
        raise NotImplementedError(
            f"{kind} handler is not implemented yet (arrives with #32/#34)."
        )

    return handler


# Default handler registry: each kind is stubbed until its owning issue fills it.
# Injectable on the command instance (``cmd.handlers = {...}``) for tests.
STUB_HANDLERS: dict[str, Callable[[AIJob], dict]] = {
    kind.value: _not_implemented(kind.value) for kind in AIJobKind
}


class Command(BaseCommand):
    help = (
        "Drive pending AIJob rows: claim, cancel stale jobs, dispatch to the "
        "per-kind handler (paid when implemented). Run on cron."
    )

    # Per-kind handlers; overridable in tests to drive the lifecycle with no model.
    handlers: dict[str, Callable[[AIJob], dict]] = STUB_HANDLERS

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Max number of jobs to process this run (default: all).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List pending jobs and exit WITHOUT claiming or calling a model.",
        )

    def handle(self, *args, **options):
        pending = AIJob.objects.filter(status=AIJobStatus.PENDING).order_by(
            "created_at"
        )
        if options["limit"]:
            pending = pending[: options["limit"]]
        job_ids = list(pending.values_list("pk", flat=True))

        if not job_ids:
            self.stdout.write("No pending AI jobs.")
            return

        if options["dry_run"]:
            self.stdout.write(
                f"[dry-run] {len(job_ids)} pending job(s) — each implemented "
                f"handler is a PAID model call. Not processing:"
            )
            for job in AIJob.objects.filter(pk__in=job_ids):
                self.stdout.write(
                    f"  #{job.pk} [{job.kind}] paper={job.paper_id} "
                    f"base_revision={job.base_revision}"
                )
            return

        for job_id in job_ids:
            job = self._claim(job_id)
            if job is not None:
                self._process(job)

    @staticmethod
    def _claim(job_id: int) -> AIJob | None:
        """Atomically flip one still-pending row to running; skip if locked/gone."""
        with transaction.atomic():
            job = (
                AIJob.objects.select_for_update(skip_locked=True)
                .filter(pk=job_id, status=AIJobStatus.PENDING)
                .first()
            )
            if job is None:
                return None
            job.status = AIJobStatus.RUNNING
            job.save(update_fields=["status", "updated_at"])
            return job

    def _process(self, job: AIJob) -> None:
        """Cancel a stale job, else run its handler and record done/failed.

        Any handler error is caught and recorded as ``failed`` — one bad job
        must not abort the rest of the drain."""
        if job.base_revision != job.paper.revision:
            job.status = AIJobStatus.CANCELLED
            job.error = (
                "Paper changed since the job was queued; cancelled before any "
                "model call."
            )
            job.save(update_fields=["status", "error", "updated_at"])
            self.stdout.write(f"Job #{job.pk} cancelled (stale base_revision).")
            return

        handler = self.handlers[job.kind]
        try:
            result = handler(job)
        except Exception as exc:  # noqa: BLE001 — record failure, keep draining
            job.status = AIJobStatus.FAILED
            job.error = f"{type(exc).__name__}: {exc}"
            job.save(update_fields=["status", "error", "updated_at"])
            self.stderr.write(f"Job #{job.pk} failed: {job.error}")
            return

        job.status = AIJobStatus.DONE
        job.result = result
        job.error = ""
        job.save(update_fields=["status", "result", "error", "updated_at"])
        self.stdout.write(f"Job #{job.pk} done.")
