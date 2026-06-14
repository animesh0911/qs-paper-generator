"""Behavior tests for traceable corpus chunks and lexical retrieval.

The tests use the public builder and retriever interfaces because citation
integrity, stable rebuilds, and topic-scoped retrieval are their contracts.
"""

from __future__ import annotations

import pytest

from bank.models import Chapter
from corpus.chapter_map import ChapterMapBuilder
from corpus.management.commands.benchmark_textbook_retrieval import (
    evaluate_queries,
    summary,
)
from corpus.models import (
    ChapterMapNode,
    RetrievalChunk,
    TextbookDocument,
    TextbookElement,
)
from corpus.retrieval import (
    PostgresTextbookRetriever,
    RetrievalChunkBuilder,
    TextbookRetrievalRequest,
)


@pytest.fixture
def document(db):
    chapter = Chapter.objects.get(slug="carbon-and-its-compounds")
    document = TextbookDocument.objects.create(
        chapter=chapter,
        source_file_name="jesc104.pdf",
        source_hash="a" * 64,
        extractor_name="Docling",
        extractor_version="2.102.1",
        canonical_json_path="content/ncert/jesc104/jesc104.json",
        canonical_json_hash="b" * 64,
        page_count=3,
    )
    rows = [
        ("text", "Chapter introduction", 1),
        ("section_header", "4.1 Bonding in Carbon", 1),
        ("text", "Carbon forms covalent bonds by sharing electrons.", 1),
        ("text", "Methane has four carbon hydrogen bonds.", 1),
        ("section_header", "4.2 Versatile Nature of Carbon", 2),
        ("text", "Carbon forms long chains because of catenation.", 2),
        ("section_header", "Activity 4.2", 2),
        ("list_item", "Observe the carbon compounds in the table.", 2),
        ("table", "", 2),
        ("caption", "Table 4.1 Carbon compounds", 2),
        ("section_header", "E X E R C I S E S", 3),
        ("list_item", "Explain why carbon forms many compounds.", 3),
    ]
    for source_order, (element_type, text, page_number) in enumerate(rows):
        TextbookElement.objects.create(
            document=document,
            stable_element_id=f"element-{source_order}",
            element_type=element_type,
            source_order=source_order,
            page_number=page_number,
            bbox={"l": 1, "t": 2, "r": 3, "b": 0},
            text=text,
            structured_data=(
                {
                    "data": {
                        "table_cells": [
                            {"text": "Compound"},
                            {"text": "Formula"},
                        ]
                    }
                }
                if element_type == "table"
                else {}
            ),
        )
    ChapterMapBuilder().rebuild(document)
    return document


@pytest.mark.django_db
def test_rebuild_creates_stable_traceable_chunks_with_one_topic_owner(document):
    """Retrieval evidence must remain exact and stable across unchanged rebuilds."""
    builder = RetrievalChunkBuilder(max_chars=120)

    first = builder.rebuild(document)
    first_rows = list(
        RetrievalChunk.objects.order_by("stable_chunk_id").values_list(
            "stable_chunk_id", "pk"
        )
    )
    repeated = builder.rebuild(document)

    assert first.chunk_count == repeated.chunk_count == RetrievalChunk.objects.count()
    assert (
        list(
            RetrievalChunk.objects.order_by("stable_chunk_id").values_list(
                "stable_chunk_id", "pk"
            )
        )
        == first_rows
    )
    assert all(
        chunk.chapter_map_node.node_type == ChapterMapNode.NodeType.SECTION
        for chunk in RetrievalChunk.objects.select_related("chapter_map_node")
    )
    assert all(chunk.source_element_ids for chunk in RetrievalChunk.objects.all())
    assert all(chunk.citation["pages"] for chunk in RetrievalChunk.objects.all())
    assert not any(
        {"element-3", "element-4"} <= set(chunk.source_element_ids)
        for chunk in RetrievalChunk.objects.all()
    )

    table_chunk = RetrievalChunk.objects.get(content_types__contains=["table"])
    assert table_chunk.chapter_map_node.title == "4.2 Versatile Nature of Carbon"
    assert table_chunk.source_element_ids == ["element-8", "element-9"]
    assert table_chunk.citation == {
        "document_id": document.pk,
        "source_file_name": "jesc104.pdf",
        "source_hash": "a" * 64,
        "chapter_slug": "carbon-and-its-compounds",
        "chapter_map_node_id": table_chunk.chapter_map_node.stable_node_id,
        "source_element_ids": ["element-8", "element-9"],
        "pages": [2],
        "context_source_element_ids": ["element-4", "element-6"],
        "context_pages": [2],
    }
    assert table_chunk.text.startswith("4.2 Versatile Nature of Carbon\n")
    assert RetrievalChunk.objects.filter(content_types__contains=["activity"]).exists()
    assert RetrievalChunk.objects.filter(content_types__contains=["exercises"]).exists()
    activity_chunk = RetrievalChunk.objects.filter(
        content_types__contains=["activity"]
    ).first()
    assert "Activity 4.2" in activity_chunk.text


@pytest.mark.django_db
def test_rebuild_preserves_current_embeddings_and_clears_stale_ones(document):
    """A stable chunk identity must not let a vector outlive changed source text."""
    builder = RetrievalChunkBuilder(max_chars=120)
    builder.rebuild(document)
    chunk = RetrievalChunk.objects.filter(content_types__contains=["text"]).first()
    chunk.embedding = [1.0, 0.0, 0.0]
    chunk.embedding_model = "fixed-vector-test"
    chunk.embedding_version = "v1"
    chunk.embedding_dimensions = 3
    chunk.save(
        update_fields=[
            "embedding",
            "embedding_model",
            "embedding_version",
            "embedding_dimensions",
        ]
    )

    builder.rebuild(document)
    chunk.refresh_from_db()
    assert list(chunk.embedding) == [1.0, 0.0, 0.0]

    element = TextbookElement.objects.get(
        document=document,
        stable_element_id=chunk.source_element_ids[-1],
    )
    element.text = f"{element.text} Updated."
    element.save(update_fields=["text"])

    builder.rebuild(document)
    chunk.refresh_from_db()
    assert chunk.embedding is None
    assert chunk.embedding_model == ""
    assert chunk.embedding_version == ""
    assert chunk.embedding_dimensions is None


@pytest.mark.django_db
def test_lexical_retriever_ranks_cited_chunks_and_applies_topic_and_type_filters(
    document,
):
    """Developers must inspect relevant excerpts without losing topic provenance."""
    RetrievalChunkBuilder(max_chars=120).rebuild(document)
    topic = ChapterMapNode.objects.get(title="4.2 Versatile Nature of Carbon")
    request = TextbookRetrievalRequest(
        chapter=document.chapter,
        chapter_map_node=topic,
        content_types=("table",),
        query_text="compound formula",
        limit=3,
    )

    context = PostgresTextbookRetriever().retrieve(request)

    assert len(context.results) == 1
    result = context.results[0]
    assert result.rank > 0
    assert result.chunk.chapter_map_node == topic
    assert "table" in result.chunk.content_types
    assert result.chunk.citation["source_element_ids"] == ["element-8", "element-9"]


@pytest.mark.django_db
def test_lexical_retriever_returns_no_context_for_unsupported_query(document):
    """Unsupported requests must not receive unrelated textbook evidence."""
    RetrievalChunkBuilder().rebuild(document)

    context = PostgresTextbookRetriever().retrieve(
        TextbookRetrievalRequest(
            chapter=document.chapter,
            query_text="photosynthesis chlorophyll stomata",
        )
    )

    assert context.results == ()


@pytest.mark.django_db
def test_lexical_retriever_preserves_short_science_terms(document):
    """Science retrieval must not discard meaningful symbols such as pH or O2."""
    element = TextbookElement.objects.get(stable_element_id="element-2")
    element.text = "The pH changes when O2 reacts with Fe."
    element.save(update_fields=["text"])
    RetrievalChunkBuilder().rebuild(document)

    for query in ("pH", "O2", "Fe"):
        context = PostgresTextbookRetriever().retrieve(
            TextbookRetrievalRequest(chapter=document.chapter, query_text=query)
        )
        assert context.results, query


@pytest.mark.django_db
def test_evaluation_rows_make_supported_hits_and_unsupported_misses_explicit(document):
    """A recorded baseline must calculate pass/fail instead of relying on judgment."""
    RetrievalChunkBuilder(max_chars=120).rebuild(document)
    evaluation = [
        {
            "id": "supported-catenation",
            "query": "catenation long chains",
            "supported": True,
            "expected_topic_titles": ["4.2 Versatile Nature of Carbon"],
            "expected_content_types": ["text"],
            "expected_source_pages": [2],
        },
        {
            "id": "unsupported-photosynthesis",
            "query": "photosynthesis chlorophyll stomata",
            "supported": False,
            "expected_topic_titles": [],
            "expected_content_types": [],
            "expected_source_pages": [],
        },
    ]

    rows = evaluate_queries(evaluation, document.chapter)

    assert [row["passed"] for row in rows] == [True, True]
    assert rows[0]["first_relevant_rank"] == 1
    assert summary(rows) == {
        "query_count": 2,
        "passed": 2,
        "failed": 0,
        "pass_rate": 1.0,
        "supported_passed": 1,
        "supported_count": 1,
        "unsupported_passed": 1,
        "unsupported_count": 1,
    }
