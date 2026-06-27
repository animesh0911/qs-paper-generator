"""Bulk Question generation as a resumable LangGraph ``StateGraph``.

This is the generation counterpart of ``workflows.extraction`` (ADR-0005/0006):
a queued ``GenerationBatch`` is driven by a checkpointed graph so the single
paid model call is snapshotted the instant it returns. A run killed between the
model call and candidate persistence resumes from the post-``generate``
checkpoint instead of re-billing the model (Rule 13). The ``GenerationBatch``
ledger stays the queryable business record (status, the poll endpoint) and
points at the graph thread via ``thread_id``; everything in-flight lives here in
checkpointer state.

Graph shape: ``assemble`` (build request + grounding manifest, no LLM) →
``generate`` (exactly one ``QuestionGenerator.generate`` call) →
``validate_and_persist`` (deterministic validation + idempotent candidate
persist). The single paid step is isolated behind its own checkpoint so a crash
in the validate/persist tail never repeats it.

Patterns / invariants:
- ``build_generation_graph`` takes the checkpointer and the generator /
  context-assembler factories as arguments (the injection seams — no module
  globals), mirroring ``build_extraction_graph`` and ``Ingestor(extractor=...)``
  (Rules 9/11). Tests pass a fake generator and the real ``PostgresSaver``
  against the test database (mirroring ``test_extraction``).
- Nodes carry only the ``batch_id`` and small derived payloads in state; the
  batch row is re-read each step so checkpoints stay small and a resumed process
  reads the same durable source.
- ``validate_and_persist`` is idempotent under re-run: candidates are
  bulk-created only when none exist yet for the batch, so a crash between
  persisting and checkpointing cannot double-create rows.

Where it fits:
- Called by: ``bank.generation_batches.process_generation_batch`` via
  ``graph.invoke(state, {thread_id})`` (fresh) or ``graph.invoke(None, ...)``
  (resume).
- Calls into: ``bank.generation_batches`` (``request_from_batch``,
  ``grounding_manifest_from_batch``), ``bank.generation``
  (``validate_generated_questions``).
- Persisted via: LangGraph ``PostgresSaver`` (``workflows.checkpointer``).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph

from bank.generation import (
    node_question_targets,
    select_balanced_questions,
    validate_generated_questions,
)
from bank.models import GeneratedQuestionCandidate, GenerationBatch


class GenerationState(TypedDict, total=False):
    batch_id: int
    grounding_manifest: dict
    payloads: list[dict]
    valid_count: int


def build_generation_graph(
    checkpointer: BaseCheckpointSaver,
    *,
    generator_factory: Callable[[], object],
    context_assembler_factory: Callable[[], object],
):
    """Compile the bulk-generation graph against the given checkpointer."""
    # Imported lazily to avoid a circular import: ``generation_batches`` imports
    # this module's driver helpers.
    from bank.generation_batches import (
        grounding_manifest_from_batch,
        request_from_batch,
    )

    def assemble(state: GenerationState) -> dict:
        batch = GenerationBatch.objects.get(pk=state["batch_id"])
        manifest = grounding_manifest_from_batch(
            batch,
            context_assembler=(
                context_assembler_factory() if batch.chapter_map_node_ids else None
            ),
        )
        return {"grounding_manifest": manifest or {}}

    def generate(state: GenerationState) -> dict:
        batch = GenerationBatch.objects.get(pk=state["batch_id"])
        manifest = state.get("grounding_manifest") or None
        request = request_from_batch(batch, manifest)
        return {"payloads": list(generator_factory().generate(request))}

    def validate_and_persist(state: GenerationState) -> dict:
        batch = GenerationBatch.objects.get(pk=state["batch_id"])
        request = request_from_batch(batch, state.get("grounding_manifest") or None)
        result = validate_generated_questions({"questions": state["payloads"]}, request)
        if not result.valid_questions:
            raise ValueError("No valid generated candidates.")
        # The persistence boundary owns the even per-topic-node distribution: it
        # re-runs the deterministic trim so persisted candidates are balanced by
        # construction, regardless of how ``payloads`` reached this node. This is
        # idempotent over an already-balanced generator output (a no-op trim).
        targets = node_question_targets(
            tuple(batch.chapter_map_node_ids), batch.requested_count
        )
        candidates = select_balanced_questions(
            result.valid_questions, targets, state.get("grounding_manifest") or None
        )
        # Idempotent: a resumed run that already persisted skips re-creating.
        if not batch.candidates.exists():
            GeneratedQuestionCandidate.objects.bulk_create(
                [
                    GeneratedQuestionCandidate(
                        batch=batch,
                        payload=payload,
                        grounding_manifest=state.get("grounding_manifest") or {},
                    )
                    for payload in candidates
                ]
            )
        return {"valid_count": len(candidates)}

    graph = StateGraph(GenerationState)
    graph.add_node("assemble", assemble)
    graph.add_node("generate", generate)
    graph.add_node("validate_and_persist", validate_and_persist)
    graph.set_entry_point("assemble")
    graph.add_edge("assemble", "generate")
    graph.add_edge("generate", "validate_and_persist")
    graph.add_edge("validate_and_persist", END)
    return graph.compile(checkpointer=checkpointer)
