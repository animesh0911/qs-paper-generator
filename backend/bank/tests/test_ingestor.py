"""Tests for bank.ingestor — parse and tag pipeline.

Pure functions (strip_hindi, segment_questions) are tested without any mocks.
tag_with_claude is tested by injecting a fake Claude client via monkeypatching
the `anthropic` module imported inside the function.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from bank.ingestor import segment_questions, strip_hindi, tag_with_claude


# ---------------------------------------------------------------------------
# strip_hindi
# ---------------------------------------------------------------------------


def test_strip_hindi_removes_devanagari():
    text = "What is photosynthesis? प्रकाश संश्लेषण क्या है?"
    result = strip_hindi(text)
    assert "प्रकाश" not in result
    assert "What is photosynthesis?" in result


def test_strip_hindi_passthrough_english():
    text = "The speed of light is 3×10^8 m/s."
    assert strip_hindi(text) == text


def test_strip_hindi_empty():
    assert strip_hindi("") == ""


# ---------------------------------------------------------------------------
# segment_questions
# ---------------------------------------------------------------------------

_SAMPLE_TEXT = """\
SECTION A
1. Which gas is released during photosynthesis?
(A) CO2 (B) O2 (C) N2 (D) H2
2. The SI unit of electric current is:
(A) Volt (B) Ohm (C) Ampere (D) Watt

SECTION B
3. Define decomposition reaction and give one example.
4. What is the function of the stomata in a leaf?

SECTION C
5. Explain the process of digestion in the human stomach. [3]
"""


def test_segment_finds_section_a_questions():
    qs = segment_questions(_SAMPLE_TEXT)
    section_a = [q for q in qs if q["section"] == "A"]
    assert len(section_a) == 2


def test_segment_finds_section_b_questions():
    qs = segment_questions(_SAMPLE_TEXT)
    section_b = [q for q in qs if q["section"] == "B"]
    assert len(section_b) == 2


def test_segment_mcq_options_extracted():
    qs = segment_questions(_SAMPLE_TEXT)
    q1 = next(q for q in qs if q["section"] == "A")
    assert len(q1["options"]) == 4
    labels = [o["label"] for o in q1["options"]]
    assert labels == ["A", "B", "C", "D"]


def test_segment_mcq_stem_does_not_include_options():
    qs = segment_questions(_SAMPLE_TEXT)
    q1 = next(q for q in qs if q["section"] == "A")
    assert "(A)" not in q1["text"]


def test_segment_default_marks_by_section():
    qs = segment_questions(_SAMPLE_TEXT)
    for q in qs:
        if q["section"] == "A":
            assert q["marks"] == 1
        elif q["section"] == "B":
            assert q["marks"] == 2


def test_segment_explicit_marks_override():
    qs = segment_questions(_SAMPLE_TEXT)
    section_c = [q for q in qs if q["section"] == "C"]
    assert len(section_c) == 1
    assert section_c[0]["marks"] == 3


def test_segment_empty_text():
    assert segment_questions("") == []


def test_segment_no_sections():
    assert segment_questions("Some random text without headers") == []


# ---------------------------------------------------------------------------
# tag_with_claude
# ---------------------------------------------------------------------------


def _make_chapters(*slugs: str):
    return [SimpleNamespace(slug=s, name=s.replace("-", " ").title()) for s in slugs]


def _fake_claude_response(tags: list[dict]) -> MagicMock:
    """Build a mock anthropic.Anthropic().messages.create() return value."""
    content_block = SimpleNamespace(text=json.dumps(tags))
    message = SimpleNamespace(content=[content_block])
    client = MagicMock()
    client.messages.create.return_value = message
    return client


@pytest.mark.django_db
def test_tag_with_claude_adds_chapter_and_level():
    chapters = _make_chapters("electricity", "life-processes")
    raw = [
        {"section": "A", "qtype": "MCQ", "marks": 1, "text": "Q about electricity", "options": []},
        {"section": "B", "qtype": "VSA", "marks": 2, "text": "Q about life processes", "options": []},
    ]
    expected_tags = [
        {"index": 0, "chapter_slug": "electricity", "cognitive_level": "R"},
        {"index": 1, "chapter_slug": "life-processes", "cognitive_level": "U"},
    ]
    fake_client = _fake_claude_response(expected_tags)

    with patch("bank.ingestor.anthropic") as mock_anthropic:
        mock_anthropic.Anthropic.return_value = fake_client
        result = tag_with_claude(raw, chapters)

    assert result[0]["chapter_slug"] == "electricity"
    assert result[0]["cognitive_level"] == "R"
    assert result[1]["chapter_slug"] == "life-processes"
    assert result[1]["cognitive_level"] == "U"


@pytest.mark.django_db
def test_tag_with_claude_empty_input():
    result = tag_with_claude([], _make_chapters("electricity"))
    assert result == []


@pytest.mark.django_db
def test_tag_with_claude_preserves_original_fields():
    chapters = _make_chapters("electricity")
    raw = [{"section": "A", "qtype": "MCQ", "marks": 1, "text": "Q?", "options": []}]
    fake_client = _fake_claude_response(
        [{"index": 0, "chapter_slug": "electricity", "cognitive_level": "Ap"}]
    )

    with patch("bank.ingestor.anthropic") as mock_anthropic:
        mock_anthropic.Anthropic.return_value = fake_client
        result = tag_with_claude(raw, chapters)

    assert result[0]["section"] == "A"
    assert result[0]["marks"] == 1
    assert result[0]["text"] == "Q?"
