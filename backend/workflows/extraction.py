"""Extraction as a resumable LangGraph ``StateGraph`` — one checkpoint per page.

This is the payoff slice of the LangGraph migration (#157, ADR-0005/ADR-0006):
a teacher-uploaded PDF is extracted one page per graph super-step, so the
``PostgresSaver`` checkpointer snapshots state after every paid model call. A
run killed mid-paper resumes from the last extracted page instead of
re-billing Gemini from page 1 (Rule 13). The split of responsibilities is
ADR-0006's: the ``IngestionJob`` ledger stays the queryable business record
(status, counts, the poll endpoint) and points at the graph thread via
``thread_id``; everything in-flight lives here, in checkpointer state.

Graph shape: ``plan`` (count pages) → ``extract_page`` (self-loop, exactly one
``SeamExtractor.extract_page`` call per step) → ``persist`` (merge payloads,
then ``Ingestor.ingest_extracted`` — the same guardrail/dedup/persist tail as
both existing front doors). ``persist`` is idempotent under re-run: the
``source_hash`` dedup can only skip, never duplicate, so a crash between
persisting rows and checkpointing cannot double-create ``Question`` rows.

Patterns / invariants:
- ``build_extraction_graph`` takes the checkpointer and ``make_model`` as
  arguments (the injection seams — no module globals), mirroring
  ``build_skeleton_graph`` and ``Ingestor(extractor=...)`` (Rules 9/11).
- State carries the ``job_id`` and the raw page payloads, never the PDF bytes:
  nodes re-read the PDF from the job row each step so checkpoints stay small
  and a resumed process reads the same durable source — scratch files would
  die with the killed process. Each step slices only its own page
  (``slice_page``), keeping total split work O(pages). The ``payloads`` list
  is ordered by page (``operator.add`` over a single sequential branch),
  which ``merge_page_payloads`` relies on for figure page-rewrite.
- ``count_pages`` never returns less than 1 (whole-PDF fallback, mirroring
  ``slice_page``), so the ``plan`` → ``extract_page`` edge needs no guard.

Where it fits:
- Called by: ``bank.management.commands.drain_ingestion_jobs`` via
  ``graph.invoke(state, {thread_id})`` (fresh) or ``graph.invoke(None, ...)``
  (resume).
- Calls into: ``bank.ingestor`` (``SeamExtractor``, ``Ingestor``,
  ``count_pages``, ``slice_page``, ``merge_page_payloads``).
- Persisted via: LangGraph ``PostgresSaver`` (``workflows.checkpointer``).
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph

from ai_services.llm import make_chat_model
from bank.ingestor import (
    Ingestor,
    MakeChatModel,
    SeamExtractor,
    count_pages,
    merge_page_payloads,
    slice_page,
)
from bank.models import IngestionJob


class ExtractionState(TypedDict, total=False):
    job_id: int
    total_pages: int
    next_page: int
    payloads: Annotated[list[dict], operator.add]
    created: int
    skipped: int


def _load_job_pdf(job_id: int) -> tuple[IngestionJob, bytes]:
    job = IngestionJob.objects.get(pk=job_id)
    with job.pdf.open("rb") as fh:
        return job, fh.read()


def _next_step(state: ExtractionState) -> str:
    return "extract_page" if state["next_page"] < state["total_pages"] else "persist"


def build_extraction_graph(
    checkpointer: BaseCheckpointSaver,
    make_model: MakeChatModel = make_chat_model,
):
    """Compile the per-page extraction graph against the given checkpointer."""
    extractor = SeamExtractor(make_model=make_model)
    ingestor = Ingestor(extractor=extractor)

    def plan(state: ExtractionState) -> dict:
        _, pdf_bytes = _load_job_pdf(state["job_id"])
        return {"total_pages": count_pages(pdf_bytes), "next_page": 0}

    def extract_page(state: ExtractionState) -> dict:
        _, pdf_bytes = _load_job_pdf(state["job_id"])
        page = slice_page(pdf_bytes, state["next_page"])
        return {
            "payloads": [extractor.extract_page(page)],
            "next_page": state["next_page"] + 1,
        }

    def persist(state: ExtractionState) -> dict:
        job, pdf_bytes = _load_job_pdf(state["job_id"])
        result = ingestor.ingest_extracted(
            merge_page_payloads(state["payloads"]),
            source_file_name=job.source_file_name,
            source_type=job.source_type,
            school=job.school,
            pdf_bytes=pdf_bytes,
        )
        return {"created": result.created, "skipped": result.skipped_duplicates}

    graph = StateGraph(ExtractionState)
    graph.add_node("plan", plan)
    graph.add_node("extract_page", extract_page)
    graph.add_node("persist", persist)
    graph.set_entry_point("plan")
    graph.add_edge("plan", "extract_page")
    graph.add_conditional_edges("extract_page", _next_step)
    graph.add_edge("persist", END)
    return graph.compile(checkpointer=checkpointer)
