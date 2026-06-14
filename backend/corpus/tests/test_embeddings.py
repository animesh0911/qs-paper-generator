"""Behavior tests for corpus-owned embedding persistence and population.

The tests exercise the public corpus seams against real Postgres because
pgvector extension ownership, vector persistence, and nearest-neighbor behavior
are integration contracts rather than in-memory implementation details.
"""

from __future__ import annotations

import math

import pytest
from django.contrib.postgres.search import SearchVector
from django.db import IntegrityError, connection, transaction
from django.test.utils import CaptureQueriesContext

from bank.models import Chapter
from corpus.embeddings import (
    EmbeddingPopulationRequest,
    EmbeddingProfile,
    RetrievalChunkEmbeddingPopulator,
)
from corpus.models import (
    ChapterMapNode,
    RetrievalChunk,
    TextbookDocument,
    TextbookElement,
)
from corpus.retrieval import (
    PostgresTextbookRetriever,
    PostgresVectorTextbookRetriever,
    TextbookRetrievalRequest,
)
from corpus.tests.fakes import FixedEmbeddingClient


@pytest.fixture
def chunk(db):
    chapter = Chapter.objects.get(slug="carbon-and-its-compounds")
    document = TextbookDocument.objects.create(
        chapter=chapter,
        source_file_name="jesc104.pdf",
        source_hash="a" * 64,
        extractor_name="Docling",
        extractor_version="2.102.1",
        canonical_json_path="content/ncert/jesc104/jesc104.json",
        canonical_json_hash="b" * 64,
        page_count=1,
    )
    element = TextbookElement.objects.create(
        document=document,
        stable_element_id="element-1",
        element_type="text",
        source_order=1,
        page_number=1,
        bbox={"l": 1, "t": 2, "r": 3, "b": 0},
        text="Carbon forms covalent bonds.",
    )
    node = ChapterMapNode.objects.create(
        document=document,
        stable_node_id="node-1",
        node_type=ChapterMapNode.NodeType.SECTION,
        title="4.1 Bonding in Carbon",
        source_element=element,
        source_start=1,
        source_end=1,
        page_start=1,
        page_end=1,
        element_count=1,
    )
    return RetrievalChunk.objects.create(
        document=document,
        chapter=chapter,
        chapter_map_node=node,
        stable_chunk_id="chunk-1",
        text="4.1 Bonding in Carbon\nCarbon forms covalent bonds.",
        source_element_ids=["element-1"],
        page_start=1,
        page_end=1,
        content_types=["text"],
        citation={"pages": [1]},
    )


@pytest.mark.django_db
def test_pgvector_extension_and_retrieval_chunk_vector_are_migration_owned(chunk):
    """A migrated database must store vectors without any manual setup step."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        extension = cursor.fetchone()

    chunk.embedding = [1.0, 2.0, 3.0]
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
    chunk.refresh_from_db()

    assert extension is not None
    assert list(chunk.embedding) == [1.0, 2.0, 3.0]
    assert chunk.embedding_model == "fixed-vector-test"
    assert chunk.embedding_version == "v1"
    assert chunk.embedding_dimensions == 3


@pytest.mark.parametrize(
    ("profile_kwargs", "message"),
    [
        ({"model": "x" * 201, "version": "v1", "dimensions": 3}, "model"),
        ({"model": "model", "version": "x" * 101, "dimensions": 3}, "version"),
    ],
)
def test_embedding_profile_rejects_values_that_persistence_cannot_store(
    profile_kwargs, message
):
    """The EmbeddingClient interface must fail before persistence limits do."""
    with pytest.raises(ValueError, match=message):
        EmbeddingProfile(**profile_kwargs)


@pytest.mark.django_db
def test_retrieval_chunk_rejects_incomplete_embedding_profile(chunk):
    """A vector without its complete profile is unsafe to retrieve."""
    chunk.embedding = [1.0, 2.0, 3.0]

    with pytest.raises(IntegrityError), transaction.atomic():
        chunk.save(update_fields=["embedding"])


@pytest.mark.django_db
def test_embedding_population_skips_chunks_already_matching_the_profile(chunk):
    """Reruns must not pay to reproduce vectors already stored for a profile."""
    client = FixedEmbeddingClient({chunk.text: (1.0, 0.0, 0.0)})
    request = EmbeddingPopulationRequest(
        document=chunk.document,
        client=client,
        batch_size=1,
    )

    first = RetrievalChunkEmbeddingPopulator().populate(request)
    repeated = RetrievalChunkEmbeddingPopulator().populate(request)
    chunk.refresh_from_db()

    assert first.populated_count == 1
    assert first.skipped_count == 0
    assert repeated.populated_count == 0
    assert repeated.skipped_count == 1
    assert client.calls == [(chunk.text,)]
    assert list(chunk.embedding) == [1.0, 0.0, 0.0]


@pytest.mark.django_db
def test_embedding_population_replaces_a_different_profile_version(chunk):
    """A requested profile change must replace rather than skip an old vector."""
    first = FixedEmbeddingClient({chunk.text: (1.0, 0.0, 0.0)})
    updated = FixedEmbeddingClient(
        {chunk.text: (0.0, 1.0, 0.0)},
        version="v2",
    )
    populator = RetrievalChunkEmbeddingPopulator()

    populator.populate(
        EmbeddingPopulationRequest(document=chunk.document, client=first)
    )
    result = populator.populate(
        EmbeddingPopulationRequest(document=chunk.document, client=updated)
    )
    chunk.refresh_from_db()

    assert result.populated_count == 1
    assert result.skipped_count == 0
    assert updated.calls == [(chunk.text,)]
    assert list(chunk.embedding) == [0.0, 1.0, 0.0]
    assert chunk.embedding_version == "v2"


@pytest.mark.django_db
def test_embedding_population_replaces_a_different_profile_dimension(chunk):
    """Dimension changes must never reuse vectors from an incompatible profile."""
    first = FixedEmbeddingClient({chunk.text: (1.0, 0.0, 0.0)})
    resized = FixedEmbeddingClient(
        {chunk.text: (0.0, 1.0, 0.0, 0.0)},
        dimensions=4,
    )
    populator = RetrievalChunkEmbeddingPopulator()

    populator.populate(
        EmbeddingPopulationRequest(document=chunk.document, client=first)
    )
    result = populator.populate(
        EmbeddingPopulationRequest(document=chunk.document, client=resized)
    )
    chunk.refresh_from_db()

    assert result.populated_count == 1
    assert result.skipped_count == 0
    assert resized.calls == [(chunk.text,)]
    assert list(chunk.embedding) == [0.0, 1.0, 0.0, 0.0]
    assert chunk.embedding_dimensions == 4


@pytest.mark.django_db
def test_embedding_population_resumes_after_a_failed_batch(chunk):
    """A retry must preserve successful batches and request only unfinished text."""
    second = RetrievalChunk.objects.create(
        document=chunk.document,
        chapter=chunk.chapter,
        chapter_map_node=chunk.chapter_map_node,
        stable_chunk_id="chunk-2",
        text="4.2 Versatile Nature of Carbon\nCarbon forms long chains.",
        source_element_ids=["element-1"],
        page_start=1,
        page_end=1,
        content_types=["text"],
        citation={"pages": [1]},
    )
    client = FixedEmbeddingClient(
        {
            chunk.text: (1.0, 0.0, 0.0),
            second.text: (0.0, 1.0, 0.0),
        },
        fail_on_call=2,
    )
    request = EmbeddingPopulationRequest(
        document=chunk.document,
        client=client,
        batch_size=1,
    )

    with pytest.raises(RuntimeError, match="configured fixed embedding failure"):
        RetrievalChunkEmbeddingPopulator().populate(request)

    chunk.refresh_from_db()
    second.refresh_from_db()
    assert list(chunk.embedding) == [1.0, 0.0, 0.0]
    assert second.embedding is None

    client.fail_on_call = None
    resumed = RetrievalChunkEmbeddingPopulator().populate(request)

    assert resumed.populated_count == 1
    assert resumed.skipped_count == 1
    assert client.calls == [(chunk.text,), (second.text,), (second.text,)]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("vectors", "message"),
    [
        ((), "wrong vector count"),
        (((1.0, 2.0),), "wrong dimensions"),
        (((1.0, math.inf, 3.0),), "non-finite"),
        (((0.0, 0.0, 0.0),), "zero-norm"),
    ],
)
def test_embedding_population_rejects_invalid_client_output(chunk, vectors, message):
    """Invalid adapter output must never create a partially trusted profile."""

    class InvalidEmbeddingClient:
        profile = FixedEmbeddingClient({}).profile

        def embed(self, texts):
            return vectors

    request = EmbeddingPopulationRequest(
        document=chunk.document,
        client=InvalidEmbeddingClient(),
    )

    with pytest.raises(ValueError, match=message):
        RetrievalChunkEmbeddingPopulator().populate(request)

    chunk.refresh_from_db()
    assert chunk.embedding is None
    assert chunk.embedding_model == ""
    assert chunk.embedding_version == ""
    assert chunk.embedding_dimensions is None


@pytest.mark.django_db
def test_dense_retrieval_orders_fixed_vectors_and_applies_corpus_filters(chunk):
    """Dense candidates must remain scoped to canonical corpus ownership."""
    other_node = ChapterMapNode.objects.create(
        document=chunk.document,
        stable_node_id="node-2",
        node_type=ChapterMapNode.NodeType.SECTION,
        title="4.2 Versatile Nature of Carbon",
        source_element=chunk.chapter_map_node.source_element,
        source_start=2,
        source_end=2,
        page_start=1,
        page_end=1,
        element_count=1,
    )
    table_chunk = RetrievalChunk.objects.create(
        document=chunk.document,
        chapter=chunk.chapter,
        chapter_map_node=other_node,
        stable_chunk_id="chunk-2",
        text="4.2 Versatile Nature of Carbon\nCompound formula table.",
        source_element_ids=["element-1"],
        page_start=1,
        page_end=1,
        content_types=["table"],
        citation={"pages": [1]},
        embedding=[0.9, 0.1, 0.0],
        embedding_model="fixed-vector-test",
        embedding_version="v1",
        embedding_dimensions=3,
    )
    RetrievalChunk.objects.create(
        document=chunk.document,
        chapter=chunk.chapter,
        chapter_map_node=chunk.chapter_map_node,
        stable_chunk_id="chunk-wrong-profile",
        text="Wrong profile",
        source_element_ids=["element-1"],
        page_start=1,
        page_end=1,
        content_types=["text"],
        citation={"pages": [1]},
        embedding=[1.0, 0.0, 0.0],
        embedding_model="another-model",
        embedding_version="v1",
        embedding_dimensions=3,
    )
    other_chapter = Chapter.objects.exclude(pk=chunk.chapter_id).first()
    other_document = TextbookDocument.objects.create(
        chapter=other_chapter,
        source_file_name="other.pdf",
        source_hash="c" * 64,
        extractor_name="Docling",
        extractor_version="2.102.1",
        canonical_json_path="content/ncert/other.json",
        canonical_json_hash="d" * 64,
        page_count=1,
    )
    other_element = TextbookElement.objects.create(
        document=other_document,
        stable_element_id="other-element",
        element_type="text",
        source_order=1,
        page_number=1,
        bbox={},
        text="Other chapter.",
    )
    other_chapter_node = ChapterMapNode.objects.create(
        document=other_document,
        stable_node_id="other-node",
        node_type=ChapterMapNode.NodeType.SECTION,
        title="Other Chapter",
        source_element=other_element,
        source_start=1,
        source_end=1,
        page_start=1,
        page_end=1,
        element_count=1,
    )
    RetrievalChunk.objects.create(
        document=other_document,
        chapter=other_chapter,
        chapter_map_node=other_chapter_node,
        stable_chunk_id="other-chunk",
        text="Other chapter nearest vector.",
        source_element_ids=["other-element"],
        page_start=1,
        page_end=1,
        content_types=["table"],
        citation={"pages": [1]},
        embedding=[1.0, 0.0, 0.0],
        embedding_model="fixed-vector-test",
        embedding_version="v1",
        embedding_dimensions=3,
    )
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
    client = FixedEmbeddingClient({"dense query": (1.0, 0.0, 0.0)})
    retriever = PostgresVectorTextbookRetriever(client)

    broad = retriever.retrieve(
        TextbookRetrievalRequest(
            chapter=chunk.chapter,
            query_text="dense query",
            limit=5,
        )
    )
    filtered = retriever.retrieve(
        TextbookRetrievalRequest(
            chapter=chunk.chapter,
            chapter_map_node=other_node,
            content_types=("table",),
            query_text="dense query",
            limit=5,
        )
    )

    assert [result.chunk for result in broad.results] == [chunk, table_chunk]
    assert [result.chunk for result in filtered.results] == [table_chunk]


@pytest.mark.django_db
def test_dense_retrieval_uses_the_fixed_profile_hnsw_index(chunk):
    """The infrastructure slice must prove its dense query is index-backed."""
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
    retriever = PostgresVectorTextbookRetriever(
        FixedEmbeddingClient({"dense query": (1.0, 0.0, 0.0)})
    )
    request = TextbookRetrievalRequest(
        chapter=chunk.chapter,
        query_text="dense query",
        limit=5,
    )

    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SET LOCAL enable_seqscan = off")
        with CaptureQueriesContext(connection) as queries:
            retriever.retrieve(request)
        dense_sql = next(
            query["sql"]
            for query in queries.captured_queries
            if "cosine_distance" not in query["sql"]
            and "corpus_retrievalchunk" in query["sql"]
            and "ORDER BY" in query["sql"]
        )
        cursor.execute(f"EXPLAIN {dense_sql}")
        plan = "\n".join(row[0] for row in cursor.fetchall())

    assert "retrieval_chunk_fixed_test_v1_hnsw" in plan, f"{dense_sql}\n{plan}"


@pytest.mark.django_db
def test_lexical_retrieval_remains_available_without_embeddings(chunk):
    """Dense readiness must not remove unembedded chunks from lexical search."""
    RetrievalChunk.objects.filter(pk=chunk.pk).update(
        search_vector=SearchVector("text", config="english")
    )
    request = TextbookRetrievalRequest(
        chapter=chunk.chapter,
        query_text="covalent bonds",
    )
    client = FixedEmbeddingClient({"covalent bonds": (1.0, 0.0, 0.0)})

    dense = PostgresVectorTextbookRetriever(client).retrieve(request)
    lexical = PostgresTextbookRetriever().retrieve(request)

    assert dense.results == ()
    assert [result.chunk for result in lexical.results] == [chunk]
