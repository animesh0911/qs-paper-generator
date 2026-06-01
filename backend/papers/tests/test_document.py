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
    assert source["sourceType"] == "previous_year_paper"
    assert source["sourceName"] == "31-2-1 Science 2026"
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
        "sourceType": "question_bank",
        "sourceName": "School Science Question Bank",
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
