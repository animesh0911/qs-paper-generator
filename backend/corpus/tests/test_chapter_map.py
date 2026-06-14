"""Behavior tests for deterministic corpus ChapterMap derivation.

The tests exercise the public builder and persisted map because later
RetrievalChunks and renderers depend on stable section ownership, not the
builder's internal representation.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from bank.models import Chapter
from corpus.chapter_map import ChapterMapBuilder
from corpus.models import (
    ChapterMapEdge,
    ChapterMapNode,
    TextbookDocument,
    TextbookElement,
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
        ("text", "Covalent bonding content", 1),
        ("section_header", "4.2 Versatile Nature of Carbon", 2),
        ("text", "Carbon chains", 2),
        ("section_header", "4.2.1 Saturated Compounds", 2),
        ("text", "Single bonds", 3),
        ("section_header", "Activity 4.2", 3),
        ("list_item", "Observe the carbon compounds.", 3),
        ("picture", "", 3),
        ("caption", "Figure 4.1 Carbon bonds", 3),
        ("text", "Compare the bonds shown in Fig. 4.1.", 3),
        ("text", "There is no local Table 9.9.", 3),
        ("table", "", 3),
        ("caption", "Table 4.1 Carbon compounds", 3),
        ("section_header", "Q U E S T I O N S", 3),
        ("list_item", "Why does carbon form bonds?", 3),
        ("section_header", "E X E R C I S E S", 3),
        ("list_item", "Draw a carbon compound.", 3),
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
            asset_path=(
                "figure.png"
                if element_type == "picture"
                else "table.png" if element_type == "table" else ""
            ),
        )
    return document


@pytest.mark.django_db
def test_numbered_sections_partition_every_element_once(document):
    """Every element needs one nearest topic for gap-free RetrievalChunk scope."""
    ChapterMapBuilder().rebuild(document)

    root = ChapterMapNode.objects.get(document=document, node_type="document")
    sections = list(
        ChapterMapNode.objects.filter(document=document, node_type="section").order_by(
            "source_start"
        )
    )

    assert (root.source_start, root.source_end, root.element_count) == (0, 18, 19)
    assert [
        (node.title, node.source_start, node.source_end, node.element_count)
        for node in sections
    ] == [
        ("4.1 Bonding in Carbon", 0, 2, 3),
        ("4.2 Versatile Nature of Carbon", 3, 4, 2),
        ("4.2.1 Saturated Compounds", 5, 18, 14),
    ]

    owned_orders = [
        source_order
        for node in sections
        for source_order in range(node.source_start, node.source_end + 1)
    ]
    assert owned_orders == list(range(19))
    assert sections[0].parent == root
    assert sections[1].parent == root
    assert sections[2].parent == sections[1]


@pytest.mark.django_db
def test_landmarks_are_contained_without_splitting_section_ownership(document):
    """Renderers need source landmarks while retrieval keeps one topic owner."""
    ChapterMapBuilder().rebuild(document)

    landmarks = list(
        ChapterMapNode.objects.exclude(node_type__in=["document", "section"]).order_by(
            "source_start"
        )
    )
    assert [
        (node.node_type, node.title, node.source_start, node.source_end)
        for node in landmarks
    ] == [
        ("activity", "Activity 4.2", 7, 14),
        ("figure", "Figure 4.1 Carbon bonds", 9, 10),
        ("table", "Table 4.1 Carbon compounds", 13, 14),
        ("questions", "Questions", 15, 16),
        ("exercises", "Exercises", 17, 18),
    ]
    section = ChapterMapNode.objects.get(title="4.2.1 Saturated Compounds")
    assert all(node.parent == section for node in landmarks)

    contains = ChapterMapEdge.objects.filter(edge_type="contains")
    assert contains.count() == ChapterMapNode.objects.count() - 1
    next_edges = list(
        ChapterMapEdge.objects.filter(edge_type="next").values_list(
            "source__title", "target__title"
        )
    )
    assert ("Activity 4.2", "Figure 4.1 Carbon bonds") in next_edges
    assert ("Figure 4.1 Carbon bonds", "Table 4.1 Carbon compounds") in next_edges


@pytest.mark.django_db
def test_activity_landmark_keeps_embedded_visuals_and_continuing_text(document):
    """An activity remains identifiable after an embedded figure or table."""
    ChapterMapBuilder().rebuild(document)

    activity = ChapterMapNode.objects.get(node_type="activity")

    assert (activity.source_start, activity.source_end) == (7, 14)


@pytest.mark.django_db
def test_sectionless_landmarks_belong_to_the_document_root(document):
    """Landmarks still need a retrieval owner when extraction finds no topics."""
    document.elements.all().delete()
    activity = TextbookElement.objects.create(
        document=document,
        stable_element_id="sectionless-activity",
        element_type="section_header",
        source_order=0,
        page_number=1,
        bbox={"l": 1, "t": 2, "r": 3, "b": 0},
        text="Activity 4.1",
    )
    TextbookElement.objects.create(
        document=document,
        stable_element_id="sectionless-content",
        element_type="text",
        source_order=1,
        page_number=1,
        bbox={"l": 1, "t": 2, "r": 3, "b": 0},
        text="Observe the sample.",
    )

    ChapterMapBuilder().rebuild(document)

    root = ChapterMapNode.objects.get(document=document, node_type="document")
    landmark = ChapterMapNode.objects.get(source_element=activity)
    assert landmark.parent == root


@pytest.mark.django_db
def test_references_edges_require_an_exact_local_landmark_and_keep_evidence(document):
    """The map must not invent semantic links from unresolved source mentions."""
    ChapterMapBuilder().rebuild(document)

    references = list(
        ChapterMapEdge.objects.filter(edge_type="references").select_related(
            "source", "target", "evidence_element"
        )
    )

    assert len(references) == 1
    edge = references[0]
    assert edge.source.title == "4.2.1 Saturated Compounds"
    assert edge.target.title == "Figure 4.1 Carbon bonds"
    assert edge.evidence_element.text == "Compare the bonds shown in Fig. 4.1."


@pytest.mark.django_db
def test_ambiguous_landmark_identifier_does_not_create_reference(document):
    """A repeated figure number cannot justify choosing one target arbitrarily."""
    TextbookElement.objects.create(
        document=document,
        stable_element_id="element-19",
        element_type="picture",
        source_order=19,
        page_number=3,
        bbox={"l": 1, "t": 2, "r": 3, "b": 0},
        asset_path="figure-b.png",
    )
    TextbookElement.objects.create(
        document=document,
        stable_element_id="element-20",
        element_type="caption",
        source_order=20,
        page_number=3,
        bbox={"l": 1, "t": 2, "r": 3, "b": 0},
        text="Figure 4.1 Another carbon view",
    )

    ChapterMapBuilder().rebuild(document)

    assert not ChapterMapEdge.objects.filter(edge_type="references").exists()


@pytest.mark.django_db
def test_chapter_map_api_returns_document_specific_semantic_graph(document, api_client):
    """Clients select one extraction explicitly and receive no layout state."""
    ChapterMapBuilder().rebuild(document)

    response = api_client.get(f"/api/corpus/documents/{document.pk}/chapter-map/")

    assert response.status_code == 200
    assert response.data["document"] == {
        "id": document.pk,
        "chapter": {
            "id": document.chapter_id,
            "slug": "carbon-and-its-compounds",
            "name": document.chapter.name,
            "order": 4,
        },
        "source_file_name": "jesc104.pdf",
        "page_count": 3,
    }
    assert response.data["nodes"]
    assert response.data["edges"]
    assert "position" not in response.data["nodes"][0]
    assert {
        "id",
        "type",
        "parent_id",
        "source_element_id",
        "source_range",
        "page_range",
        "element_count",
        "preview",
        "title",
    } == set(response.data["nodes"][0])

    anonymous = APIClient().get(f"/api/corpus/documents/{document.pk}/chapter-map/")
    assert anonymous.status_code in (401, 403)


@pytest.mark.django_db
def test_node_details_api_returns_owned_source_evidence(document, api_client):
    """A selected topic must resolve back to inspectable source and assets."""
    ChapterMapBuilder().rebuild(document)
    node = ChapterMapNode.objects.get(title="4.2.1 Saturated Compounds")

    response = api_client.get(
        f"/api/corpus/documents/{document.pk}/chapter-map/nodes/"
        f"{node.stable_node_id}/"
    )

    assert response.status_code == 200
    source = response.data["source"]
    assert [element["source_order"] for element in source["elements"]] == list(
        range(5, 19)
    )
    assert source["pages"] == [2, 3]
    assert {"section_header", "text", "picture", "table"} <= set(
        source["element_types"]
    )
    assert source["excerpt"].startswith("4.2.1 Saturated Compounds")
    assert source["assets"] == [
        {"element_id": "element-9", "type": "picture", "path": "figure.png"},
        {"element_id": "element-13", "type": "table", "path": "table.png"},
    ]
