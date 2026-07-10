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
from collections.abc import Callable
from typing import Annotated, Protocol, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph

from ai_services.llm import make_chat_model
from bank.extraction import (
    MakeChatModel,
    SeamExtractor,
    count_pages,
    merge_page_payloads,
    slice_page,
)
from bank.ingestor import Ingestor
from bank.models import IngestionJob


class PageExtractor(Protocol):
    def extract_page(self, page_bytes: bytes) -> dict: ...


ExtractorFactory = Callable[[], PageExtractor]


class ExtractionState(TypedDict, total=False):
    job_id: int
    total_pages: int
    next_page: int
    payloads: Annotated[list[dict], operator.add]
    created: int
    skipped: int


class OcrBatchExtractionState(TypedDict, total=False):
    job_id: int
    total_pages: int
    batch_pages: int
    next_batch: int
    ocr_pages: list[dict]
    payloads: Annotated[list[dict], operator.add]
    created: int
    skipped: int


def _load_job_pdf(job_id: int) -> tuple[IngestionJob, bytes]:
    job = IngestionJob.objects.get(pk=job_id)
    with job.pdf.open("rb") as fh:
        return job, fh.read()


def _next_step(state: ExtractionState) -> str:
    return "extract_page" if state["next_page"] < state["total_pages"] else "persist"


def _next_ocr_batch_step(state: OcrBatchExtractionState) -> str:
    return (
        "structure_batch"
        if state["next_batch"] * state["batch_pages"] < state["total_pages"]
        else "persist"
    )


def build_extraction_graph(
    checkpointer: BaseCheckpointSaver,
    make_model: MakeChatModel = make_chat_model,
    make_extractor: ExtractorFactory | None = None,
):
    """Compile the per-page extraction graph against the given checkpointer.

    ``make_extractor`` is the experiment seam for OCR-first adapters. When it is
    omitted, production keeps using the native-PDF ``SeamExtractor`` path.
    """
    extractor = (
        make_extractor() if make_extractor else SeamExtractor(make_model=make_model)
    )
    ingestor = Ingestor(extractor=extractor)

    def plan(state: ExtractionState) -> dict:
        _, pdf_bytes = _load_job_pdf(state["job_id"])
        total_pages = count_pages(pdf_bytes)
        # Publish the page count (and reset progress) on the ledger row so the
        # poll endpoint can show "page N of M" while the drain runs. A targeted
        # update() avoids clobbering the status the drainer owns.
        IngestionJob.objects.filter(pk=state["job_id"]).update(
            total_pages=total_pages, pages_done=0
        )
        return {"total_pages": total_pages, "next_page": 0}

    def extract_page(state: ExtractionState) -> dict:
        _, pdf_bytes = _load_job_pdf(state["job_id"])
        page = slice_page(pdf_bytes, state["next_page"])
        payload = extractor.extract_page(page)
        # Advance live progress as each (paid) page lands. On resume this is set
        # from next_page, so it stays correct without re-reading the checkpoint.
        pages_done = state["next_page"] + 1
        IngestionJob.objects.filter(pk=state["job_id"]).update(pages_done=pages_done)
        return {
            "payloads": [payload],
            "next_page": pages_done,
        }

    def persist(state: ExtractionState) -> dict:
        job, pdf_bytes = _load_job_pdf(state["job_id"])
        result = ingestor.ingest_extracted(
            merge_page_payloads(state["payloads"]),
            source_file_name=job.source_file_name,
            source_type=job.source_type,
            school=job.school,
            pdf_bytes=pdf_bytes,
            ingestion_job=job,
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


def build_ocr_batch_extraction_graph(
    checkpointer: BaseCheckpointSaver,
    *,
    batch_pages: int = 999,
):
    """Compile the whole-PDF OCR + structuring extraction graph.

    This experimental graph is optimized for bilingual CBSE papers: it OCRs the
    uploaded PDF once, filters to English/question pages, then sends the selected
    OCR markdown to the LLM in one large batch by default. Keeping the full
    English paper together avoids splitting long/internal-choice questions across
    page-count batch boundaries.
    """
    from bank.ocr_extractor import (
        MistralOcrClient,
        MistralOcrMarkdownExtractor,
        pages_from_ocr_response,
    )
    from bank.upload_extraction.pipeline import UploadExtractionPipeline

    ocr_client = MistralOcrClient()
    extractor = MistralOcrMarkdownExtractor(ocr_client=ocr_client)
    pipeline = UploadExtractionPipeline(extractor.chat_model)
    ingestor = Ingestor(extractor=extractor)

    def plan(state: OcrBatchExtractionState) -> dict:
        _, pdf_bytes = _load_job_pdf(state["job_id"])
        ocr = ocr_client.process_pdf(pdf_bytes)
        pages = [
            page.as_raw()
            for page in pipeline.select_pages(
                pipeline.coerce_ocr_pages(pages_from_ocr_response(ocr))
            )
        ]
        total_pages = len(pages)
        IngestionJob.objects.filter(pk=state["job_id"]).update(
            total_pages=total_pages,
            pages_done=0,
        )
        return {
            "ocr_pages": pages,
            "total_pages": total_pages,
            "batch_pages": batch_pages,
            "next_batch": 0,
        }

    def structure_batch(state: OcrBatchExtractionState) -> dict:
        start = state["next_batch"] * state["batch_pages"]
        end = start + state["batch_pages"]
        batch = pipeline.coerce_ocr_pages(state["ocr_pages"][start:end])
        payload = pipeline.structure_batch(batch).payload
        next_batch = state["next_batch"] + 1
        pages_done = min(end, state["total_pages"])
        IngestionJob.objects.filter(pk=state["job_id"]).update(pages_done=pages_done)
        return {
            "payloads": [payload],
            "next_batch": next_batch,
        }

    def persist(state: OcrBatchExtractionState) -> dict:
        job, _ = _load_job_pdf(state["job_id"])
        result = ingestor.ingest_extracted(
            merge_page_payloads(state.get("payloads", [])),
            source_file_name=job.source_file_name,
            source_type=job.source_type,
            school=job.school,
            # OCR batch payloads intentionally do not carry source-page figure
            # boxes yet, so skip diagram cropping for this experiment.
            pdf_bytes=None,
            ingestion_job=job,
        )
        return {"created": result.created, "skipped": result.skipped_duplicates}

    graph = StateGraph(OcrBatchExtractionState)
    graph.add_node("plan", plan)
    graph.add_node("structure_batch", structure_batch)
    graph.add_node("persist", persist)
    graph.set_entry_point("plan")
    graph.add_conditional_edges("plan", _next_ocr_batch_step)
    graph.add_conditional_edges("structure_batch", _next_ocr_batch_step)
    graph.add_edge("persist", END)
    return graph.compile(checkpointer=checkpointer)
