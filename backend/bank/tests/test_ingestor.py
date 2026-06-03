"""Tests for bank.ingestor (Gemini native-PDF path).

The Ingestor coordinator is tested end-to-end with a stub Extractor — no live
Gemini call. GeminiExtractor's section-chunking + coercion is tested against a
stub LLMClient. Pure helpers (`_compute_parse_quality`, `_parse_source_filename`)
are tested directly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bank.ingestor import (
    GeminiExtractor,
    Ingestor,
    _compute_parse_quality,
    _parse_source_filename,
)
from bank.models import Chapter, Question

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


def _q(section="A", qtype="short_answer", marks=1, text="Q?", **extra):
    """Build a coordinator-shape question dict (Extractor output)."""
    base = {
        "section": section,
        "qtype": qtype,
        "marks": marks,
        "text": text,
        "options": [],
        "content": {},
        "chapter_slug": None,
        "cognitive_level": "U",
        "topic_names": [],
        "primary_form": "none",
    }
    base.update(extra)
    return base


class StubExtractor:
    """Extractor adapter returning canned, already-tagged question dicts."""

    def __init__(self, questions: list[dict]):
        self._questions = questions

    def extract(self, pdf_bytes: bytes) -> list[dict]:
        return [dict(q) for q in self._questions]


# ---------------------------------------------------------------------------
# Ingestor — end-to-end with a stub Extractor
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_ingestor_persists_unverified_questions_with_tags():
    """End-to-end: extractor → coordinator → DB.

    Why this matters: this is the only test that proves the coordinator wires the
    extractor output through dedup, provenance, and persist. If a step is skipped
    or the row shape drifts, this fails."""
    questions = [
        _q(section="A", qtype="mcq", chapter_slug="electricity", cognitive_level="Ap"),
        _q(
            section="B",
            text="Define inertia.",
            chapter_slug="electricity",
            cognitive_level="Ap",
        ),
    ]
    result = Ingestor(extractor=StubExtractor(questions)).ingest(b"%PDF")

    assert result.created == 2
    assert Question.objects.count() == 2
    assert all(q.verified is False for q in Question.objects.all())

    electricity = Chapter.objects.get(slug="electricity")
    assert all(q.chapter_id == electricity.pk for q in Question.objects.all())
    assert all(q.cognitive_level == "Ap" for q in Question.objects.all())


@pytest.mark.django_db
def test_ingestor_empty_pdf_creates_nothing():
    result = Ingestor(extractor=StubExtractor([])).ingest(b"")
    assert result.created == 0
    assert Question.objects.count() == 0


@pytest.mark.django_db
def test_ingestor_unknown_chapter_slug_persists_without_chapter():
    """An unknown slug → chapter stays None, ingestion still succeeds."""
    result = Ingestor(
        extractor=StubExtractor([_q(chapter_slug="no-such-chapter")])
    ).ingest(b"x")
    assert result.created == 1
    assert Question.objects.get().chapter_id is None


@pytest.mark.django_db
def test_ingestor_sets_parse_quality_from_structure():
    """Coordinator sets parse_quality structurally (no source-text verification).

    Why this matters: parse_quality is the picker gate. An mcq with no options is
    broken; a non-empty short answer is clean — both decided by structure here."""
    questions = [
        _q(section="A", qtype="mcq", text="Which gas?", options=[]),
        _q(section="C", qtype="short_answer", text="Define refraction."),
    ]
    Ingestor(extractor=StubExtractor(questions)).ingest(b"x")

    mcq = Question.objects.get(qtype="mcq")
    sa = Question.objects.get(qtype="short_answer")
    assert mcq.parse_quality == "broken"  # mcq with zero options
    assert sa.parse_quality == "clean"  # non-empty short answer


@pytest.mark.django_db
def test_ingestor_persists_content_options_and_topics():
    """Structured content, options, topic_names, primary_form reach the row."""
    q = _q(
        section="A",
        qtype="mcq",
        text="Which gas?",
        options=[{"label": "A", "text": "O2"}],
        content={"stem": [{"type": "paragraph", "text": "Which gas?"}]},
        topic_names=["Photosynthesis"],
        primary_form="diagram_based",
    )
    Ingestor(extractor=StubExtractor([q])).ingest(b"x")

    row = Question.objects.get()
    assert row.options == [{"label": "A", "text": "O2"}]
    assert row.content["stem"][0]["text"] == "Which gas?"
    assert row.topic_names == ["Photosynthesis"]
    assert row.primary_form == "diagram_based"
    assert row.has_diagram is True  # diagram_based reinforces it


# ---------------------------------------------------------------------------
# GeminiExtractor — section-chunking + coercion, via a stub LLMClient
# ---------------------------------------------------------------------------


class SequenceLLMClient:
    """LLMClient stub: one question per call, so we can assert call count + order."""

    def __init__(self):
        self.calls: list[str] = []

    def extract(self, pdf_bytes, prompt, response_schema):
        self.calls.append(prompt)
        n = len(self.calls)
        return {
            "questions": [{"qtype": "short_answer", "marks": 2, "rawText": f"Q{n}"}]
        }


def test_gemini_extractor_calls_client_once_per_section_and_merges():
    """One request per Section A–E; results merge in document order.

    Why this matters: section-chunking keeps the model's attention dense; the
    coordinator relies on the section label coming from the loop, not the model."""
    client = SequenceLLMClient()
    out = GeminiExtractor(client=client).extract(b"%PDF")

    assert len(client.calls) == 5
    assert [q["section"] for q in out] == ["A", "B", "C", "D", "E"]
    assert [q["text"] for q in out] == ["Q1", "Q2", "Q3", "Q4", "Q5"]
    assert all(q["marks"] == 2 for q in out)


class OneSectionLLMClient:
    """Returns a payload on the first call (Section A), empty afterwards."""

    def __init__(self, payload: dict):
        self.payload = payload
        self.calls = 0

    def extract(self, pdf_bytes, prompt, response_schema):
        self.calls += 1
        return self.payload if self.calls == 1 else {"questions": []}


def test_gemini_extractor_coerces_question_fields():
    """rawText→text, marks fallback, topic_names cleaned, primary_form clamped.

    Why this matters: the model's output is normalised to the row shape here; a
    garbage primary_form must be clamped, not persisted raw."""
    payload = {
        "questions": [
            {
                "qtype": "mcq",
                # no marks → falls back to Section A default (1)
                "rawText": "Which gas?",
                "options": [{"label": "A", "text": "O2"}],
                "content": {"stem": [{"type": "paragraph", "text": "Which gas?"}]},
                "chapter_slug": "electricity",
                "cognitive_level": "R",
                "topic_names": ["Photosynthesis", "  ", 7],
                "primary_form": "interpretive_dance",
            }
        ]
    }
    out = GeminiExtractor(client=OneSectionLLMClient(payload)).extract(b"%PDF")

    assert len(out) == 1
    q = out[0]
    assert q["section"] == "A"
    assert q["marks"] == 1  # section default fallback
    assert q["text"] == "Which gas?"
    assert q["topic_names"] == ["Photosynthesis"]  # blanks/non-str dropped
    assert q["primary_form"] == "none"  # unknown value clamped
    assert q["chapter_slug"] == "electricity"


# ---------------------------------------------------------------------------
# _compute_parse_quality — structural self-assessment
# ---------------------------------------------------------------------------


def test_compute_parse_quality_clean_assertion_reason():
    content = {
        "assertion": [{"type": "paragraph", "text": "Some assertion."}],
        "reason": [{"type": "paragraph", "text": "Some reason."}],
    }
    raw_q = {"text": "AR", "content": content}
    assert _compute_parse_quality(raw_q, "assertion_reason") == "clean"


def test_compute_parse_quality_broken_when_content_empty():
    """A structured qtype with empty content is broken, not silently partial:
    parse_quality='broken' means the picker excludes the question."""
    raw_q = {"text": "Assertion (A): X", "content": {}}
    assert _compute_parse_quality(raw_q, "assertion_reason") == "broken"


def test_compute_parse_quality_broken_mcq_missing_options():
    raw_q = {"text": "Which gas?", "options": [], "content": {}}
    assert _compute_parse_quality(raw_q, "mcq") == "broken"


def test_compute_parse_quality_clean_mcq_four_options():
    opts = [
        {"label": label, "text": t}
        for label, t in [("A", "O2"), ("B", "CO2"), ("C", "N2"), ("D", "H2")]
    ]
    raw_q = {"text": "Which gas?", "options": opts, "content": {}}
    assert _compute_parse_quality(raw_q, "mcq") == "clean"


def test_compute_parse_quality_clean_short_answer_with_text():
    raw_q = {"text": "Define refraction.", "content": {}}
    assert _compute_parse_quality(raw_q, "short_answer") == "clean"


# ---------------------------------------------------------------------------
# _parse_source_filename
# ---------------------------------------------------------------------------


def test_parse_source_filename_underscore_science():
    """Underscore-separated CBSE code with subject label and year from parent dir."""
    result = _parse_source_filename(Path("content/science_2024/31_1_1_Science.pdf"))
    assert result == {
        "source_type": "previous_year_paper",
        "source_name": "31-1-1 Science 2024",
        "source_file_name": "31_1_1_Science.pdf",
    }


def test_parse_source_filename_dash_only():
    result = _parse_source_filename(Path("content/science_2025/31-2-1.pdf"))
    assert result == {
        "source_type": "previous_year_paper",
        "source_name": "31-2-1 2025",
        "source_file_name": "31-2-1.pdf",
    }


def test_parse_source_filename_prefixed():
    result = _parse_source_filename(
        Path("content/science_2026/1190-1_31-4-1_Science.pdf")
    )
    assert result["source_type"] == "previous_year_paper"
    assert result["source_file_name"] == "1190-1_31-4-1_Science.pdf"
    assert "2026" in result["source_name"]
    assert "Science" in result["source_name"]


def test_parse_source_filename_no_year_in_parent():
    result = _parse_source_filename(Path("uploads/31_1_1_Science.pdf"))
    assert result["source_type"] == "previous_year_paper"
    assert result["source_name"] == "31-1-1 Science"
