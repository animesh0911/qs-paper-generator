"""Runtime lexical, dense, and subtree retrieval for the NCERT corpus.

RetrievalChunk construction lives in ``corpus.chunks``. This module owns the
TextbookRetriever seam, GroundingContext manifests, retrieval scope validation,
and Postgres ranking without calling a generation model provider.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol

from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db.models import Q
from django.db.models.functions import Cast
from pgvector.django import CosineDistance, VectorField

from bank.models import Chapter

from .embeddings import EmbeddingClient, validate_embedding_vectors
from .models import ChapterMapNode, RetrievalChunk, TextbookElement

_DEFAULT_EXCLUDED_CONTEXT_TYPES = {
    ChapterMapNode.NodeType.EXERCISES,
    ChapterMapNode.NodeType.QUESTIONS,
}
_FORMULA_ONLY_CONTENT_TYPES = {"formula", "equation"}
_CHEMICAL_TERM = re.compile(r"^(?:pH|(?:[A-Z][a-z]?\d*)+)$")
GROUNDING_UNSUPPORTED_CONTENT_POLICY = (
    "Excluded by default: existing NCERT question/exercise chunks, "
    "picture-only chunks without captions, formula-only chunks, "
    "and diagram-image generation."
)



@dataclass(frozen=True)
class TextbookRetrievalRequest:
    chapter: Chapter
    query_text: str = ""
    chapter_map_node: ChapterMapNode | None = None
    chapter_map_node_ids: tuple[str, ...] = ()
    content_types: tuple[str, ...] = ()
    limit: int = 5
    context_chunk_limit: int | None = None


@dataclass(frozen=True)
class GroundingChunk:
    chunk: RetrievalChunk
    rank: float


@dataclass(frozen=True)
class GroundingContext:
    results: tuple[GroundingChunk, ...]
    diagnostics: dict[str, object] = field(default_factory=dict)

    def to_generation_manifest(self) -> dict[str, object]:
        """Return the corpus-owned manifest consumed by Question generation.

        The Bank should not rebuild citation, page, source element, or unsupported
        content policy details from RetrievalChunks. Those are Corpus and
        Grounding concerns, so this interface keeps generation callers on the
        ready-to-use manifest shape while this module owns the implementation.
        """
        excerpts = []
        for result in self.results:
            chunk = result.chunk
            excerpts.append(
                {
                    "citation_id": chunk.stable_chunk_id,
                    "chapter_map_node_id": chunk.chapter_map_node.stable_node_id,
                    "pages": list(
                        chunk.citation.get(
                            "pages", range(chunk.page_start, chunk.page_end + 1)
                        )
                    ),
                    "source_element_ids": list(
                        chunk.citation.get(
                            "source_element_ids", chunk.source_element_ids
                        )
                    ),
                    "content_types": list(chunk.content_types),
                    "text": chunk.text,
                }
            )

        chapter_slug = self.diagnostics.get("chapter_slug")
        if not isinstance(chapter_slug, str) and self.results:
            chapter_slug = self.results[0].chunk.chapter.slug

        return {
            "chapter_slug": chapter_slug or "",
            "requested_chapter_map_node_ids": list(
                self.diagnostics.get("requested_chapter_map_node_ids", [])
            ),
            "included_chapter_map_node_ids": list(
                self.diagnostics.get("included_chapter_map_node_ids", [])
            ),
            "excerpts": excerpts,
            "unsupported_content_policy": GROUNDING_UNSUPPORTED_CONTENT_POLICY,
            "diagnostics": dict(self.diagnostics),
        }


class TextbookRetriever(Protocol):
    def retrieve(self, request: TextbookRetrievalRequest) -> GroundingContext: ...


class ChapterMapContextAssembler:
    """Assemble selected ChapterMapNode subtree context without search."""

    def __init__(self, context_char_limit: int = 25000):
        if context_char_limit < 1:
            raise ValueError("context_char_limit must be positive.")
        self.context_char_limit = context_char_limit

    def retrieve(self, request: TextbookRetrievalRequest) -> GroundingContext:
        if request.context_chunk_limit is not None and request.context_chunk_limit < 1:
            raise ValueError("context_chunk_limit must be positive.")
        selected_ids = self._selected_ids(request)
        selected_nodes = list(
            ChapterMapNode.objects.filter(
                document__chapter=request.chapter,
                stable_node_id__in=selected_ids,
            )
            .select_related("document", "parent")
            .order_by("source_start", "stable_node_id")
        )
        if len(selected_nodes) != len(set(selected_ids)):
            raise ValueError(
                "chapter_map_node_ids must belong to the requested Chapter."
            )

        context_nodes = self._context_nodes(selected_nodes)
        chunks = list(
            RetrievalChunk.objects.filter(
                chapter=request.chapter,
                chapter_map_node_id__in=[node.pk for node in context_nodes],
            ).select_related("document", "chapter", "chapter_map_node")
        )
        if request.content_types:
            chunks = [
                chunk
                for chunk in chunks
                if self._matches_content_types(chunk, request.content_types)
            ]

        source_order_by_chunk_id = self._source_order_by_chunk_id(chunks)
        ordered_chunks = sorted(
            chunks,
            key=lambda chunk: (
                chunk.chapter_map_node.source_start,
                source_order_by_chunk_id.get(chunk.pk, chunk.page_start),
                chunk.stable_chunk_id,
            ),
        )
        filtered_chunks = [
            chunk for chunk in ordered_chunks if self._included_by_default(chunk)
        ]
        included: list[GroundingChunk] = []
        char_count = 0
        cap_reached = False
        for chunk in filtered_chunks:
            next_count = char_count + len(chunk.text)
            if next_count > self.context_char_limit:
                cap_reached = True
                break
            included.append(GroundingChunk(chunk=chunk, rank=float(len(included) + 1)))
            char_count = next_count
            if (
                request.context_chunk_limit is not None
                and len(included) >= request.context_chunk_limit
            ):
                break

        included_node_ids = list(
            dict.fromkeys(
                result.chunk.chapter_map_node.stable_node_id for result in included
            )
        )
        return GroundingContext(
            results=tuple(included),
            diagnostics={
                "mode": "chapter_map_subtree",
                "chapter_slug": request.chapter.slug,
                "requested_chapter_map_node_ids": list(selected_ids),
                "included_chapter_map_node_ids": included_node_ids,
                "included_chunk_count": len(included),
                "skipped_chunk_count": len(ordered_chunks) - len(included),
                "context_char_count": char_count,
                "context_char_limit": self.context_char_limit,
                "cap_reached": cap_reached,
                "chunk_limit_reached": (
                    request.context_chunk_limit is not None
                    and len(filtered_chunks) > len(included)
                    and len(included) >= request.context_chunk_limit
                ),
            },
        )

    @staticmethod
    def _selected_ids(request: TextbookRetrievalRequest) -> tuple[str, ...]:
        ids = request.chapter_map_node_ids
        if request.chapter_map_node is not None:
            if request.chapter_map_node.document.chapter_id != request.chapter.pk:
                raise ValueError(
                    "chapter_map_node must belong to the requested Chapter."
                )
            ids = (*ids, request.chapter_map_node.stable_node_id)
        ids = tuple(dict.fromkeys(ids))
        if not ids:
            raise ValueError("chapter_map_node_ids must not be empty.")
        return ids

    @staticmethod
    def _context_nodes(selected_nodes: list[ChapterMapNode]) -> list[ChapterMapNode]:
        documents = {node.document_id for node in selected_nodes}
        nodes = list(
            ChapterMapNode.objects.filter(document_id__in=documents)
            .select_related("parent")
            .order_by("source_start", "stable_node_id")
        )
        selected_pks = {node.pk for node in selected_nodes}
        nodes_by_pk = {node.pk: node for node in nodes}

        def in_selected_subtree(node: ChapterMapNode) -> bool:
            current: ChapterMapNode | None = node
            while current is not None:
                if current.pk in selected_pks:
                    return True
                current = nodes_by_pk.get(current.parent_id)
            return False

        return [
            node
            for node in nodes
            if in_selected_subtree(node)
            and node.node_type
            in {
                ChapterMapNode.NodeType.SECTION,
                ChapterMapNode.NodeType.DOCUMENT,
            }
        ]

    @staticmethod
    def _matches_content_types(
        chunk: RetrievalChunk, content_types: tuple[str, ...]
    ) -> bool:
        chunk_types = set(chunk.content_types)
        return any(content_type in chunk_types for content_type in content_types)

    @staticmethod
    def _source_order_by_chunk_id(chunks: list[RetrievalChunk]) -> dict[int, int]:
        element_ids_by_document: dict[int, set[str]] = {}
        for chunk in chunks:
            element_ids_by_document.setdefault(chunk.document_id, set()).update(
                chunk.source_element_ids
            )
        rows = TextbookElement.objects.filter(
            document_id__in=element_ids_by_document.keys(),
            stable_element_id__in={
                element_id
                for element_ids in element_ids_by_document.values()
                for element_id in element_ids
            },
        ).values_list("document_id", "stable_element_id", "source_order")
        source_order_by_element = {
            (document_id, stable_element_id): source_order
            for document_id, stable_element_id, source_order in rows
        }
        source_order_by_chunk_id = {}
        for chunk in chunks:
            source_orders = [
                source_order_by_element[(chunk.document_id, element_id)]
                for element_id in chunk.source_element_ids
                if (chunk.document_id, element_id) in source_order_by_element
            ]
            if source_orders:
                source_order_by_chunk_id[chunk.pk] = min(source_orders)
        return source_order_by_chunk_id

    @staticmethod
    def _included_by_default(chunk: RetrievalChunk) -> bool:
        content_types = set(chunk.content_types)
        if content_types & _DEFAULT_EXCLUDED_CONTEXT_TYPES:
            return False
        if content_types <= _FORMULA_ONLY_CONTENT_TYPES:
            return False
        if "picture" in content_types and "caption" not in content_types:
            return False
        return True


def _validate_search_request(request: TextbookRetrievalRequest) -> None:
    if not request.query_text.strip():
        raise ValueError("query_text must not be blank.")
    if request.limit < 1:
        raise ValueError("limit must be positive.")
    _validate_chapter_map_node(request)


def _validate_chapter_map_node(request: TextbookRetrievalRequest) -> None:
    if (
        request.chapter_map_node is not None
        and request.chapter_map_node.document.chapter_id != request.chapter.pk
    ):
        raise ValueError("chapter_map_node must belong to the requested Chapter.")
    if request.chapter_map_node_ids:
        found = set(
            ChapterMapNode.objects.filter(
                document__chapter=request.chapter,
                stable_node_id__in=request.chapter_map_node_ids,
            ).values_list("stable_node_id", flat=True)
        )
        missing = [
            node_id
            for node_id in request.chapter_map_node_ids
            if node_id not in found
        ]
        if missing:
            raise ValueError(
                "chapter_map_node_ids must belong to the requested Chapter."
            )


def _content_type_filter(content_types: tuple[str, ...]) -> Q:
    query = Q(content_types__contains=[content_types[0]])
    for content_type in content_types[1:]:
        query &= Q(content_types__contains=[content_type])
    return query


def _apply_retrieval_scope(chunks, request: TextbookRetrievalRequest):
    if request.chapter_map_node is not None:
        chunks = chunks.filter(chapter_map_node=request.chapter_map_node)
    if request.chapter_map_node_ids:
        chunks = chunks.filter(
            chapter_map_node__stable_node_id__in=request.chapter_map_node_ids
        )
    if request.content_types:
        chunks = chunks.filter(_content_type_filter(request.content_types))
    return chunks


class PostgresTextbookRetriever:
    """Retrieve ranked chunks using only persisted Postgres lexical data."""

    def retrieve(self, request: TextbookRetrievalRequest) -> GroundingContext:
        _validate_search_request(request)

        query = self._query(request.query_text)
        chunks = RetrievalChunk.objects.filter(
            chapter=request.chapter,
            search_vector=query,
        ).select_related("document", "chapter", "chapter_map_node")
        chunks = _apply_retrieval_scope(chunks, request)
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
        _validate_search_request(request)

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
        chunks = _apply_retrieval_scope(chunks, request)
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



# Re-exported for the existing corpus.retrieval interface. The implementation
# lives with import-time chunk construction policy.
from .chunks import ChunkBuildResult, RetrievalChunkBuilder  # noqa: E402
