"""Unit tests for PaperDocumentBuilder's question-level mapping.

These exercise _build_source / _build_metadata directly against a Question so
the contract mapping can't silently regress to hardcoded constants. Why this
matters: these mappers used to emit fixed strings regardless of the row — a
test that couldn't fail when the question changed. Now they must reflect it.
"""

from __future__ import annotations

import pytest

from bank.models import Chapter, Question
from papers.document import PaperDocumentBuilder


@pytest.mark.django_db
def test_build_source_reflects_question_provenance():
    chapter = Chapter.objects.get(slug="heredity")
    q = Question(
        chapter=chapter,
        section="B",
        qtype="short_answer",
        marks=3,
        cognitive_level="U",
        text="Explain monohybrid cross.",
        source_type="previous_year_paper",
        source_name="31-2-1 Science 2026",
        source_file_name="31-2-1.pdf",
        source_original_qnum="7",
    )
    source = PaperDocumentBuilder()._build_source(q)
    assert source["type"] == "previous_year_paper"
    assert source["name"] == "31-2-1 Science 2026"
    assert source["fileName"] == "31-2-1.pdf"
    assert source["originalQuestionNumber"] == "7"
    # pageNumber omitted when unset, not emitted as null.
    assert "pageNumber" not in source


@pytest.mark.django_db
def test_build_source_falls_back_for_blank_provenance():
    """Blank provenance fields still produce a valid contract source object."""
    q = Question(
        section="A",
        qtype="mcq",
        marks=1,
        text="Q?",
        cognitive_level="R",
        source_type="",
        source_name="",
    )
    source = PaperDocumentBuilder()._build_source(q)
    assert source == {
        "type": "question_bank",
        "name": "School Science Question Bank",
    }


@pytest.mark.django_db
def test_build_metadata_carries_topic_names_and_difficulty():
    chapter = Chapter.objects.get(slug="heredity")
    q = Question(
        chapter=chapter,
        section="B",
        qtype="short_answer",
        marks=3,
        cognitive_level="An",  # An → hard
        text="Q?",
        topic_names=["Monohybrid Cross"],
    )
    meta = PaperDocumentBuilder()._build_metadata(q)
    assert meta["topicNames"] == ["Monohybrid Cross"]
    assert meta["difficulty"] == "hard"
    assert meta["chapterNames"] == [chapter.name]


@pytest.mark.django_db
def test_build_source_emits_page_number_when_set():
    """pageNumber comes straight off the Question column, not a constant."""
    q = Question(
        section="B",
        qtype="short_answer",
        marks=3,
        cognitive_level="U",
        text="Q?",
        source_type="previous_year_paper",
        source_name="31-2-1 Science 2026",
        source_page_number=3,
    )
    source = PaperDocumentBuilder()._build_source(q)
    assert source["pageNumber"] == 3


@pytest.mark.django_db
def test_build_content_preserves_structured_content_verbatim():
    """A row with structured content emits it untouched (contract §10).

    The builder must not flatten or rebuild ingested region maps from rawText;
    that would silently drop assertion/reason/passage/options the ingestor
    extracted from the source PDF.
    """
    structured = {
        "assertion": [{"type": "paragraph", "text": "A: Mendel used pea plants."}],
        "reason": [{"type": "paragraph", "text": "R: Peas self-pollinate."}],
        "options": [
            {"label": "A", "content": [{"type": "paragraph", "text": "Both true"}]},
            {"label": "B", "content": [{"type": "paragraph", "text": "Both false"}]},
        ],
    }
    q = Question(
        section="A",
        qtype="assertion_reason",
        marks=1,
        cognitive_level="U",
        text="Assertion-Reason raw fallback text.",
        content=structured,
    )
    assert PaperDocumentBuilder()._build_content(q) == structured


@pytest.mark.django_db
def test_build_metadata_carries_subject_area_from_chapter():
    """Every question whose chapter has a subject_area exposes it in metadata."""
    chapter = Chapter.objects.get(slug="heredity")  # Biology
    q = Question(
        chapter=chapter,
        section="B",
        qtype="short_answer",
        marks=3,
        cognitive_level="U",
        text="Q?",
    )
    meta = PaperDocumentBuilder()._build_metadata(q)
    assert meta["subjectArea"] == "Biology"
    assert meta["cognitiveLevel"] == "understand"


@pytest.mark.django_db
def test_build_metadata_requires_table_reflects_content():
    """requiresTable is derived from a table item in content, not a flat flag."""
    builder = PaperDocumentBuilder()
    with_table = Question(
        section="C",
        qtype="table_based",
        marks=3,
        cognitive_level="U",
        text="Q?",
        content={"stem": [{"type": "table", "rows": [["a", "b"]]}]},
    )
    without_table = Question(
        section="C",
        qtype="short_answer",
        marks=3,
        cognitive_level="U",
        text="Q?",
        content={"stem": [{"type": "paragraph", "text": "no table"}]},
    )
    assert builder._build_metadata(with_table)["requiresTable"] is True
    assert builder._build_metadata(without_table)["requiresTable"] is False


@pytest.mark.django_db
def test_section_subtitle_uses_majority_subject_area():
    """Subtitle reflects the dominant subject_area; mixed sections stay untitled.

    Guards against a regression to the old hardcoded "Class X" subtitle: a
    section is labelled only when one subject actually dominates it.
    """
    bio = Chapter.objects.get(slug="heredity")  # Biology
    physics = Chapter.objects.get(slug="electricity")  # Physics
    builder = PaperDocumentBuilder()

    def q(pk, chapter):
        return Question(
            pk=pk,
            chapter=chapter,
            section="A",
            qtype="mcq",
            marks=1,
            cognitive_level="R",
            text="Q?",
        )

    by_pk = {1: q(1, bio), 2: q(2, bio), 3: q(3, physics)}
    # 2 Biology vs 1 Physics -> Biology majority.
    assert builder._section_subtitle([1, 2, 3], by_pk) == "Biology"
    # Even split -> no subtitle (never "Class X").
    assert builder._section_subtitle([1, 3], by_pk) is None


@pytest.mark.django_db
def test_build_content_emits_image_item_for_diagram_file():
    """A cropped diagram file becomes an image content item keyed by assetId."""
    q = Question(
        section="C",
        qtype="diagram_based",
        marks=3,
        cognitive_level="U",
        text="Label the diagram.",
    )
    q.diagram.name = "diagrams/abc12345-0.png"
    content = PaperDocumentBuilder()._build_content(q)
    assert {"type": "image", "assetId": "diagrams/abc12345-0.png"} in content["stem"]


@pytest.mark.django_db
def test_build_content_emits_placeholder_when_diagram_pending():
    """has_diagram with no extracted file leaves a visible placeholder."""
    q = Question(
        section="C",
        qtype="diagram_based",
        marks=3,
        cognitive_level="U",
        text="Label the diagram.",
        has_diagram=True,
    )
    content = PaperDocumentBuilder()._build_content(q)
    assert any(item.get("type") == "image_placeholder" for item in content["stem"])
