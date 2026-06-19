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
   double-bill, Rule 13) the same row. A ``running`` row is only claimable once
   it has been idle past ``RECLAIM_RUNNING_AFTER`` — long enough that a sibling
   drain still working it is never hijacked; a row that idle is one a prior
   drain died on. Since editor jobs have no per-page checkpoint (unlike
   ``IngestionJob``), a reclaimed row is **failed** rather than re-run —
   re-running would re-bill (Rule 13), and failing frees the paper from the
   one-active-job lock.
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
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from ai_editor.models import AIJob, AIJobKind, AIJobStatus

# A ``running`` row is only reclaimed once it has been idle (``updated_at``)
# longer than this. The window must comfortably exceed the slowest handler so an
# overlapping drain on the short cron interval never reclaims a job a sibling
# pass is still actively working — that would fail a live job and invite a retry
# that double-bills (Rule 13). A genuinely abandoned (crashed-drain) row crosses
# the window and is then freed.
RECLAIM_RUNNING_AFTER = timedelta(minutes=10)


def _drainable_filter(now) -> Q:
    """Pending rows, plus running rows idle past :data:`RECLAIM_RUNNING_AFTER`."""
    return Q(status=AIJobStatus.PENDING) | Q(
        status=AIJobStatus.RUNNING, updated_at__lt=now - RECLAIM_RUNNING_AFTER
    )


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
        now = timezone.now()
        drainable = AIJob.objects.filter(_drainable_filter(now)).order_by("created_at")
        if options["limit"]:
            drainable = drainable[: options["limit"]]
        job_ids = list(drainable.values_list("pk", flat=True))

        if not job_ids:
            self.stdout.write("No drainable AI jobs.")
            return

        if options["dry_run"]:
            self.stdout.write(
                f"[dry-run] {len(job_ids)} drainable job(s) — each implemented "
                f"handler is a PAID model call. Not processing:"
            )
            for job in AIJob.objects.filter(pk__in=job_ids):
                self.stdout.write(
                    f"  #{job.pk} [{job.kind}] paper={job.paper_id} "
                    f"base_revision={job.base_revision}"
                )
            return

        for job_id in job_ids:
            job, reclaimed = self._claim(job_id)
            if job is not None:
                self._process(job, reclaimed=reclaimed)

    @staticmethod
    def _claim(job_id: int) -> tuple[AIJob | None, bool]:
        """Atomically claim one drainable row as running; skip if locked/gone.

        The drainable predicate is re-evaluated under the row lock with a fresh
        ``now``, so a running row a sibling drain claimed (and thus refreshed
        ``updated_at`` on) between listing and locking is no longer reclaimable
        and is skipped — closing the claim→process race window (Rule 13).

        Returns ``(job, reclaimed)`` where ``reclaimed`` is True when the row was
        already ``running`` — i.e. a previous drain died mid-flight and this pass
        is picking it back up.
        """
        with transaction.atomic():
            job = (
                AIJob.objects.select_for_update(skip_locked=True)
                .filter(_drainable_filter(timezone.now()), pk=job_id)
                .first()
            )
            if job is None:
                return None, False
            reclaimed = job.status == AIJobStatus.RUNNING
            job.status = AIJobStatus.RUNNING
            job.save(update_fields=["status", "updated_at"])
            return job, reclaimed

    def _process(self, job: AIJob, *, reclaimed: bool) -> None:
        """Cancel a stale job, else run its handler and record done/failed.

        Any handler error is caught and recorded as ``failed`` — one bad job
        must not abort the rest of the drain."""
        if reclaimed:
            # A prior drain died after claiming this job. Editor jobs have no
            # per-page checkpoint (unlike IngestionJob), so re-running the
            # handler would re-bill a paid call (Rule 13). Fail it terminally
            # instead, which also frees the paper from the one-active-job lock;
            # the teacher can re-request. (#34 may add resumable handlers.)
            job.status = AIJobStatus.FAILED
            job.error = "Reclaimed after an interrupted drain run; not retried."
            job.save(update_fields=["status", "error", "updated_at"])
            self.stderr.write(f"Job #{job.pk} failed (reclaimed, interrupted run).")
            return

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
