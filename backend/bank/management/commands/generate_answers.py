"""generate_answers — LLM-generate model answers for unanswered bank questions.

Asks a chat model (built through the model seam — ADR-0005) for CBSE-appropriate
model answers, **batched** so one call covers several questions (answer
generation is cheap-per-token but call-heavy; batching keeps cost down). Each
generated answer is stored with ``answer_source='generated_unverified'``. A
teacher must set ``answer_source='generated_verified'`` via the Django admin
("Approve generated answers" action) before the answer can appear in a marking
scheme. The gate that enforces this is
``PaperAnswerKeyPdfView._answers_by_id`` (papers/views.py), which drops
``generated_unverified`` answers so they render as ``(no answer on file)`` until
approved.

Usage::

    python manage.py generate_answers [--qtype mcq vsa] [--limit 100]
                                      [--batch-size 10] [--dry-run]

``--dry-run`` prints the batch prompts without writing to the database.
``--qtype`` filters to specific question types (space-separated, default: all).
``--limit`` caps the number of questions processed in one run.
``--batch-size`` sets how many questions go in one LLM call (default 10).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from django.core.management.base import BaseCommand, CommandError
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import PydanticOutputParser

from ai_services.llm import ModelPurpose, make_chat_model
from bank.answer_generation import (
    answerable_questions,
    persist_answer_if_unanswered,
)
from bank.answer_generation_core import (
    AnswerGenerator,
    AnswerQuestion,
    BatchAnswers,
    build_answer_prompt,
    render_answer_question,
)
from bank.models import Question

_DEFAULT_BATCH_SIZE = 10


def _render_question(q: Question) -> str:
    """Backwards-compatible wrapper around the shared production renderer."""
    return render_answer_question(AnswerQuestion.from_model(q))


def _build_batch_prompt(questions: Sequence[Question], format_instructions: str) -> str:
    """Backwards-compatible wrapper around the shared production prompt."""
    return build_answer_prompt(
        [AnswerQuestion.from_model(question) for question in questions],
        format_instructions,
    )


def _chunk(items: list[Question], size: int):
    for start in range(0, len(items), size):
        yield items[start : start + size]


class Command(BaseCommand):
    help = "LLM-generate model answers for bank questions that have no stored answer."

    # Injection seam (Rules 9/11): tests set this on a Command instance and pass
    # the instance to call_command, so the fake chat-model factory is supplied
    # without patching the module. Defaults to the real model seam.
    make_model: Callable[[ModelPurpose], BaseChatModel] = staticmethod(make_chat_model)

    def add_arguments(self, parser):
        parser.add_argument(
            "--qtype",
            nargs="*",
            metavar="QTYPE",
            help="Restrict to these question types (default: all).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Max questions to process in this run.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=_DEFAULT_BATCH_SIZE,
            help=f"Questions per LLM call (default {_DEFAULT_BATCH_SIZE}).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print batch prompts without writing to the database.",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        if batch_size < 1:
            raise CommandError("--batch-size must be at least 1.")

        qs = (
            answerable_questions(Question.objects.filter(answer=""))
            .select_related("chapter")
            .order_by("section", "id")
        )
        if options["qtype"]:
            qs = qs.filter(qtype__in=options["qtype"])
        if options["limit"]:
            qs = qs[: options["limit"]]

        questions = list(qs)
        if not questions:
            self.stdout.write("No unanswered questions found.")
            return

        parser = PydanticOutputParser(pydantic_object=BatchAnswers)
        dry_run = options["dry_run"]

        if dry_run:
            for batch in _chunk(questions, batch_size):
                self.stdout.write(
                    _build_batch_prompt(batch, parser.get_format_instructions())
                )
                self.stdout.write("")
            return

        # One model for the whole run; the seam attaches per-call telemetry.
        generator = AnswerGenerator(self.make_model(ModelPurpose.ANSWER_GENERATION))

        updated = failed = skipped = 0
        for batch in _chunk(questions, batch_size):
            ids = [q.pk for q in batch]
            # One bad batch (unparseable reply, transport error) must not abort
            # the rest of the run, so the whole call is guarded.
            try:
                result = generator.generate(
                    [AnswerQuestion.from_model(question) for question in batch]
                )
                by_id = {item["id"]: item["answer"] for item in result.accepted}
            except Exception as exc:  # noqa: BLE001
                failed += len(batch)
                self.stderr.write(self.style.ERROR(f"Batch {ids}: failed — {exc}"))
                continue

            for q in batch:
                answer = by_id.get(q.pk, "")
                if not answer:
                    failed += 1
                    self.stderr.write(
                        self.style.ERROR(f"Q#{q.pk} ({q.qtype}): no answer returned.")
                    )
                    continue
                if persist_answer_if_unanswered(q.pk, answer):
                    updated += 1
                    self.stdout.write(f"Q#{q.pk} ({q.qtype}): generated.")
                else:
                    skipped += 1
                    self.stdout.write(
                        f"Q#{q.pk} ({q.qtype}): skipped; answer already exists."
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {updated} generated, {skipped} skipped, {failed} failed."
            )
        )
