"""Optional answer generation for questions extracted from one upload.

Small public surface, deep implementation: views and commands only queue, read,
or process an ``AnswerGenerationJob``. This module owns tenancy, idempotency,
target selection, prompt rendering, and persistence provenance.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import uuid4

from django.db import transaction
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from ai_services.errors import friendly_llm_error
from ai_services.llm import ModelPurpose, make_chat_model
from bank.models import (
    AnswerGenerationJob,
    AnswerGenerationJobStatus,
    AnswerSource,
    IngestionJob,
    IngestionJobStatus,
    Question,
)
from workflows.checkpointer import get_checkpointer

USABLE_PARSE_QUALITIES = ("clean", "partial")


class AnswerGenerationConflict(Exception):
    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class ProcessedAnswerGeneration:
    generated_count: int
    skipped_count: int


class _GeneratedAnswer(BaseModel):
    id: int = Field(description="Question id being answered.")
    answer: str = Field(description="Model answer text only.")


class _BatchAnswers(BaseModel):
    answers: list[_GeneratedAnswer]


_QTYPE_HINT = {
    "mcq": "Write the correct option label and option text.",
    "assertion_reason": (
        "State whether assertion/reason are true and whether the reason "
        "correctly explains the assertion."
    ),
    "very_short_answer": "Write a concise answer in 1-2 sentences.",
    "short_answer": "Write a model answer in 3-5 sentences.",
    "long_answer": "Write a structured model answer with key points.",
    "case_based": "Address each sub-part of the case study in order.",
}


def get_owned_ingestion_job(user, ingestion_job_id: int) -> IngestionJob | None:
    try:
        return IngestionJob.objects.get(pk=ingestion_job_id, school=user.school)
    except IngestionJob.DoesNotExist:
        return None


def target_questions_for_upload(ingestion_job: IngestionJob):
    return ingestion_job.questions.filter(
        parse_quality__in=USABLE_PARSE_QUALITIES
    ).order_by("section", "id")


def queue_ingestion_answer_generation(user, ingestion_job_id: int):
    """Queue optional answer generation for a completed upload.

    Returns ``None`` for a cross-school/missing upload, raises conflict for a
    non-terminal extraction, and is idempotent for repeated clicks.
    """
    ingestion_job = get_owned_ingestion_job(user, ingestion_job_id)
    if ingestion_job is None:
        return None
    if ingestion_job.status != IngestionJobStatus.DONE:
        raise AnswerGenerationConflict(
            "Extraction must finish before answers can be generated."
        )

    total = target_questions_for_upload(ingestion_job).count()
    job, created = AnswerGenerationJob.objects.get_or_create(
        ingestion_job=ingestion_job,
        defaults={
            "school": user.school,
            "created_by": user,
            "total_count": total,
        },
    )
    if not created and job.status == AnswerGenerationJobStatus.FAILED:
        job.status = AnswerGenerationJobStatus.PENDING
        job.error = ""
        job.total_count = total
        job.generated_count = 0
        job.skipped_count = 0
        job.save(
            update_fields=[
                "status",
                "error",
                "total_count",
                "generated_count",
                "skipped_count",
                "updated_at",
            ]
        )
    return job


def answer_generation_state(user, ingestion_job_id: int):
    ingestion_job = get_owned_ingestion_job(user, ingestion_job_id)
    if ingestion_job is None:
        return None
    try:
        job = ingestion_job.answer_generation_job
    except AnswerGenerationJob.DoesNotExist:
        job = None
    answered = target_questions_for_upload(ingestion_job).exclude(answer="")
    return job, answered


def _render_question(q: Question) -> str:
    chapter = q.chapter.name if q.chapter else "unknown chapter"
    hint = _QTYPE_HINT.get(q.qtype, "Write a concise model answer.")
    options_block = ""
    if q.options:
        lines = "\n".join(
            f"    {o.get('label', '?')}. {o.get('text', '')}" for o in q.options
        )
        options_block = f"\n  Options:\n{lines}"
    return (
        f"[id={q.pk}] Type: {q.qtype}; Marks: {q.marks}; Chapter: {chapter}\n"
        f"  Question: {q.text}{options_block}\n"
        f"  Instruction: {hint}"
    )


def _build_prompt(questions: list[Question], format_instructions: str) -> str:
    blocks = "\n\n".join(_render_question(q) for q in questions)
    return (
        "Generate CBSE Class 10 Science model answers for the extracted "
        "questions below. Return an answer for each id. Persistable answer text "
        "only: no preamble and no restatement of the question.\n\n"
        f"{blocks}\n\n{format_instructions}"
    )


class BankAnswerGenerator:
    """Boundary wrapper around the chat model used by the answer graph."""

    def __init__(
        self,
        make_model: Callable[[ModelPurpose], BaseChatModel] = make_chat_model,
    ):
        self.make_model = make_model

    def generate(self, question_ids: list[int]) -> list[dict]:
        questions = list(
            Question.objects.filter(pk__in=question_ids)
            .select_related("chapter")
            .order_by("section", "id")
        )
        if not questions:
            return []
        parser = PydanticOutputParser(pydantic_object=_BatchAnswers)
        chain = self.make_model(ModelPurpose.ANSWER_GENERATION) | parser
        result = chain.invoke(
            _build_prompt(questions, parser.get_format_instructions())
        )
        return [{"id": item.id, "answer": item.answer} for item in result.answers]


def plan_answer_generation(job: AnswerGenerationJob) -> dict:
    questions = list(target_questions_for_upload(job.ingestion_job))
    unanswered = [q.pk for q in questions if not q.answer]
    return {
        "target_question_ids": unanswered,
        "total_count": len(questions),
        "skipped_count": len(questions) - len(unanswered),
    }


@transaction.atomic
def persist_generated_answers(job: AnswerGenerationJob, answers: list[dict]) -> dict:
    by_id = {
        int(item.get("id")): str(item.get("answer") or "").strip()
        for item in answers
        if item.get("id") is not None
    }
    generated = 0
    skipped = 0
    for question in target_questions_for_upload(job.ingestion_job).select_for_update():
        answer = by_id.get(question.pk, "")
        if question.answer:
            if (
                answer
                and question.answer == answer
                and question.answer_source == AnswerSource.GENERATED_UNVERIFIED
            ):
                generated += 1
            else:
                skipped += 1
            continue
        if not answer:
            skipped += 1
            continue
        question.answer = answer
        question.answer_source = AnswerSource.GENERATED_UNVERIFIED
        question.save(update_fields=["answer", "answer_source"])
        generated += 1
    return {"generated_count": generated, "skipped_count": skipped}


def build_generator(
    make_model: Callable[[ModelPurpose], BaseChatModel] = make_chat_model,
):
    return BankAnswerGenerator(make_model=make_model)


def process_answer_generation_job(
    job: AnswerGenerationJob,
    *,
    generator_factory: Callable[[], object] | None = None,
    checkpointer_cm=get_checkpointer,
) -> ProcessedAnswerGeneration:
    """Run/resume one answer-generation graph and settle the ledger row."""
    from workflows.answer_generation import build_answer_generation_graph

    if not job.thread_id:
        job.thread_id = f"answer-generation:{uuid4().hex}"
    job.status = AnswerGenerationJobStatus.RUNNING
    job.error = ""
    job.save(update_fields=["status", "thread_id", "error", "updated_at"])

    try:
        with checkpointer_cm() as checkpointer:
            graph = build_answer_generation_graph(
                checkpointer,
                generator_factory=generator_factory or build_generator,
            )
            config = {"configurable": {"thread_id": job.thread_id}}
            snapshot = graph.get_state(config)
            if snapshot.values and not snapshot.next:
                final = snapshot.values
            else:
                state = None if snapshot.values else {"answer_job_id": job.pk}
                final = graph.invoke(state, config, durability="sync")
    except Exception as exc:  # noqa: BLE001
        job.status = AnswerGenerationJobStatus.FAILED
        # Sanitise raw provider errors before they reach the teacher-visible job.
        job.error = friendly_llm_error(exc)
        job.save(update_fields=["status", "error", "updated_at"])
        raise

    job.status = AnswerGenerationJobStatus.DONE
    job.total_count = final.get("total_count", job.total_count)
    job.generated_count = final.get("generated_count", 0)
    job.skipped_count = final.get("skipped_count", 0)
    job.error = ""
    job.save(
        update_fields=[
            "status",
            "total_count",
            "generated_count",
            "skipped_count",
            "error",
            "updated_at",
        ]
    )
    return ProcessedAnswerGeneration(job.generated_count, job.skipped_count)
