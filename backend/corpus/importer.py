"""Deep import module for existing canonical textbook extraction artifacts.

Callers provide one CorpusImportRequest. The module owns JSON validation,
normalization, provenance hashing, and atomic idempotent persistence so those
invariants do not leak into management commands or future batch importers.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from django.db import transaction

from bank.models import Chapter

from .chapter_map import ChapterMapBuilder
from .models import TextbookDocument, TextbookElement
from .textbook import DoclingNormalizer, canonical_json_hash, load_docling_json


@dataclass(frozen=True)
class CorpusImportRequest:
    chapter: Chapter
    canonical_json_path: Path
    source_file_name: str
    source_hash: str
    extractor_name: str
    extractor_version: str


@dataclass(frozen=True)
class CorpusImportResult:
    document: TextbookDocument
    element_count: int


class CorpusImporter:
    """Import one canonical extraction behind a single deterministic interface."""

    @transaction.atomic
    def import_document(self, request: CorpusImportRequest) -> CorpusImportResult:
        payload = load_docling_json(request.canonical_json_path)
        normalized = DoclingNormalizer(request.source_hash).normalize(payload)
        artifact_hash = canonical_json_hash(request.canonical_json_path)
        document, _ = TextbookDocument.objects.get_or_create(
            chapter=request.chapter,
            source_hash=request.source_hash,
            extractor_name=request.extractor_name,
            extractor_version=request.extractor_version,
            canonical_json_hash=artifact_hash,
            defaults={
                "source_file_name": request.source_file_name,
                "canonical_json_path": str(request.canonical_json_path),
                "page_count": len(payload.get("pages", {})),
            },
        )
        stable_ids = [element.stable_element_id for element in normalized]
        TextbookElement.objects.bulk_create(
            [
                TextbookElement(document=document, **element.__dict__)
                for element in normalized
            ],
            update_conflicts=True,
            update_fields=[
                "element_type",
                "source_order",
                "page_number",
                "bbox",
                "heading_path",
                "text",
                "structured_data",
                "asset_path",
            ],
            unique_fields=["document", "stable_element_id"],
        )
        document.elements.exclude(stable_element_id__in=stable_ids).delete()
        ChapterMapBuilder().rebuild(document)
        return CorpusImportResult(document=document, element_count=len(normalized))
