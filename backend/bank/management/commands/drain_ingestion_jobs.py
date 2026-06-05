"""drain_ingestion_jobs — process queued teacher PDF uploads out-of-request.

The live HTTP ingest front door (``bank.views.ingest``) only persists the
uploaded PDF and creates an ``IngestionJob`` row with ``status=pending`` — it
makes no Gemini call inside the request. This command is the drainer: run it on
the platform's cron (Render Cron Jobs / Railway / VPS crontab — no Celery, no
Redis, no always-on worker), it picks up pending jobs and runs each through the
same ``GeminiExtractor`` + ``Ingestor`` the CLI path uses, scoping the created
``Question`` rows to the job's ``school``.

~1-minute pickup latency is irrelevant: extraction itself takes minutes.

COST (Rule 13): each drained job is a PAID Gemini call per PDF page. ``--dry-run``
lists what would run and exits without touching Gemini. A real run is gated by
the deployment that schedules the cron; nothing here calls the model until a
pending job exists and the command runs for real.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from bank.ingestor import Ingestor
from bank.models import IngestionJob, IngestionJobStatus


class Command(BaseCommand):
    help = "Process pending IngestionJob rows via Gemini (paid). Run on cron."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Max number of pending jobs to process this run (default: all).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List pending jobs and exit WITHOUT calling Gemini (no cost).",
        )

    def handle(self, *args, **options):
        pending = IngestionJob.objects.filter(
            status=IngestionJobStatus.PENDING
        ).order_by("created_at")
        if options["limit"]:
            pending = pending[: options["limit"]]
        jobs = list(pending)

        if not jobs:
            self.stdout.write("No pending ingestion jobs.")
            return

        if options["dry_run"]:
            self.stdout.write(
                f"[dry-run] {len(jobs)} pending job(s) — each is a PAID Gemini "
                f"call per PDF page. Not processing:"
            )
            for job in jobs:
                self.stdout.write(
                    f"  #{job.pk} {job.source_file_name!r} "
                    f"school={job.school_id} type={job.source_type}"
                )
            return

        for job in jobs:
            self._process(job)

    def _process(self, job: IngestionJob) -> None:
        """Run one job through the ingestion pipeline; record status + counts.

        Marks ``running`` first (so a crashed run is visible as stuck-running,
        not silently re-picked), then ``done`` with result counts or ``failed``
        with the error. Any extraction error is caught and recorded — one bad
        PDF must not abort the rest of the drain."""
        job.status = IngestionJobStatus.RUNNING
        job.save(update_fields=["status", "updated_at"])

        try:
            with job.pdf.open("rb") as fh:
                pdf_bytes = fh.read()
            result = Ingestor().ingest(
                pdf_bytes,
                source_file_name=job.source_file_name,
                source_type=job.source_type,
                school=job.school,
            )
        except Exception as exc:  # noqa: BLE001 — record failure, keep draining
            job.status = IngestionJobStatus.FAILED
            job.error = f"{type(exc).__name__}: {exc}"
            job.save(update_fields=["status", "error", "updated_at"])
            self.stderr.write(f"Job #{job.pk} failed: {job.error}")
            return

        job.status = IngestionJobStatus.DONE
        job.created_count = result.created
        job.skipped_count = result.skipped_duplicates
        job.error = ""
        job.save(
            update_fields=[
                "status",
                "created_count",
                "skipped_count",
                "error",
                "updated_at",
            ]
        )
        self.stdout.write(
            f"Job #{job.pk} done: {result.created} created, "
            f"{result.skipped_duplicates} skipped."
        )
