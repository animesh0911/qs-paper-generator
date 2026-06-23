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
    ChapterMapContextAssembler,
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
        chapter_map_node_ids=(topic.stable_node_id,),
        content_types=("table", "activity"),
        query_text="compound formula",
        limit=3,
    )

    context = PostgresTextbookRetriever().retrieve(request)

    assert len(context.results) == 1
    assert context.diagnostics == {}
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
    assert context.diagnostics == {}


@pytest.mark.django_db
def test_search_retriever_still_rejects_default_blank_query(document):
    """Making query text optional for query-free seams must not weaken search."""
    RetrievalChunkBuilder().rebuild(document)

    with pytest.raises(ValueError, match="query_text must not be blank"):
        PostgresTextbookRetriever().retrieve(
            TextbookRetrievalRequest(chapter=document.chapter)
        )


@pytest.mark.django_db
def test_lexical_retriever_preserves_short_science_terms(document):
    """Science retrieval must not discard meaningful symbols such as pH or O2."""
    element = TextbookElement.objects.get(stable_element_id="element-2")
    element.text = "The pH changes when O2, Fe, and CO react."
    element.save(update_fields=["text"])
    RetrievalChunkBuilder().rebuild(document)

    for query in ("pH", "O2", "Fe", "CO"):
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


@pytest.mark.django_db
def test_context_assembler_returns_selected_subtree_in_source_order(document):
    """Selected-topic generation needs complete NCERT context, not search hits."""
    RetrievalChunkBuilder(max_chars=120).rebuild(document)
    topic = ChapterMapNode.objects.get(title="4.2 Versatile Nature of Carbon")

    context = ChapterMapContextAssembler().retrieve(
        TextbookRetrievalRequest(
            chapter=document.chapter,
            chapter_map_node_ids=(topic.stable_node_id,),
        )
    )

    assert [result.chunk.chapter_map_node.title for result in context.results] == [
        "4.2 Versatile Nature of Carbon",
        "4.2 Versatile Nature of Carbon",
        "4.2 Versatile Nature of Carbon",
    ]
    assert [
        result.chunk.citation["source_element_ids"] for result in context.results
    ] == [["element-5"], ["element-6", "element-7"], ["element-8", "element-9"]]
    assert context.diagnostics == {
        "mode": "chapter_map_subtree",
        "chapter_slug": "carbon-and-its-compounds",
        "requested_chapter_map_node_ids": [topic.stable_node_id],
        "included_chapter_map_node_ids": [topic.stable_node_id],
        "included_chunk_count": 3,
        "skipped_chunk_count": 1,
        "context_char_count": sum(len(result.chunk.text) for result in context.results),
        "context_char_limit": 25000,
        "cap_reached": False,
        "chunk_limit_reached": False,
    }


@pytest.mark.django_db
def test_context_assembler_includes_descendant_sections_and_filters_chunks(document):
    """A major topic owns nested topic context but not exercises or weak media."""
    RetrievalChunkBuilder(max_chars=120).rebuild(document)
    topic = ChapterMapNode.objects.get(title="4.2 Versatile Nature of Carbon")
    child_heading = TextbookElement.objects.create(
        document=document,
        stable_element_id="element-child-heading",
        element_type="section_header",
        source_order=12,
        page_number=3,
        bbox={},
        text="4.2.1 Chains, Branches and Rings",
    )
    child = ChapterMapNode.objects.create(
        document=document,
        stable_node_id="child-topic",
        node_type=ChapterMapNode.NodeType.SECTION,
        title="4.2.1 Chains, Branches and Rings",
        parent=topic,
        source_element=child_heading,
        source_start=12,
        source_end=13,
        page_start=3,
        page_end=3,
        element_count=2,
        preview="Chains, branches and rings",
    )
    RetrievalChunk.objects.create(
        document=document,
        chapter=document.chapter,
        chapter_map_node=child,
        stable_chunk_id="child-prose",
        text="4.2.1 Chains, Branches and Rings\nCarbon chains may be branched.",
        source_element_ids=["element-child-heading", "element-child-prose"],
        page_start=3,
        page_end=3,
        content_types=["section_header", "text"],
        citation={
            "chapter_map_node_id": child.stable_node_id,
            "source_element_ids": ["element-child-heading", "element-child-prose"],
            "pages": [3],
        },
    )
    RetrievalChunk.objects.create(
        document=document,
        chapter=document.chapter,
        chapter_map_node=topic,
        stable_chunk_id="picture-only",
        text="4.2 Versatile Nature of Carbon",
        source_element_ids=["element-picture"],
        page_start=3,
        page_end=3,
        content_types=["picture"],
        citation={
            "chapter_map_node_id": topic.stable_node_id,
            "source_element_ids": ["element-picture"],
            "pages": [3],
        },
    )
    RetrievalChunk.objects.create(
        document=document,
        chapter=document.chapter,
        chapter_map_node=topic,
        stable_chunk_id="formula-only",
        text="C2H6",
        source_element_ids=["element-formula"],
        page_start=3,
        page_end=3,
        content_types=["formula"],
        citation={
            "chapter_map_node_id": topic.stable_node_id,
            "source_element_ids": ["element-formula"],
            "pages": [3],
        },
    )

    context = ChapterMapContextAssembler().retrieve(
        TextbookRetrievalRequest(
            chapter=document.chapter,
            chapter_map_node_ids=(topic.stable_node_id,),
        )
    )

    assert [result.chunk.stable_chunk_id for result in context.results] == [
        RetrievalChunk.objects.get(source_element_ids=["element-5"]).stable_chunk_id,
        RetrievalChunk.objects.get(
            source_element_ids=["element-6", "element-7"]
        ).stable_chunk_id,
        RetrievalChunk.objects.get(
            source_element_ids=["element-8", "element-9"]
        ).stable_chunk_id,
        "child-prose",
    ]
    assert "picture-only" not in [
        result.chunk.stable_chunk_id for result in context.results
    ]
    assert "formula-only" not in [
        result.chunk.stable_chunk_id for result in context.results
    ]


@pytest.mark.django_db
def test_context_assembler_applies_optional_content_type_filters(document):
    """Callers can narrow selected-topic context without freeform Topic strings."""
    RetrievalChunkBuilder(max_chars=120).rebuild(document)
    topic = ChapterMapNode.objects.get(title="4.2 Versatile Nature of Carbon")

    context = ChapterMapContextAssembler().retrieve(
        TextbookRetrievalRequest(
            chapter=document.chapter,
            chapter_map_node_ids=(topic.stable_node_id,),
            content_types=("table",),
        )
    )

    assert len(context.results) == 1
    assert context.results[0].chunk.source_element_ids == ["element-8", "element-9"]
    assert "table" in context.results[0].chunk.content_types


@pytest.mark.django_db
def test_context_assembler_uses_element_source_order_not_stable_hash(document):
    """Textbook context must preserve narrative order inside one section."""
    RetrievalChunkBuilder(max_chars=120).rebuild(document)
    topic = ChapterMapNode.objects.get(title="4.2 Versatile Nature of Carbon")
    TextbookElement.objects.create(
        document=document,
        stable_element_id="early-extra",
        element_type="text",
        source_order=12,
        page_number=3,
        bbox={},
        text="Earlier extra context.",
    )
    TextbookElement.objects.create(
        document=document,
        stable_element_id="late-extra",
        element_type="text",
        source_order=13,
        page_number=3,
        bbox={},
        text="Later extra context.",
    )
    RetrievalChunk.objects.create(
        document=document,
        chapter=document.chapter,
        chapter_map_node=topic,
        stable_chunk_id="aaa-late-hash-sort",
        text="Later extra context.",
        source_element_ids=["late-extra"],
        page_start=3,
        page_end=3,
        content_types=["text"],
        citation={
            "chapter_map_node_id": topic.stable_node_id,
            "source_element_ids": ["late-extra"],
            "pages": [3],
        },
    )
    RetrievalChunk.objects.create(
        document=document,
        chapter=document.chapter,
        chapter_map_node=topic,
        stable_chunk_id="zzz-early-hash-sort",
        text="Earlier extra context.",
        source_element_ids=["early-extra"],
        page_start=3,
        page_end=3,
        content_types=["text"],
        citation={
            "chapter_map_node_id": topic.stable_node_id,
            "source_element_ids": ["early-extra"],
            "pages": [3],
        },
    )

    context = ChapterMapContextAssembler().retrieve(
        TextbookRetrievalRequest(
            chapter=document.chapter,
            chapter_map_node_ids=(topic.stable_node_id,),
        )
    )

    assert [result.chunk.source_element_ids for result in context.results][-2:] == [
        ["early-extra"],
        ["late-extra"],
    ]


@pytest.mark.django_db
def test_context_assembler_does_not_truncate_to_search_result_limit(document):
    """Selected-topic context includes the full subtree unless the context cap fires."""
    RetrievalChunkBuilder(max_chars=120).rebuild(document)
    topic = ChapterMapNode.objects.get(title="4.2 Versatile Nature of Carbon")
    for index in range(6):
        element_id = f"extra-{index}"
        TextbookElement.objects.create(
            document=document,
            stable_element_id=element_id,
            element_type="text",
            source_order=12 + index,
            page_number=3,
            bbox={},
            text=f"Extra context {index}.",
        )
        RetrievalChunk.objects.create(
            document=document,
            chapter=document.chapter,
            chapter_map_node=topic,
            stable_chunk_id=f"extra-{index}",
            text=f"Extra context {index}.",
            source_element_ids=[element_id],
            page_start=3,
            page_end=3,
            content_types=["text"],
            citation={
                "chapter_map_node_id": topic.stable_node_id,
                "source_element_ids": [element_id],
                "pages": [3],
            },
        )

    context = ChapterMapContextAssembler().retrieve(
        TextbookRetrievalRequest(
            chapter=document.chapter,
            chapter_map_node_ids=(topic.stable_node_id,),
        )
    )

    assert len(context.results) == 9
    assert context.diagnostics["cap_reached"] is False
    assert context.diagnostics["chunk_limit_reached"] is False


@pytest.mark.django_db
def test_context_assembler_reports_defensive_cap_without_splitting(document):
    """The context budget is a safety fuse, not multiple generation batches."""
    RetrievalChunkBuilder(max_chars=120).rebuild(document)
    topic = ChapterMapNode.objects.get(title="4.2 Versatile Nature of Carbon")

    context = ChapterMapContextAssembler(context_char_limit=80).retrieve(
        TextbookRetrievalRequest(
            chapter=document.chapter,
            chapter_map_node_ids=(topic.stable_node_id,),
        )
    )

    assert len(context.results) == 1
    assert context.diagnostics["cap_reached"] is True
    assert context.diagnostics["context_char_count"] == len(
        context.results[0].chunk.text
    )
    assert "chunks" not in context.diagnostics
    assert "text" not in context.diagnostics


@pytest.mark.django_db
def test_context_assembler_rejects_nodes_outside_requested_chapter(document):
    """Canonical ChapterMapNode filters must not cross Chapter boundaries."""
    other_chapter = Chapter.objects.get(slug="life-processes")
    other_document = TextbookDocument.objects.create(
        chapter=other_chapter,
        source_file_name="jesc106.pdf",
        source_hash="c" * 64,
        extractor_name="Docling",
        extractor_version="2.102.1",
        canonical_json_path="content/ncert/jesc106/jesc106.json",
        canonical_json_hash="d" * 64,
        page_count=1,
    )
    other_node = ChapterMapNode.objects.create(
        document=other_document,
        stable_node_id="other-node",
        node_type=ChapterMapNode.NodeType.SECTION,
        title="6.1 Life Processes",
        source_start=0,
        source_end=1,
        page_start=1,
        page_end=1,
        element_count=2,
    )

    with pytest.raises(
        ValueError, match="chapter_map_node_ids must belong to the requested Chapter"
    ):
        ChapterMapContextAssembler().retrieve(
            TextbookRetrievalRequest(
                chapter=document.chapter,
                chapter_map_node_ids=(other_node.stable_node_id,),
            )
        )
