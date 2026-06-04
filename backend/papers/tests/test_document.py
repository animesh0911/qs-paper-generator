"""Unit tests for PaperDocumentBuilder's question-level mapping.

These exercise _build_source / _build_metadata directly against a Question so
the contract mapping can't silently regress to hardcoded constants. Why this
matters: these mappers used to emit fixed strings regardless of the row — a
test that couldn't fail when the question changed. Now they must reflect it.
"""

from __future__ import annotations

from types import SimpleNamespace

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


def _paper_with_settings(settings: dict | None):
    """A Paper stand-in carrying a School with the given settings (no DB)."""
    school = None if settings is None else SimpleNamespace(settings=settings)
    return SimpleNamespace(school=school)


def test_build_branding_reads_school_settings():
    """Branding is driven by the School row, so a school rebrands without code.

    Pins that name/logo/header come straight from settings JSON — a regression
    to a hardcoded school identity would fail here.
    """
    paper = _paper_with_settings(
        {
            "branding": {
                "schoolName": "Greenwood High School",
                "logoUrl": "https://cdn.example.com/logo.png",
                "examHeader": "Half-Yearly Examination 2026",
            }
        }
    )
    branding = PaperDocumentBuilder()._build_branding(paper)
    assert branding == {
        "schoolName": "Greenwood High School",
        "logoUrl": "https://cdn.example.com/logo.png",
        "examHeader": "Half-Yearly Examination 2026",
    }


def test_build_branding_emits_only_set_keys():
    """Unset branding keys are dropped, not emitted blank (contract §1)."""
    paper = _paper_with_settings({"branding": {"schoolName": "Greenwood High"}})
    assert PaperDocumentBuilder()._build_branding(paper) == {
        "schoolName": "Greenwood High"
    }


def test_build_branding_none_without_school_or_config():
    """No school, or a school with no branding, yields None (block omitted)."""
    builder = PaperDocumentBuilder()
    assert builder._build_branding(_paper_with_settings(None)) is None
    assert builder._build_branding(_paper_with_settings({})) is None
    assert builder._build_branding(_paper_with_settings({"branding": {}})) is None


# --- structured qtype content regions (contract §9, issue #46 AC-3) ---
#
# AC-3: structured qtypes render from `content`, not `rawText` fallback.
# These tests verify the pass-through and the fallback for each structured type.
# They run against Question instances (no DB needed) so they never require
# a real loaded bank.


def _question(**kwargs) -> Question:
    """Build an unsaved Question with defaults suitable for content tests."""
    from bank.models import Question

    defaults = dict(
        section="A",
        marks=1,
        cognitive_level="U",
        text="Default stem text.",
        options=[],
        content={},
        has_diagram=False,
    )
    defaults.update(kwargs)
    return Question(**defaults)


def test_assertion_reason_structured_content_passthrough():
    """assertion_reason with structured content emits all regions verbatim."""
    structured = {
        "assertion": [{"type": "paragraph", "text": "Mendel used pea plants."}],
        "reason": [{"type": "paragraph", "text": "Peas self-pollinate."}],
        "options": [
            {
                "label": "A",
                "content": [{"type": "paragraph", "text": "Both true, reason correct"}],
            },
            {
                "label": "B",
                "content": [
                    {"type": "paragraph", "text": "Both true, reason incorrect"}
                ],
            },
        ],
    }
    q = _question(qtype="assertion_reason", content=structured)
    result = PaperDocumentBuilder()._build_content(q)
    assert result == structured


def test_assertion_reason_fallback_has_only_stem():
    """assertion_reason without structured content falls back to stem only.

    Why: fallback_regions for AR is ('stem',) — the builder can't synthesise
    assertion/reason text from rawText, so it doesn't try. The frontend renders
    from rawText for unstructured AR rows.
    """
    q = _question(qtype="assertion_reason", content={}, text="Assertion: X. Reason: Y.")
    result = PaperDocumentBuilder()._build_content(q)
    assert "stem" in result
    assert "assertion" not in result
    assert "reason" not in result


def test_case_based_structured_content_passthrough():
    """case_based with structured content emits passage + subparts verbatim."""
    structured = {
        "passage": [{"type": "paragraph", "text": "Read the passage about circuits."}],
        "subparts": [
            {
                "label": "i",
                "marks": 1,
                "content": [{"type": "paragraph", "text": "What is current?"}],
            },
            {
                "label": "ii",
                "marks": 1,
                "content": [{"type": "paragraph", "text": "State Ohm's law."}],
            },
        ],
    }
    q = _question(qtype="case_based", content=structured)
    result = PaperDocumentBuilder()._build_content(q)
    assert result == structured


def test_case_based_fallback_has_only_stem():
    """case_based without structured content falls back to stem only."""
    q = _question(qtype="case_based", content={}, text="Read this passage.")
    result = PaperDocumentBuilder()._build_content(q)
    assert "stem" in result
    assert "passage" not in result
    assert "subparts" not in result


def test_internal_choice_structured_content_passthrough():
    """internal_choice with structured content emits choices (ChoiceGroup) verbatim."""
    structured = {
        "choices": [
            {
                "displayStyle": "or",
                "chooseCount": 1,
                "options": [
                    {
                        "label": "A",
                        "content": [
                            {"type": "paragraph", "text": "Explain photosynthesis."}
                        ],
                    },
                    {
                        "label": "B",
                        "content": [
                            {"type": "paragraph", "text": "Explain respiration."}
                        ],
                    },
                ],
            }
        ]
    }
    q = _question(qtype="internal_choice", content=structured)
    result = PaperDocumentBuilder()._build_content(q)
    assert result == structured


def test_internal_choice_fallback_has_only_stem():
    """internal_choice without structured content falls back to stem only."""
    q = _question(qtype="internal_choice", content={}, text="Answer any one.")
    result = PaperDocumentBuilder()._build_content(q)
    assert "stem" in result
    assert "choices" not in result


def test_content_regions_are_lists_not_scalars():
    """Every region value in _build_content output is a list, never a scalar.

    Why: contract §9 says each region holds ContentItem[] or option objects.
    A scalar would break the frontend's array iteration.
    """
    for qtype in ("mcq", "short_answer", "long_answer", "very_short_answer"):
        q = _question(qtype=qtype, content={})
        result = PaperDocumentBuilder()._build_content(q)
        for region, value in result.items():
            assert isinstance(
                value, list
            ), f"{qtype}: region '{region}' is {type(value).__name__}, expected list"
