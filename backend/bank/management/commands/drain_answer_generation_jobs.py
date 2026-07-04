"""drain_answer_generation_jobs — run optional upload answer generation.

The upload screen queues ``AnswerGenerationJob`` rows only after the teacher
clicks Generate answers. This command is the paid drainer; run on cron alongside
other drainers. ``--dry-run`` lists work without constructing the model.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from ai_services.llm import make_chat_model
from bank.answer_generation import build_generator, process_answer_generation_job
from bank.models import AnswerGenerationJob, AnswerGenerationJobStatus

_RESUMABLE = (AnswerGenerationJobStatus.PENDING, AnswerGenerationJobStatus.RUNNING)


class Command(BaseCommand):
    help = "Run or resume optional AnswerGenerationJob rows (paid)."

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
            help="List queued answer jobs and exit WITHOUT calling a model.",
        )

    def handle(self, *args, **options):
        queued = AnswerGenerationJob.objects.filter(status__in=_RESUMABLE).order_by(
            "created_at"
        )
        if options["limit"]:
            queued = queued[: options["limit"]]
        jobs = list(queued)

        if not jobs:
            self.stdout.write("No resumable answer generation jobs.")
            return

        if options["dry_run"]:
            self.stdout.write(
                f"[dry-run] {len(jobs)} answer generation job(s) — each may be "
                "a PAID model call. Not processing:"
            )
            for job in jobs:
                self.stdout.write(
                    f"  #{job.pk} [{job.status}] upload={job.ingestion_job_id} "
                    f"school={job.school_id} total={job.total_count}"
                )
            return

        for job in jobs:
            self._process(job)

    def _process(self, job: AnswerGenerationJob) -> None:
        try:
            result = process_answer_generation_job(
                job,
                generator_factory=lambda: build_generator(make_chat_model),
            )
        except Exception as exc:  # noqa: BLE001
            self.stderr.write(f"Answer generation job #{job.pk} failed: {exc}")
            return
        self.stdout.write(
            f"Answer generation job #{job.pk} done: "
            f"{result.generated_count} generated, {result.skipped_count} skipped."
        )
