"""Question ingestion coordinator.

`Ingestor` persists extracted Question payloads. Extraction adapters live in
`bank.extraction`; diagram assets live behind the `DiagramCropper` seam. The
coordinator owns the batch tail: provenance, internal-choice flattening,
parse-quality assessment, guardrails, de-duplication, diagram cropping, and row
creation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from . import content as content_mod
from .diagram_cropper import DiagramCropper, PyMuPdfCropper
from .extraction import (
    MARKS_TO_SECTION,
    QTYPE_BY_MARKS,
    QTYPE_DEFAULT_MARKS,
    Extractor,
    GeminiExtractor,
    MakeChatModel,
    SeamExtractor,
    _QUESTION_SCHEMA,
    _coerce_cognitive_level,
    _coerce_figures,
    _coerce_primary_form,
    _coerce_question,
    _coerce_topic_names,
    _content_text,
    _detect_numerical,
    _fingerprint,
    _mentions_diagram,
    _page_message,
    _page_prompt,
    _split_internal_choice_question,
    _split_internal_choices,
    build_question_schema,
    count_pages,
    genai_to_json_schema,
    merge_page_payloads,
    slice_page,
    split_pages,
)
from .models import Chapter, CognitiveLevel, Question
from .question_content import normalise_question_content, repair_stem
from .question_shape import compute_parse_quality

_CBSE_TOKEN_RE = re.compile(r"[_\-]")
_YEAR_RE = re.compile(r"(\d{4})$")


def _parse_source_filename(path: Path) -> dict:
    """Parse a CBSE paper PDF path into source provenance fields."""
    file_name = path.name
    stem = path.stem
    year_match = _YEAR_RE.search(path.parent.name)
    year = year_match.group(1) if year_match else ""
    tokens = _CBSE_TOKEN_RE.split(stem)
    numeric_tokens = [t for t in tokens if t.isdigit()]
    alpha_tokens = [t for t in tokens if not t.isdigit() and t]
    parts = ["-".join(numeric_tokens)] if numeric_tokens else []
    parts += alpha_tokens
    if year:
        parts.append(year)
    return {
        "source_type": "previous_year_paper",
        "source_name": " ".join(parts),
        "source_file_name": file_name,
    }


@dataclass
class IngestResult:
    created: int
    skipped_duplicates: int = 0


@dataclass
class _Provenance:
    """Batch-level source provenance mapped onto flat Question source fields."""

    source_type: str
    source_name: str
    source_file_name: str

    @classmethod
    def from_filename(cls, file_name: str, source_type: str) -> "_Provenance":
        file_name = (file_name or "").strip()
        source_name = file_name.rsplit(".", 1)[0].strip() if file_name else ""
        return cls(
            source_type=(source_type or "").strip() or "previous_year_paper",
            source_name=source_name,
            source_file_name=file_name,
        )


@dataclass
class QuestionIngestBatch:
    """One batch entering the Ingestor tail."""

    raw_questions: list[dict]
    provenance: _Provenance
    school: object | None = None
    pdf_bytes: bytes | None = None
    ingestion_job: object | None = None


class Ingestor:
    """Persist extracted Questions through one deep ingestion tail.

    The Extractor seam is used only by `ingest`; all other front doors can call
    `ingest_questions` with already-extracted payloads and receive the same
    parse-quality, guardrail, de-duplication, cropping, and persistence behavior.
    """

    def __init__(
        self,
        extractor: Extractor | None = None,
        cropper: DiagramCropper | None = None,
    ):
        self.extractor = extractor or SeamExtractor()
        self.cropper = cropper or PyMuPdfCropper()

    def ingest(
        self,
        pdf_bytes: bytes,
        *,
        source_file_name: str = "",
        source_type: str = "",
        school=None,
    ) -> IngestResult:
        """Extract a paper PDF and persist Question rows."""
        return self.ingest_extracted(
            self.extractor.extract(pdf_bytes),
            source_file_name=source_file_name,
            source_type=source_type,
            school=school,
            pdf_bytes=pdf_bytes,
        )

    def ingest_extracted(
        self,
        raw_questions: list[dict],
        *,
        source_file_name: str = "",
        source_type: str = "",
        school=None,
        pdf_bytes: bytes | None = None,
        ingestion_job=None,
    ) -> IngestResult:
        """Persist already-extracted question dicts through the shared tail."""
        return self.ingest_questions(
            raw_questions,
            provenance=_Provenance.from_filename(source_file_name, source_type),
            school=school,
            pdf_bytes=pdf_bytes,
            ingestion_job=ingestion_job,
        )

    def ingest_questions(
        self,
        raw_questions: list[dict],
        *,
        provenance: _Provenance,
        school=None,
        pdf_bytes: bytes | None = None,
        ingestion_job=None,
        chapter_by_slug: dict[str, Chapter] | None = None,
    ) -> IngestResult:
        """Public entry point for the Ingestor tail.

        `raw_questions` may come from the live Extractor, a checkpointed workflow,
        an OCR experiment, or reviewed JSON. The tail is intentionally one module
        interface so row-shape behavior has locality.
        """
        if not raw_questions:
            return IngestResult(created=0)
        return self._ingest_batch(
            QuestionIngestBatch(
                raw_questions=raw_questions,
                provenance=provenance,
                school=school,
                pdf_bytes=pdf_bytes,
                ingestion_job=ingestion_job,
            ),
            chapter_by_slug=chapter_by_slug,
        )

    def _ingest_raw(
        self,
        raw_questions: list[dict],
        *,
        provenance: _Provenance,
        school,
        pdf_bytes: bytes | None,
        chapter_by_slug: dict[str, Chapter],
        ingestion_job=None,
    ) -> IngestResult:
        """Compatibility shim; new callers should use `ingest_questions`."""
        return self.ingest_questions(
            raw_questions,
            provenance=provenance,
            school=school,
            pdf_bytes=pdf_bytes,
            ingestion_job=ingestion_job,
            chapter_by_slug=chapter_by_slug,
        )

    def _ingest_batch(
        self,
        batch: QuestionIngestBatch,
        *,
        chapter_by_slug: dict[str, Chapter] | None = None,
    ) -> IngestResult:
        raw_questions = _split_internal_choices(batch.raw_questions)
        if not raw_questions:
            return IngestResult(created=0)

        if chapter_by_slug is None:
            chapter_by_slug = {c.slug: c for c in Chapter.objects.all()}

        for q in raw_questions:
            q["parse_quality"] = compute_parse_quality(q, q["qtype"])

        from .guardrails import apply_guardrails

        apply_guardrails(raw_questions, set(chapter_by_slug))

        fingerprints_by_index = [_fingerprint(q["text"]) for q in raw_questions]
        seen = set(
            Question.objects.filter(source_hash__in=fingerprints_by_index).values_list(
                "source_hash", flat=True
            )
        )
        unique_indices: list[int] = []
        for index, fingerprint in enumerate(fingerprints_by_index):
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            unique_indices.append(index)

        skipped = len(raw_questions) - len(unique_indices)
        raw_questions = [raw_questions[index] for index in unique_indices]
        fingerprints = [fingerprints_by_index[index] for index in unique_indices]
        if not raw_questions:
            return IngestResult(created=0, skipped_duplicates=skipped)

        primary_assets = (
            self.cropper.crop(batch.pdf_bytes, raw_questions, fingerprints)
            if batch.pdf_bytes is not None
            else [None] * len(raw_questions)
        )
        created = self._persist(
            raw_questions,
            fingerprints,
            primary_assets,
            chapter_by_slug,
            batch.provenance,
            batch.school,
            batch.ingestion_job,
        )
        return IngestResult(created=created, skipped_duplicates=skipped)

    @staticmethod
    def _persist(
        tagged: list[dict],
        fingerprints: list[str],
        primary_assets: list[str | None],
        chapter_by_slug: dict[str, Chapter],
        provenance: _Provenance,
        school=None,
        ingestion_job=None,
    ) -> int:
        rows: list[Question] = []
        for i, q in enumerate(tagged):
            primary_asset = primary_assets[i] if i < len(primary_assets) else None
            primary_form = q.get("primary_form", "none")
            content = normalise_question_content(q.get("content", {}))
            content = repair_stem(content, q["text"])
            has_diagram = (
                primary_asset is not None
                or primary_form == "diagram_based"
                or _mentions_diagram(q["text"])
                or content_mod.has_item(content, "image", "image_placeholder")
            )
            row = Question(
                school=school,
                ingestion_job=ingestion_job,
                chapter=chapter_by_slug.get(q.get("chapter_slug")),
                section=q["section"],
                qtype=q["qtype"],
                marks=q["marks"],
                cognitive_level=q.get("cognitive_level", CognitiveLevel.REMEMBER),
                text=q["text"],
                options=q.get("options", []),
                content=content,
                topic_names=q.get("topic_names", []),
                primary_form=primary_form,
                parse_quality=q.get("parse_quality", "partial"),
                review_flags=q.get("review_flags", []),
                answer=q.get("answer", ""),
                answer_source=q.get("answer_source", ""),
                verified=False,
                has_diagram=has_diagram,
                is_numerical=_detect_numerical(q["text"]),
                source_hash=fingerprints[i],
                source_type=provenance.source_type,
                source_name=provenance.source_name,
                source_file_name=provenance.source_file_name,
                source_page_number=q.get("source_page_number"),
            )
            if primary_asset:
                row.diagram.name = primary_asset
            rows.append(row)
        Question.objects.bulk_create(rows)
        return len(rows)
