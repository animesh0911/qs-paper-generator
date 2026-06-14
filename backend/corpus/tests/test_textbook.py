"""Tests for deterministic TextbookDocument normalization and import.

These tests pin source evidence and stable identity because later chapter-map
and retrieval layers must be reproducible from the same canonical extraction.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from django.core.management import call_command

from corpus.models import (
    ChapterMapEdge,
    ChapterMapNode,
    RetrievalChunk,
    TextbookDocument,
    TextbookElement,
)
from corpus.textbook import DoclingNormalizer, load_docling_json

FIXTURE = Path(__file__).parent / "fixtures" / "jesc104_pages_1_8_16.json"
SOURCE_HASH = "efbb053ea8cedf29bc6891834613fdbcc17772e369f6b35405f3bb4701c41abe"


def test_normalizer_preserves_order_source_evidence_and_assets():
    """Representative pages remain inspectable rather than becoming flat text."""
    elements = DoclingNormalizer(SOURCE_HASH).normalize(load_docling_json(FIXTURE))

    assert [element.source_order for element in elements] == list(range(len(elements)))
    assert {element.page_number for element in elements} == {1, 8, 16}
    assert all(element.bbox for element in elements)

    table = next(element for element in elements if element.element_type == "table")
    assert table.structured_data["data"]["num_cols"] == 2
    picture = next(element for element in elements if element.element_type == "picture")
    assert picture.asset_path.endswith(".png")
    assert "/" not in picture.structured_data["image"]["uri"]


def test_normalizer_cleans_only_demonstrated_noise_and_builds_heading_paths():
    """Known duplicated/decorative headings do not poison later map hierarchy."""
    elements = DoclingNormalizer(SOURCE_HASH).normalize(load_docling_json(FIXTURE))
    texts = [element.text for element in elements]

    assert "Activity 4.1" in texts
    assert "Activity 4.1 Activity 4.1" not in texts
    assert not any(text.startswith("PDDDD") for text in texts)
    assert not any(element.element_type == "page_footer" for element in elements)

    heading = next(
        element
        for element in elements
        if element.text == "4.2.3 Will you be my Friend?"
    )
    assert heading.heading_path[-1] == "4.2.3 Will you be my Friend?"


def test_clean_text_preserves_legitimate_two_word_repetition():
    """Source fidelity matters more than guessing that short repetition is noise."""
    assert DoclingNormalizer._clean_text("iron iron") == "iron iron"
    assert DoclingNormalizer._clean_text("Activity 4.1 Activity 4.1") == "Activity 4.1"


def test_stable_ids_depend_on_source_and_docling_reference():
    """The same extraction is reproducible while a different PDF cannot collide."""
    payload = load_docling_json(FIXTURE)
    first = DoclingNormalizer(SOURCE_HASH).normalize(payload)
    repeated = DoclingNormalizer(SOURCE_HASH).normalize(payload)
    other_source = DoclingNormalizer("different-source").normalize(payload)

    assert [element.stable_element_id for element in first] == [
        element.stable_element_id for element in repeated
    ]
    assert first[0].stable_element_id != other_source[0].stable_element_id


def test_heading_paths_replace_siblings_and_keep_unnumbered_context():
    """Topic paths must not nest siblings or lose meaningful leaf headings."""
    payload = {
        "schema_name": "DoclingDocument",
        "texts": [
            _heading("#/texts/0", "4.2 Parent"),
            _heading("#/texts/1", "4.2.1 First"),
            _heading("#/texts/2", "4.2.2 Second"),
            _heading("#/texts/3", "Exercises"),
            _text("#/texts/4", "Practice the chapter."),
        ],
        "tables": [],
        "pictures": [],
        "groups": [],
        "form_items": [],
        "key_value_items": [],
        "body": {"children": [{"$ref": f"#/texts/{index}"} for index in range(5)]},
    }

    elements = DoclingNormalizer(SOURCE_HASH).normalize(payload)

    second = next(element for element in elements if element.text == "4.2.2 Second")
    practice = next(
        element for element in elements if element.text == "Practice the chapter."
    )
    assert second.heading_path == ["4.2 Parent", "4.2.2 Second"]
    assert practice.heading_path == ["4.2 Parent", "4.2.2 Second", "Exercises"]


def test_numbered_heading_discards_unrelated_opening_leaf_heading():
    """An opening activity must not become the parent of every later topic."""
    payload = {
        "schema_name": "DoclingDocument",
        "texts": [
            _heading("#/texts/0", "Activity 4.1"),
            _text("#/texts/1", "Opening activity."),
            _heading("#/texts/2", "4.1 Bonding in Carbon"),
            _text("#/texts/3", "Covalent bonds."),
        ],
        "tables": [],
        "pictures": [],
        "groups": [],
        "form_items": [],
        "key_value_items": [],
        "body": {"children": [{"$ref": f"#/texts/{index}"} for index in range(4)]},
    }

    elements = DoclingNormalizer(SOURCE_HASH).normalize(payload)
    covalent = next(
        element for element in elements if element.text == "Covalent bonds."
    )

    assert covalent.heading_path == ["4.1 Bonding in Carbon"]


def _heading(ref: str, text: str) -> dict:
    return {
        "self_ref": ref,
        "label": "section_header",
        "text": text,
        "prov": [{"page_no": 1, "bbox": {"l": 1, "t": 2, "r": 3, "b": 0}}],
    }


def _text(ref: str, text: str) -> dict:
    return {
        "self_ref": ref,
        "label": "text",
        "text": text,
        "prov": [{"page_no": 1, "bbox": {"l": 1, "t": 2, "r": 3, "b": 0}}],
    }


@pytest.mark.django_db
def test_import_command_is_idempotent_and_records_provenance():
    """Repeated imports preserve stable rows for later map and chunk references."""
    options = {
        "chapter": "carbon-and-its-compounds",
        "source_file_name": "jesc104.pdf",
        "source_hash": SOURCE_HASH,
        "extractor_version": "2.102.1",
    }
    call_command("import_textbook_document", FIXTURE, **options)
    first_ids = list(
        TextbookElement.objects.values_list("stable_element_id", flat=True)
    )
    first_pks = list(TextbookElement.objects.values_list("pk", flat=True))
    first_node_pks = list(
        ChapterMapNode.objects.order_by("stable_node_id").values_list("pk", flat=True)
    )
    first_edge_pks = list(
        ChapterMapEdge.objects.order_by("stable_edge_id").values_list("pk", flat=True)
    )
    first_chunk_pks = list(
        RetrievalChunk.objects.order_by("stable_chunk_id").values_list("pk", flat=True)
    )
    call_command("import_textbook_document", FIXTURE, **options)

    document = TextbookDocument.objects.get()
    assert document.source_hash == SOURCE_HASH
    assert document.extractor_name == "Docling"
    assert document.extractor_version == "2.102.1"
    assert document.page_count == 3
    assert TextbookElement.objects.count() == len(first_ids)
    assert (
        list(TextbookElement.objects.values_list("stable_element_id", flat=True))
        == first_ids
    )
    assert list(TextbookElement.objects.values_list("pk", flat=True)) == first_pks
    assert first_node_pks
    assert first_edge_pks
    assert first_chunk_pks
    assert (
        list(
            ChapterMapNode.objects.order_by("stable_node_id").values_list(
                "pk", flat=True
            )
        )
        == first_node_pks
    )
    assert (
        list(
            ChapterMapEdge.objects.order_by("stable_edge_id").values_list(
                "pk", flat=True
            )
        )
        == first_edge_pks
    )
    assert (
        list(
            RetrievalChunk.objects.order_by("stable_chunk_id").values_list(
                "pk", flat=True
            )
        )
        == first_chunk_pks
    )
