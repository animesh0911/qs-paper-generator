"""generate_answers — LLM-generate model answers for unanswered bank questions.

Calls Gemini once per question to produce a CBSE-appropriate model answer,
storing it with ``answer_source='generated_unverified'``. A teacher must set
``answer_source='generated_verified'`` via the Django admin ("Approve generated
answers" action) before the answer can appear in a marking scheme. The gate that
enforces this is ``PaperAnswerKeyPdfView._answers_by_id`` (papers/views.py),
which drops ``generated_unverified`` answers so they render as
``(no answer on file)`` until approved.

Usage::

    python manage.py generate_answers [--qtype mcq vsa] [--limit 100] [--dry-run]

``--dry-run`` prints what would be generated without writing to the database.
``--qtype`` filters to specific question types (space-separated, default: all).
``--limit`` caps the number of questions processed in one run.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from ai_services.llm import make_llm_client
from bank.models import AnswerSource, Question

_ANSWER_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "answer": {"type": "STRING"},
    },
    "required": ["answer"],
}

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


def _build_prompt(q: Question) -> str:
    hint = _QTYPE_HINT.get(q.qtype, "Write a concise model answer.")
    chapter = q.chapter.name if q.chapter else "unknown chapter"
    options_block = ""
    if q.options:
        # .get(): a malformed option dict must not crash prompt-building (and
        # thereby abort the whole batch — _build_prompt runs before the
        # per-question try in handle()).
        lines = "\n".join(
            f"  {o.get('label', '?')}. {o.get('text', '')}" for o in q.options
        )
        options_block = f"\nOptions:\n{lines}"
    return (
        "You are generating a CBSE Class 10 Science model answer for the "
        "marking scheme.\n\n"
        f"Chapter: {chapter}\n"
        f"Question type: {q.qtype} ({q.marks} mark{'s' if q.marks != 1 else ''})\n"
        f"Question: {q.text}{options_block}\n\n"
        f"{hint}\n\n"
        "Return only the answer field — no preamble, no explanation of your reasoning."
    )


class Command(BaseCommand):
    help = "LLM-generate model answers for bank questions that have no stored answer."

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
            "--dry-run",
            action="store_true",
            help="Print prompts without writing to the database.",
        )

    def handle(self, *args, **options):
        qs = Question.objects.filter(answer="").select_related("chapter")
        if options["qtype"]:
            qs = qs.filter(qtype__in=options["qtype"])
        if options["limit"]:
            qs = qs[: options["limit"]]

        questions = list(qs)
        if not questions:
            self.stdout.write("No unanswered questions found.")
            return

        dry_run = options["dry_run"]
        client = None if dry_run else make_llm_client()

        updated = failed = 0
        for q in questions:
            prompt = _build_prompt(q)
            if dry_run:
                self.stdout.write(f"--- Q#{q.pk} ({q.qtype}) ---")
                self.stdout.write(prompt)
                self.stdout.write("")
                continue
            try:
                result = client.generate_text(prompt, _ANSWER_SCHEMA)
                answer = result.get("answer", "").strip()
                if not answer:
                    raise ValueError("empty answer returned")
                q.answer = answer
                q.answer_source = AnswerSource.GENERATED_UNVERIFIED
                q.save(update_fields=["answer", "answer_source"])
                updated += 1
                self.stdout.write(f"Q#{q.pk} ({q.qtype}): generated.")
            except Exception as exc:  # noqa: BLE001
                failed += 1
                self.stderr.write(
                    self.style.ERROR(f"Q#{q.pk} ({q.qtype}): failed — {exc}")
                )

        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(f"Done: {updated} generated, {failed} failed.")
            )
