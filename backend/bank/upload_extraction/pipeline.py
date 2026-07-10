"""Shared upload OCR-markdown structuring pipeline.

This is the production/eval core for the Mistral OCR upload architecture. It is
small on purpose but it is not a throwaway eval helper: the LangGraph upload
flow and the live research runner both call this same module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from langchain_core.language_models import BaseChatModel

from bank.extraction import merge_page_payloads
from bank.ocr_extractor import (
    batch_ocr_markdown,
    is_english_question_page,
    structure_ocr_markdown,
)

BatchSize = int | Literal["all"]
FilterPolicy = Literal["english-question", "none"]


@dataclass(frozen=True)
class OcrMarkdownPage:
    """One OCR page markdown unit from a document parser/OCR engine."""

    index: int
    markdown: str

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> OcrMarkdownPage:
        return cls(
            index=int(raw.get("index", 0)),
            markdown=str(raw.get("markdown") or ""),
        )

    def as_raw(self) -> dict[str, Any]:
        return {"index": self.index, "markdown": self.markdown}


@dataclass(frozen=True)
class StructuredBatch:
    """One OCR-markdown batch sent to the structuring LLM."""

    batch_index: int
    pages: tuple[int, ...]  # one-based source page numbers for humans
    payload: dict[str, Any]

    @property
    def question_count(self) -> int:
        questions = self.payload.get("questions")
        return len(questions) if isinstance(questions, list) else 0

    def as_artifact(self) -> dict[str, Any]:
        return {
            "batch": self.batch_index,
            "pages": list(self.pages),
            "questions": self.question_count,
            "payload": self.payload,
        }


@dataclass(frozen=True)
class StructuringRun:
    """Structured payloads plus merged application questions."""

    selected_pages: tuple[OcrMarkdownPage, ...]
    batches: tuple[StructuredBatch, ...]
    questions: list[dict]


class UploadExtractionPipeline:
    """Deep module for OCR-markdown upload structuring.

    Interface: callers provide OCR page markdown, one chat model, a batch size,
    and a filter policy. The module owns page selection, batching, rendering,
    LLM structuring, and payload merging. LangGraph remains orchestration; this
    module owns the deterministic/upload-specific implementation sequence.
    """

    def __init__(self, chat_model: BaseChatModel):
        self.chat_model = chat_model

    def coerce_ocr_pages(self, pages: list[dict[str, Any]]) -> list[OcrMarkdownPage]:
        """Normalize OCR provider page dicts into the shared page type."""
        return [OcrMarkdownPage.from_raw(page) for page in pages]

    def select_pages(
        self,
        pages: list[OcrMarkdownPage],
        filter_policy: FilterPolicy = "english-question",
    ) -> list[OcrMarkdownPage]:
        """Choose OCR markdown pages worth sending to the structuring LLM."""
        if filter_policy == "none":
            return pages
        return [page for page in pages if is_english_question_page(page.markdown)]

    def batch_pages(
        self, pages: list[OcrMarkdownPage], batch_size: BatchSize
    ) -> list[list[OcrMarkdownPage]]:
        """Group OCR markdown pages into structuring LLM calls."""
        if batch_size == "all":
            return [pages] if pages else []
        size = int(batch_size)
        if size < 1:
            raise ValueError("batch_size must be >= 1 or 'all'")
        return [pages[i : i + size] for i in range(0, len(pages), size)]

    def render_batch(self, batch: list[OcrMarkdownPage]) -> str:
        """Render one batch in the same format production/evals structure."""
        return batch_ocr_markdown([page.as_raw() for page in batch])

    def structure_batch(
        self, batch: list[OcrMarkdownPage], *, batch_index: int = 1
    ) -> StructuredBatch:
        """Structure one already-selected OCR markdown batch."""
        payload = structure_ocr_markdown(self.render_batch(batch), self.chat_model)
        return StructuredBatch(
            batch_index=batch_index,
            pages=tuple(page.index + 1 for page in batch),
            payload=payload,
        )

    def structure_pages(
        self,
        *,
        pages: list[OcrMarkdownPage],
        batch_size: BatchSize,
        filter_policy: FilterPolicy = "english-question",
        max_batches: int = 0,
    ) -> StructuringRun:
        """Structure OCR markdown into merged upload questions."""
        selected = self.select_pages(pages, filter_policy)
        grouped = self.batch_pages(selected, batch_size)
        if max_batches > 0:
            grouped = grouped[:max_batches]

        batches = tuple(
            self.structure_batch(batch, batch_index=batch_index)
            for batch_index, batch in enumerate(grouped, start=1)
        )
        questions = merge_page_payloads([batch.payload for batch in batches])
        return StructuringRun(
            selected_pages=tuple(selected),
            batches=batches,
            questions=questions,
        )

