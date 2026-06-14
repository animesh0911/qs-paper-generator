"""Traceable chunk building and lexical retrieval for the NCERT corpus.

RetrievalChunks are rebuilt from persisted TextbookElements after the chapter
map establishes one section/topic owner for every source order. The module
owns deterministic chunk identities, citation integrity, and Postgres lexical
ranking without calling an embedding or model provider.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Protocol

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db import transaction
from django.db.models.functions import Cast
from pgvector.django import CosineDistance, VectorField

from bank.models import Chapter

from .embeddings import EmbeddingClient, validate_embedding_vectors
from .models import ChapterMapNode, RetrievalChunk, TextbookDocument, TextbookElement

_ATOMIC_CONTENT_TYPES = {"caption", "picture", "table"}
_LANDMARK_CONTENT_TYPES = {
    ChapterMapNode.NodeType.ACTIVITY,
    ChapterMapNode.NodeType.EXERCISES,
    ChapterMapNode.NodeType.QUESTIONS,
}
_CHEMICAL_TERM = re.compile(r"^(?:pH|[A-Z][a-z]?\d*)$")


@dataclass(frozen=True)
class ChunkBuildResult:
    document: TextbookDocument
    chunk_count: int


@dataclass(frozen=True)
class TextbookRetrievalRequest:
    chapter: Chapter
    query_text: str
    chapter_map_node: ChapterMapNode | None = None
    content_types: tuple[str, ...] = ()
    limit: int = 5


@dataclass(frozen=True)
class GroundingChunk:
    chunk: RetrievalChunk
    rank: float


@dataclass(frozen=True)
class GroundingContext:
    results: tuple[GroundingChunk, ...]


class TextbookRetriever(Protocol):
    def retrieve(self, request: TextbookRetrievalRequest) -> GroundingContext: ...


class PostgresTextbookRetriever:
    """Retrieve ranked chunks using only persisted Postgres lexical data."""

    def retrieve(self, request: TextbookRetrievalRequest) -> GroundingContext:
        if not request.query_text.strip():
            raise ValueError("query_text must not be blank.")
        if request.limit < 1:
            raise ValueError("limit must be positive.")
        if (
            request.chapter_map_node is not None
            and request.chapter_map_node.document.chapter_id != request.chapter.pk
        ):
            raise ValueError("chapter_map_node must belong to the requested Chapter.")

        query = self._query(request.query_text)
        chunks = RetrievalChunk.objects.filter(
            chapter=request.chapter,
            search_vector=query,
        ).select_related("document", "chapter", "chapter_map_node")
        if request.chapter_map_node is not None:
            chunks = chunks.filter(chapter_map_node=request.chapter_map_node)
        if request.content_types:
            chunks = chunks.filter(content_types__contains=list(request.content_types))
        ranked = chunks.annotate(
            rank=SearchRank("search_vector", query, cover_density=True)
        ).order_by("-rank", "stable_chunk_id")[: request.limit]
        return GroundingContext(
            results=tuple(
                GroundingChunk(chunk=chunk, rank=chunk.rank) for chunk in ranked
            )
        )

    @staticmethod
    def _query(query_text: str) -> SearchQuery:
        terms = list(
            dict.fromkeys(
                term.lower()
                for term in re.findall(r"[A-Za-z0-9]+", query_text)
                if len(term) >= 3 or _CHEMICAL_TERM.fullmatch(term)
            )
        )
        if not terms:
            raise ValueError("query_text must contain a searchable term.")
        return SearchQuery(" | ".join(terms), config="english", search_type="raw")


class PostgresVectorTextbookRetriever:
    """Retrieve dense candidates for one injected embedding profile."""

    def __init__(self, client: EmbeddingClient):
        self.client = client

    def retrieve(self, request: TextbookRetrievalRequest) -> GroundingContext:
        if not request.query_text.strip():
            raise ValueError("query_text must not be blank.")
        if request.limit < 1:
            raise ValueError("limit must be positive.")
        if (
            request.chapter_map_node is not None
            and request.chapter_map_node.document.chapter_id != request.chapter.pk
        ):
            raise ValueError("chapter_map_node must belong to the requested Chapter.")

        vectors = self.client.embed((request.query_text,))
        validate_embedding_vectors(
            vectors,
            expected_count=1,
            dimensions=self.client.profile.dimensions,
        )
        query_vector = vectors[0]

        chunks = RetrievalChunk.objects.filter(
            chapter=request.chapter,
            embedding__isnull=False,
            embedding_model=self.client.profile.model,
            embedding_version=self.client.profile.version,
            embedding_dimensions=self.client.profile.dimensions,
        ).select_related("document", "chapter", "chapter_map_node")
        if request.chapter_map_node is not None:
            chunks = chunks.filter(chapter_map_node=request.chapter_map_node)
        if request.content_types:
            chunks = chunks.filter(content_types__contains=list(request.content_types))
        distance = CosineDistance(
            Cast(
                "embedding",
                VectorField(dimensions=self.client.profile.dimensions),
            ),
            query_vector,
        )
        candidates = list(
            chunks.annotate(distance=distance).order_by("distance")[: request.limit]
        )
        ranked = sorted(
            candidates,
            key=lambda chunk: (float(chunk.distance), chunk.stable_chunk_id),
        )
        return GroundingContext(
            results=tuple(
                GroundingChunk(
                    chunk=chunk,
                    rank=1.0 - float(chunk.distance),
                )
                for chunk in ranked
            )
        )


class RetrievalChunkBuilder:
    """Rebuild stable citation-bearing chunks behind one public interface."""

    def __init__(self, max_chars: int = 1200):
        if max_chars < 1:
            raise ValueError("max_chars must be positive.")
        self.max_chars = max_chars

    @transaction.atomic
    def rebuild(self, document: TextbookDocument) -> ChunkBuildResult:
        sections = list(
            document.chapter_map_nodes.filter(node_type=ChapterMapNode.NodeType.SECTION)
            .select_related("parent")
            .order_by("source_start")
        )
        existing_texts = dict(
            document.retrieval_chunks.values_list("stable_chunk_id", "text")
        )
        keep_ids: set[str] = set()
        for section in sections:
            elements = list(
                document.elements.filter(
                    source_order__gte=section.source_start,
                    source_order__lte=section.source_end,
                ).order_by("source_order")
            )
            landmarks = list(
                document.chapter_map_nodes.filter(
                    parent=section,
                    node_type__in=_LANDMARK_CONTENT_TYPES,
                )
            )
            for group in self._groups(section, elements, landmarks):
                stable_chunk_id = self._stable_id(
                    document, section, [element.stable_element_id for element in group]
                )
                self._upsert(
                    document,
                    section,
                    stable_chunk_id,
                    group,
                    landmarks,
                    existing_texts.get(stable_chunk_id),
                )
                keep_ids.add(stable_chunk_id)

        document.retrieval_chunks.exclude(stable_chunk_id__in=keep_ids).delete()
        document.retrieval_chunks.update(
            search_vector=SearchVector("text", config="english")
        )
        return ChunkBuildResult(document=document, chunk_count=len(keep_ids))

    def _groups(
        self,
        section: ChapterMapNode,
        elements: list[TextbookElement],
        landmarks: list[ChapterMapNode],
    ) -> list[list[TextbookElement]]:
        groups: list[list[TextbookElement]] = []
        current: list[TextbookElement] = []
        current_type: str | None = None
        current_length = 0
        index = 0
        while index < len(elements):
            element = elements[index]
            if element.pk == section.source_element_id:
                index += 1
                continue
            adjacent = elements[index + 1] if index + 1 < len(elements) else None
            if (
                element.element_type in {"picture", "table"}
                and adjacent is not None
                and adjacent.element_type == "caption"
            ) or (
                element.element_type == "caption"
                and adjacent is not None
                and adjacent.element_type in {"picture", "table"}
            ):
                if current:
                    groups.append(current)
                    current = []
                    current_type = None
                    current_length = 0
                groups.append([element, adjacent])
                index += 2
                continue
            group_type = self._group_type(element, landmarks)
            text_length = len(self._element_text(element))
            atomic = element.element_type in _ATOMIC_CONTENT_TYPES
            boundary = current and (
                atomic
                or current_type != group_type
                or current_length + text_length > self.max_chars
            )
            if boundary:
                groups.append(current)
                current = []
                current_length = 0
            current.append(element)
            current_type = group_type
            current_length += text_length
            if atomic:
                groups.append(current)
                current = []
                current_type = None
                current_length = 0
            index += 1
        if current:
            groups.append(current)
        return groups

    def _upsert(
        self,
        document: TextbookDocument,
        section: ChapterMapNode,
        stable_chunk_id: str,
        elements: list[TextbookElement],
        landmarks: list[ChapterMapNode],
        previous_text: str | None,
    ) -> None:
        element_ids = [element.stable_element_id for element in elements]
        pages = sorted({element.page_number for element in elements})
        content_types = sorted(
            {
                content_type
                for element in elements
                for content_type in self._content_types(element, landmarks)
            }
        )
        body = "\n".join(
            text for element in elements if (text := self._element_text(element))
        )
        context_nodes = self._context_nodes(section, elements, landmarks)
        heading_context = "\n".join(node.title for node in context_nodes)
        context_elements = [
            node.source_element
            for node in context_nodes
            if node.source_element is not None
        ]
        text = f"{heading_context}\n{body}" if body else heading_context
        defaults = {
            "chapter": document.chapter,
            "chapter_map_node": section,
            "text": text,
            "source_element_ids": element_ids,
            "page_start": min(pages),
            "page_end": max(pages),
            "content_types": content_types,
            "citation": {
                "document_id": document.pk,
                "source_file_name": document.source_file_name,
                "source_hash": document.source_hash,
                "chapter_slug": document.chapter.slug,
                "chapter_map_node_id": section.stable_node_id,
                "source_element_ids": element_ids,
                "pages": pages,
                "context_source_element_ids": [
                    element.stable_element_id for element in context_elements
                ],
                "context_pages": sorted(
                    {element.page_number for element in context_elements}
                ),
            },
        }
        if previous_text is not None and previous_text != text:
            defaults.update(
                embedding=None,
                embedding_model="",
                embedding_version="",
                embedding_dimensions=None,
            )
        RetrievalChunk.objects.update_or_create(
            document=document,
            stable_chunk_id=stable_chunk_id,
            defaults=defaults,
        )

    @staticmethod
    def _group_type(element: TextbookElement, landmarks: list[ChapterMapNode]) -> str:
        for landmark in landmarks:
            if landmark.source_start <= element.source_order <= landmark.source_end:
                return landmark.node_type
        return element.element_type

    @classmethod
    def _content_types(
        cls, element: TextbookElement, landmarks: list[ChapterMapNode]
    ) -> set[str]:
        return {element.element_type, cls._group_type(element, landmarks)}

    @staticmethod
    def _element_text(element: TextbookElement) -> str:
        if element.text.strip():
            return element.text.strip()
        if element.element_type != "table":
            return ""
        cells = element.structured_data.get("data", {}).get("table_cells", [])
        return "\n".join(
            cell["text"].strip()
            for cell in cells
            if isinstance(cell, dict) and cell.get("text", "").strip()
        )

    @staticmethod
    def _context_nodes(
        section: ChapterMapNode,
        elements: list[TextbookElement],
        landmarks: list[ChapterMapNode],
    ) -> list[ChapterMapNode]:
        nodes = [section]
        parent = section.parent
        if parent is not None and parent.node_type == ChapterMapNode.NodeType.SECTION:
            nodes.insert(0, parent)
        first_order = elements[0].source_order
        landmark = next(
            (
                candidate
                for candidate in landmarks
                if candidate.source_start <= first_order <= candidate.source_end
            ),
            None,
        )
        if landmark is not None:
            nodes.append(landmark)
        return nodes

    @staticmethod
    def _stable_id(
        document: TextbookDocument,
        section: ChapterMapNode,
        element_ids: list[str],
    ) -> str:
        evidence = ":".join(
            [document.source_hash, section.stable_node_id, *element_ids]
        )
        return hashlib.sha256(evidence.encode()).hexdigest()
