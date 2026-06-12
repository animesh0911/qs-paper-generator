"""drain_ingestion_jobs — run or resume queued PDF extractions out-of-request.

The live HTTP ingest front door (``bank.views.ingest``) only persists the
uploaded PDF and creates an ``IngestionJob`` row with ``status=pending`` — it
makes no Gemini call inside the request. This command is the drainer: run it on
the platform's cron (Render Cron Jobs / Railway / VPS crontab — no Celery, no
Redis, no always-on worker), it picks up pending *and* running jobs and drives
each through the extraction ``StateGraph`` (``workflows.extraction``),
checkpointed per page under the job's ``thread_id`` (ADR-0006). A ``running``
row whose process died is therefore not stuck: the next pass resumes its graph
thread from the last checkpoint instead of restarting it. A ``failed`` row is
terminal until manually re-queued (flip it back to ``pending``) — the resume
then still starts from the last checkpoint, not page 1.

~1-minute pickup latency is irrelevant: extraction itself takes minutes. The
drain assumes the platform schedules non-overlapping runs (it always has —
status flips alone never guarded against two simultaneous drains).

COST (Rule 13): each drained job is a PAID Gemini call per *unextracted* PDF
page — per-page checkpointing is exactly what stops a resumed job re-billing
pages it already extracted. ``--dry-run`` lists what would run and exits
without touching Gemini. A real run is gated by the deployment that schedules
the cron; nothing here calls the model until a resumable job exists and the
command runs for real.
"""

from __future__ import annotations

from uuid import uuid4

from django.core.management.base import BaseCommand

from ai_services.llm import make_chat_model
from bank.models import IngestionJob, IngestionJobStatus
from workflows.checkpointer import get_checkpointer
from workflows.extraction import build_extraction_graph

_RESUMABLE = (IngestionJobStatus.PENDING, IngestionJobStatus.RUNNING)


class Command(BaseCommand):
    help = (
        "Run or resume pending/running IngestionJob rows via the extraction "
        "graph (paid). Run on cron."
    )

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
            help="List resumable jobs and exit WITHOUT calling Gemini (no cost).",
        )

    def handle(self, *args, **options):
        queued = IngestionJob.objects.filter(status__in=_RESUMABLE).order_by(
            "created_at"
        )
        if options["limit"]:
            queued = queued[: options["limit"]]
        jobs = list(queued)

        if not jobs:
            self.stdout.write("No resumable ingestion jobs.")
            return

        if options["dry_run"]:
            self.stdout.write(
                f"[dry-run] {len(jobs)} resumable job(s) — each is a PAID Gemini "
                f"call per unextracted PDF page. Not processing:"
            )
            for job in jobs:
                self.stdout.write(
                    f"  #{job.pk} [{job.status}] {job.source_file_name!r} "
                    f"school={job.school_id} type={job.source_type}"
                )
            return

        for job in jobs:
            self._process(job)

    def _process(self, job: IngestionJob) -> None:
        """Run or resume one job's graph thread; record status + counts.

        Marks ``running`` first (a crashed run stays visible — and resumable —
        as running), then ``done`` with the counts the graph reported or
        ``failed`` with the error. Any extraction error is caught and recorded
        — one bad PDF must not abort the rest of the drain."""
        if not job.thread_id:
            job.thread_id = uuid4().hex
        job.status = IngestionJobStatus.RUNNING
        job.save(update_fields=["status", "thread_id", "updated_at"])

        try:
            final = self._run_graph(job)
        except Exception as exc:  # noqa: BLE001 — record failure, keep draining
            job.status = IngestionJobStatus.FAILED
            job.error = f"{type(exc).__name__}: {exc}"
            job.save(update_fields=["status", "error", "updated_at"])
            self.stderr.write(f"Job #{job.pk} failed: {job.error}")
            return

        job.status = IngestionJobStatus.DONE
        job.created_count = final["created"]
        job.skipped_count = final["skipped"]
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
            f"Job #{job.pk} done: {final['created']} created, "
            f"{final['skipped']} skipped."
        )

    @staticmethod
    def _run_graph(job: IngestionJob) -> dict:
        """Invoke the job's thread fresh, resume it, or just read it back.

        The checkpoint — not the ledger — is the truth about how far the
        thread got: no checkpoint means a fresh invoke with the initial state;
        pending tasks mean a resume (``input=None`` continues from the last
        per-page checkpoint); a finished thread (a crash landed between the
        graph completing and the ledger update) only needs its counts read
        back — re-invoking would be a paid restart. ``durability="sync"``
        makes each page's checkpoint a synchronous write, so a kill can never
        lose a page that was already paid for.
        """
        with get_checkpointer() as checkpointer:
            graph = build_extraction_graph(checkpointer, make_model=make_chat_model)
            config = {"configurable": {"thread_id": job.thread_id}}
            snapshot = graph.get_state(config)
            if snapshot.values and not snapshot.next:
                return snapshot.values
            state = None if snapshot.values else {"job_id": job.pk}
            return graph.invoke(state, config, durability="sync")
