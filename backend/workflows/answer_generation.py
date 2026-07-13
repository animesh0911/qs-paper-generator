"""Optional upload-answer generation as a resumable LangGraph graph.

Graph shape: ``plan`` (select unanswered extracted questions) → ``generate``
(the paid LLM pass) → ``persist`` (idempotently write answers to Question rows).
Each completed paid batch is checkpointed before final persistence, so resume
skips batches whose checkpoint committed. The currently executing batch remains
at-least-once: a crash after the provider returns but before checkpoint commit
can repeat that batch.
"""

from __future__ import annotations

import operator
from collections.abc import Callable
from typing import Annotated, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph

from bank.answer_generation import (
    StoredQuestionAnswerGenerator,
    persist_generated_answers,
    plan_answer_generation,
)
from bank.models import AnswerGenerationJob


class AnswerGenerationState(TypedDict, total=False):
    answer_job_id: int
    target_question_ids: list[int]
    answers: Annotated[list[dict], operator.add]
    missing_question_ids: Annotated[list[int], operator.add]
    duplicate_question_ids: Annotated[list[int], operator.add]
    unexpected_question_ids: Annotated[list[int], operator.add]
    blank_question_ids: Annotated[list[int], operator.add]
    batch_size: int
    next_offset: int
    total_count: int
    generated_count: int
    skipped_count: int


def build_answer_generation_graph(
    checkpointer: BaseCheckpointSaver,
    *,
    generator_factory: Callable[[], StoredQuestionAnswerGenerator],
    batch_size: int | None = None,
):
    """Compile answer generation with one checkpointed paid node per batch.

    ``batch_size=None`` preserves the historical one-call-per-upload behavior.
    Evals and deployments can supply a positive size without changing prompts,
    parsing, model routing, or persistence.
    """
    if batch_size is not None and batch_size < 1:
        raise ValueError("answer generation batch_size must be at least 1")
    generator = None

    def next_step(state: AnswerGenerationState) -> str:
        return (
            "generate_batch"
            if state.get("next_offset", 0) < len(state.get("target_question_ids") or [])
            else "persist"
        )

    def plan(state: AnswerGenerationState) -> dict:
        job = AnswerGenerationJob.objects.select_related("ingestion_job").get(
            pk=state["answer_job_id"]
        )
        planned = plan_answer_generation(job)
        target_ids = list(planned.get("target_question_ids") or [])
        return {
            **planned,
            "batch_size": batch_size or len(target_ids) or 1,
            "next_offset": 0,
        }

    def generate_batch(state: AnswerGenerationState) -> dict:
        nonlocal generator
        question_ids = list(state.get("target_question_ids") or [])
        start = int(state.get("next_offset", 0))
        end = min(start + int(state["batch_size"]), len(question_ids))
        if generator is None:
            generator = generator_factory()
        result = generator.generate(question_ids[start:end])
        return {
            "answers": list(result.accepted),
            "missing_question_ids": list(result.missing_ids),
            "duplicate_question_ids": list(result.duplicate_ids),
            "unexpected_question_ids": list(result.unexpected_ids),
            "blank_question_ids": list(result.blank_ids),
            "next_offset": end,
        }

    def persist(state: AnswerGenerationState) -> dict:
        job = AnswerGenerationJob.objects.select_related("ingestion_job").get(
            pk=state["answer_job_id"]
        )
        return persist_generated_answers(job, list(state.get("answers") or []))

    graph = StateGraph(AnswerGenerationState)
    graph.add_node("plan", plan)
    graph.add_node("generate_batch", generate_batch)
    graph.add_node("persist", persist)
    graph.set_entry_point("plan")
    graph.add_conditional_edges("plan", next_step)
    graph.add_conditional_edges("generate_batch", next_step)
    graph.add_edge("persist", END)
    return graph.compile(checkpointer=checkpointer)
