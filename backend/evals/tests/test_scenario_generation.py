"""Generation scenario: fixture resolution, citation scoping, deterministic scoring."""

import json

import pytest

from bank.models import Chapter
from corpus.chapter_map import ChapterMapBuilder
from corpus.models import ChapterMapNode, TextbookDocument, TextbookElement
from evals.scenarios import generation
from evals.scenarios.generation import _resolve_fixture

MANIFEST = {
    "excerpts": [
        {"citation_id": "c1", "text": "Carbon forms covalent bonds."},
        {"citation_id": "c2", "text": "Diamond is a giant covalent structure."},
        {"citation_id": "c3", "text": "Unrelated excerpt about light refraction."},
    ]
}


def _question(question_citation_ids=(), answer_citation_ids=()):
    return {
        "raw_text": "Why does carbon form covalent bonds?",
        "question_citation_ids": list(question_citation_ids),
        "answer_citation_ids": list(answer_citation_ids),
    }


def test_cited_context_scopes_to_question_and_answer_citation_ids():
    excerpt_text_by_id = generation._excerpt_text_by_id(MANIFEST)
    question = _question(question_citation_ids=["c1"], answer_citation_ids=["c2"])

    context = generation._cited_context(question, excerpt_text_by_id)

    assert "covalent bonds" in context
    assert "giant covalent structure" in context
    assert "light refraction" not in context


def test_cited_context_dedupes_and_ignores_unknown_ids():
    excerpt_text_by_id = generation._excerpt_text_by_id(MANIFEST)
    question = _question(
        question_citation_ids=["c1", "c1", "does-not-exist"],
        answer_citation_ids=["c1"],
    )

    context = generation._cited_context(question, excerpt_text_by_id)

    assert context == "Carbon forms covalent bonds."


def _artifact(tmp_path, questions):
    artifact_path = tmp_path / "run.json"
    artifact_path.write_text(
        json.dumps(
            {
                "questions": questions,
                "grounding_manifest": {
                    "excerpts": [
                        {"citation_id": "c1", "text": "Carbon forms bonds."},
                        {"citation_id": "c3", "text": "Unrelated excerpt."},
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    return artifact_path


def test_score_unit_reports_deterministic_metrics(tmp_path):
    artifact_path = _artifact(tmp_path, [_question(question_citation_ids=["c1"])])
    record = {"artifacts_path": str(artifact_path), "batch_size": 1}

    accuracy = generation.score_unit(record)

    assert accuracy["yield"] == 1.0
    assert accuracy["near_duplicate_rate"] == 0.0
    assert accuracy["citation_support"]["n_reviewed"] == 1


def test_citation_support_reports_production_lexical_screen():
    manifest = {
        "excerpts": [
            {
                "citation_id": "c1",
                "text": "Carbon forms covalent bonds by sharing electrons "
                "between atoms.",
            }
        ]
    }
    supported = {
        "raw_text": "Why does carbon form covalent bonds?",
        "answer": "By sharing electrons between atoms.",
        "question_citation_ids": ["c1"],
        "answer_citation_ids": ["c1"],
    }
    uncited = {
        "raw_text": "What is Ohm's law?",
        "answer": "",
        "question_citation_ids": [],
        "answer_citation_ids": [],
    }

    support = generation._citation_support([supported, uncited], manifest)

    assert support["n_reviewed"] == 2
    assert support["question_supported_rate"] == 0.5
    assert support["answer_supported_rate"] == 0.5
    assert support["supported_rate"] == 0.5
    assert support["flags"]["missing_cited_text"] == 2


def test_golden_items_freeze_citation_scoped_context(tmp_path):
    artifact_path = _artifact(
        tmp_path,
        [_question(question_citation_ids=["c1"]), _question(), _question()],
    )
    record = {"artifacts_path": str(artifact_path), "scenario": "generation"}

    items = generation.golden_items(record, sample=2)

    assert [key for key, _, _ in items] == ["i:0", "i:1"]
    assert items[0][2] == "Carbon forms bonds."
    assert items[1][2] == ""


@pytest.fixture
def two_section_document(db):
    """A minimal chapter map: two sibling SECTION nodes in source order."""
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
    rows = [
        ("section_header", "4.1 First Topic", 1),
        ("text", "Some content under the first topic.", 1),
        ("section_header", "4.2 Second Topic", 1),
        ("text", "Some content under the second topic.", 1),
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
            structured_data={},
        )
    ChapterMapBuilder().rebuild(document)
    return chapter


@pytest.mark.django_db
def test_resolve_fixture_prefers_pinned_ids_over_the_runtime_selector(
    two_section_document,
):
    """A pinned id must win even when the selector would have picked another."""
    chapter = two_section_document
    second_section = ChapterMapNode.objects.get(
        document__chapter=chapter, title="4.2 Second Topic"
    )
    fixture = {
        "chapter_slug": chapter.slug,
        "chapter_map_node_ids": [second_section.stable_node_id],
        "node_selector": {"strategy": "first_major_topics", "count": 2},
    }

    resolved_chapter, node_ids = _resolve_fixture(fixture)

    assert resolved_chapter == chapter
    assert node_ids == (second_section.stable_node_id,)


@pytest.mark.django_db
def test_resolve_fixture_falls_back_to_selector_when_unpinned(two_section_document):
    """Without pinned ids, the documented runtime selector still applies."""
    chapter = two_section_document
    fixture = {
        "chapter_slug": chapter.slug,
        "chapter_map_node_ids": [],
        "node_selector": {"strategy": "first_major_topics", "count": 2},
    }

    _, node_ids = _resolve_fixture(fixture)

    assert len(node_ids) == 2
