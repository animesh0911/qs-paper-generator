"""Optional upload-answer generation as a resumable LangGraph graph.

Graph shape: ``plan`` (select unanswered extracted questions) → ``generate``
(the paid LLM pass) → ``persist`` (idempotently write answers to Question rows).
The paid node is checkpointed before persistence so a crash after the model
returns does not rebill on resume.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph

from bank.answer_generation import persist_generated_answers, plan_answer_generation
from bank.models import AnswerGenerationJob


class AnswerGenerationState(TypedDict, total=False):
    answer_job_id: int
    target_question_ids: list[int]
    answers: list[dict]
    total_count: int
    generated_count: int
    skipped_count: int


def build_answer_generation_graph(
    checkpointer: BaseCheckpointSaver,
    *,
    generator_factory: Callable[[], object],
):
    """Compile the optional-answer graph against the supplied checkpointer."""

    def plan(state: AnswerGenerationState) -> dict:
        job = AnswerGenerationJob.objects.select_related("ingestion_job").get(
            pk=state["answer_job_id"]
        )
        return plan_answer_generation(job)

    def generate(state: AnswerGenerationState) -> dict:
        question_ids = list(state.get("target_question_ids") or [])
        if not question_ids:
            return {"answers": []}
        return {"answers": list(generator_factory().generate(question_ids))}

    def persist(state: AnswerGenerationState) -> dict:
        job = AnswerGenerationJob.objects.select_related("ingestion_job").get(
            pk=state["answer_job_id"]
        )
        return persist_generated_answers(job, list(state.get("answers") or []))

    graph = StateGraph(AnswerGenerationState)
    graph.add_node("plan", plan)
    graph.add_node("generate", generate)
    graph.add_node("persist", persist)
    graph.set_entry_point("plan")
    graph.add_edge("plan", "generate")
    graph.add_edge("generate", "persist")
    graph.add_edge("persist", END)
    return graph.compile(checkpointer=checkpointer)
