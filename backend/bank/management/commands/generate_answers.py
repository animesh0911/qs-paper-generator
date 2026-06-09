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
from pydantic import BaseModel, Field

from ai_services.llm import ModelPurpose, make_chat_model
from bank.models import AnswerSource, Question

_DEFAULT_BATCH_SIZE = 10

_QTYPE_HINT = {
    "mcq": "Write the correct option label (e.g. 'A') followed by the option text.",
    "assertion_reason": (
        "State whether the assertion and reason are true and whether the "
        "reason correctly explains the assertion."
    ),
    "very_short_answer": "Write a concise answer in 1-2 sentences (max 30 words).",
    "short_answer": "Write a model answer in 3-5 sentences (max 80 words).",
    "long_answer": "Write a structured model answer with key points (max 200 words).",
    "case_based": "Address each sub-part of the case study in order.",
    "internal_choice": "Provide a model answer for one of the choices only.",
}


class _GeneratedAnswer(BaseModel):
    """One model answer keyed back to the question it answers."""

    id: int = Field(description="The Q# id of the question being answered.")
    answer: str = Field(description="The model answer text only — no preamble.")


class _BatchAnswers(BaseModel):
    """The structured output of one batch call — one entry per question asked."""

    answers: list[_GeneratedAnswer]


def _render_question(q: Question) -> str:
    """Render one question as a block in a batch prompt, including its id so the
    model's answer can be mapped back."""
    hint = _QTYPE_HINT.get(q.qtype, "Write a concise model answer.")
    chapter = q.chapter.name if q.chapter else "unknown chapter"
    options_block = ""
    if q.options:
        # .get(): a malformed option dict must not crash prompt-building (and
        # thereby abort the whole batch — rendering runs before the per-batch try
        # in handle()).
        lines = "\n".join(
            f"    {o.get('label', '?')}. {o.get('text', '')}" for o in q.options
        )
        options_block = f"\n  Options:\n{lines}"
    marks = f"{q.marks} mark{'s' if q.marks != 1 else ''}"
    return (
        f"[id={q.pk}] Type: {q.qtype} ({marks}); Chapter: {chapter}\n"
        f"  Question: {q.text}{options_block}\n"
        f"  Instruction: {hint}"
    )


def _build_batch_prompt(questions: Sequence[Question], format_instructions: str) -> str:
    blocks = "\n\n".join(_render_question(q) for q in questions)
    return (
        "You are generating CBSE Class 10 Science model answers for a marking "
        "scheme. Answer every question below, keyed by its id. Return only the "
        "answer text for each — no preamble, no restatement of the question.\n\n"
        f"{blocks}\n\n"
        f"{format_instructions}"
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

        qs = Question.objects.filter(answer="").select_related("chapter")
        if options["qtype"]:
            qs = qs.filter(qtype__in=options["qtype"])
        if options["limit"]:
            qs = qs[: options["limit"]]

        questions = list(qs)
        if not questions:
            self.stdout.write("No unanswered questions found.")
            return

        parser = PydanticOutputParser(pydantic_object=_BatchAnswers)
        dry_run = options["dry_run"]

        if dry_run:
            for batch in _chunk(questions, batch_size):
                self.stdout.write(
                    _build_batch_prompt(batch, parser.get_format_instructions())
                )
                self.stdout.write("")
            return

        # One model for the whole run; the seam attaches per-call telemetry.
        chain = self.make_model(ModelPurpose.ANSWER_GENERATION) | parser

        updated = failed = 0
        for batch in _chunk(questions, batch_size):
            ids = [q.pk for q in batch]
            # One bad batch (unparseable reply, transport error) must not abort
            # the rest of the run, so the whole call is guarded.
            try:
                prompt = _build_batch_prompt(batch, parser.get_format_instructions())
                result = chain.invoke(prompt)
                by_id = {a.id: a.answer.strip() for a in result.answers}
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
                q.answer = answer
                q.answer_source = AnswerSource.GENERATED_UNVERIFIED
                q.save(update_fields=["answer", "answer_source"])
                updated += 1
                self.stdout.write(f"Q#{q.pk} ({q.qtype}): generated.")

        self.stdout.write(
            self.style.SUCCESS(f"Done: {updated} generated, {failed} failed.")
        )
