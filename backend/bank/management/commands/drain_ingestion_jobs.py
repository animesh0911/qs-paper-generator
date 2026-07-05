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

~1-minute pickup latency is irrelevant: extraction itself takes minutes.
Overlapping drains are made safe by a Postgres session **advisory lock**: a
tick that cannot acquire the lock exits immediately, so only one drainer ever
processes jobs at a time (status flips alone never guarded against two
simultaneous drains — two passes could both grab the same ``running`` row and
double-bill it). This keeps the drain safe under multiple worker replicas or an
accidental manual run alongside the cron, while preserving the serial,
one-job-at-a-time behaviour.

COST (Rule 13): each drained job is a PAID Gemini call per *unextracted* PDF
page — per-page checkpointing is exactly what stops a resumed job re-billing
pages it already extracted. ``--dry-run`` lists what would run and exits
without touching Gemini. A real run is gated by the deployment that schedules
the cron; nothing here calls the model until a resumable job exists and the
command runs for real.
"""

from __future__ import annotations

import os
import shlex
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from django.core.management.base import BaseCommand
from django.db import connection

from ai_services.errors import friendly_llm_error
from ai_services.llm import make_chat_model
from bank.models import IngestionJob, IngestionJobStatus
from workflows.checkpointer import get_checkpointer
from workflows.extraction import (
    build_extraction_graph,
    build_ocr_batch_extraction_graph,
)

_RESUMABLE = (IngestionJobStatus.PENDING, IngestionJobStatus.RUNNING)

# Stable, arbitrary key identifying the ingestion-drain advisory lock. Any other
# drainer on the same database calls pg_try_advisory_lock with this same key, so
# only one holds it at a time. Session-scoped: released explicitly (and by the
# backend on disconnect), never blocking other tables.
_ADVISORY_LOCK_KEY = 0x1_9E57_10B5  # "INGEST 10BS" mnemonic; value is immaterial


@contextmanager
def _drain_advisory_lock():
    """Yield ``True`` iff this process acquired the ingestion-drain lock.

    Non-blocking: ``pg_try_advisory_lock`` returns immediately so an overlapping
    tick can bail instead of piling up. SQLite (tests without Postgres) has no
    advisory locks; there we degrade to always-acquired since those runs are
    single-process anyway.
    """
    if connection.vendor != "postgresql":
        yield True
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", [_ADVISORY_LOCK_KEY])
        acquired = bool(cursor.fetchone()[0])
    try:
        yield acquired
    finally:
        if acquired:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", [_ADVISORY_LOCK_KEY])


def _format_extraction_error(exc: Exception) -> str:
    """Turn provider setup failures into operator-facing job errors."""
    message = str(exc)
    if "Your default credentials were not found" in message:
        return (
            "Gemini extraction credentials are not configured. Set GEMINI_API_KEY "
            "for the default gemini-native-pdf pipeline, configure Google ADC, or "
            "run the drainer with EXTRACTION_PIPELINE=mistral-ocr-batch if you "
            "intend to use Mistral OCR credentials."
        )
    # Sanitise raw provider errors (e.g. a 402 credits JSON dump) before they
    # land on the teacher-visible job.error — see ai_services.errors.
    return friendly_llm_error(exc)


def _load_dotenv() -> None:
    backend_dir = Path(__file__).resolve().parents[3]
    repo_dir = backend_dir.parent
    for path in (repo_dir / ".env", backend_dir / ".env"):
        if not path.is_file():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            try:
                parts = shlex.split(raw_line, comments=True, posix=True)
            except ValueError:
                continue
            if len(parts) != 1 or "=" not in parts[0]:
                continue
            key, value = parts[0].split("=", 1)
            key = key.strip()
            if key and not os.environ.get(key):
                os.environ[key] = value


def _default_extraction_llm_from_generation() -> None:
    if "LLM_EXTRACTION_PROVIDER" not in os.environ:
        provider = os.getenv("LLM_QUESTION_GENERATION_PROVIDER")
        if provider:
            os.environ["LLM_EXTRACTION_PROVIDER"] = provider
    if "LLM_EXTRACTION_MODEL" not in os.environ:
        model = os.getenv("LLM_QUESTION_GENERATION_MODEL")
        if model:
            os.environ["LLM_EXTRACTION_MODEL"] = model


class Command(BaseCommand):
    help = (
        "Run or resume pending/running IngestionJob rows via the extraction "
        "graph (paid). Run on cron."
    )

    def add_arguments(self, parser):
        _load_dotenv()
        _default_extraction_llm_from_generation()

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
        parser.add_argument(
            "--extractor",
            choices=(
                "gemini-native-pdf",
                "mistral-ocr-markdown",
                "mistral-ocr-batch",
            ),
            default=os.getenv("EXTRACTION_PIPELINE", "gemini-native-pdf"),
            help=(
                "Experimental extraction backend. Defaults to gemini-native-pdf; "
                "can also be set with EXTRACTION_PIPELINE=mistral-ocr-batch."
            ),
        )
        parser.add_argument(
            "--batch-pages",
            type=int,
            default=int(os.getenv("OCR_BATCH_PAGES") or "999"),
            help=(
                "OCR markdown pages per structuring LLM call for "
                "mistral-ocr-batch. Defaults to one-shot extraction so long "
                "questions are not split across page-count batches."
            ),
        )

    def _resumable_jobs(self, limit: int | None) -> list[IngestionJob]:
        queued = IngestionJob.objects.filter(status__in=_RESUMABLE).order_by(
            "created_at"
        )
        if limit:
            queued = queued[:limit]
        return list(queued)

    def handle(self, *args, **options):
        _load_dotenv()
        _default_extraction_llm_from_generation()

        # --dry-run only reads, and never bills Gemini, so it skips the lock —
        # inspecting the queue must not be blocked by a real drain in flight.
        if options["dry_run"]:
            jobs = self._resumable_jobs(options["limit"])
            if not jobs:
                self.stdout.write("No resumable ingestion jobs.")
                return
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

        with _drain_advisory_lock() as acquired:
            if not acquired:
                self.stdout.write(
                    "Another ingestion drain holds the lock; skipping this tick."
                )
                return

            # Query *inside* the lock: a drain that just finished may have
            # settled the jobs a stale pre-lock snapshot would have re-run.
            jobs = self._resumable_jobs(options["limit"])
            if not jobs:
                self.stdout.write("No resumable ingestion jobs.")
                return

            for job in jobs:
                self._process(
                    job,
                    extractor=options["extractor"],
                    batch_pages=options["batch_pages"],
                )

    def _process(self, job: IngestionJob, *, extractor: str, batch_pages: int) -> None:
        """Run or resume one job's graph thread; record status + counts.

        Marks ``running`` first (a crashed run stays visible — and resumable —
        as running), then ``done`` with the counts the graph reported or
        ``failed`` with the error. Any extraction error is caught and recorded
        — one bad PDF must not abort the rest of the drain."""
        if job.thread_id and ":" in job.thread_id:
            stored_extractor, _ = job.thread_id.split(":", 1)
            if stored_extractor in {
                "gemini-native-pdf",
                "mistral-ocr-markdown",
                "mistral-ocr-batch",
            }:
                extractor = stored_extractor
        if not job.thread_id:
            job.thread_id = f"{extractor}:{uuid4().hex}"
        job.status = IngestionJobStatus.RUNNING
        job.save(update_fields=["status", "thread_id", "updated_at"])

        try:
            final = self._run_graph(
                job,
                extractor=extractor,
                batch_pages=batch_pages,
            )
        except Exception as exc:  # noqa: BLE001 — record failure, keep draining
            job.status = IngestionJobStatus.FAILED
            job.error = _format_extraction_error(exc)
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
    def _run_graph(
        job: IngestionJob,
        *,
        extractor: str = "gemini-native-pdf",
        batch_pages: int = 999,
    ) -> dict:
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
        make_extractor = None
        if extractor == "mistral-ocr-markdown":
            from bank.ocr_extractor import MistralOcrMarkdownExtractor

            make_extractor = MistralOcrMarkdownExtractor

        with get_checkpointer() as checkpointer:
            if extractor == "mistral-ocr-batch":
                graph = build_ocr_batch_extraction_graph(
                    checkpointer,
                    batch_pages=batch_pages,
                )
            else:
                graph = build_extraction_graph(
                    checkpointer,
                    make_model=make_chat_model,
                    make_extractor=make_extractor,
                )
            config = {"configurable": {"thread_id": job.thread_id}}
            snapshot = graph.get_state(config)
            if snapshot.values and not snapshot.next:
                return snapshot.values
            state = None if snapshot.values else {"job_id": job.pk}
            return graph.invoke(state, config, durability="sync")
