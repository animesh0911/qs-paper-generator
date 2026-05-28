"""Tests for bank.ingestor.

Pure helpers (strip_hindi, segment_questions) tested directly.
Ingestor coordinator tested end-to-end with stub Parser/Tagger adapters —
no mock.patch on module globals.
"""
from __future__ import annotations

import pytest

from bank.ingestor import Ingestor, LLMTagger, segment_questions, strip_hindi
from bank.models import Chapter, Question


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
# Ingestor — end-to-end with stub adapters
# ---------------------------------------------------------------------------


class StubParser:
    """Parser adapter that returns canned text."""

    def __init__(self, text: str):
        self._text = text

    def parse(self, pdf_bytes: bytes) -> str:
        return self._text

    def parse_pages(self, pdf_bytes: bytes) -> list[str]:
        return [self._text]


class StubTagger:
    """Tagger adapter that assigns a fixed chapter/level to every question."""

    def __init__(self, chapter_slug: str, level: str = "U"):
        self.chapter_slug = chapter_slug
        self.level = level
        self.calls: list[tuple[int, int]] = []  # (n_questions, n_chapters)

    def tag(self, raw_questions, chapters):
        self.calls.append((len(raw_questions), len(chapters)))
        return [
            {**q, "chapter_slug": self.chapter_slug, "cognitive_level": self.level}
            for q in raw_questions
        ]


@pytest.mark.django_db
def test_ingestor_persists_unverified_questions_with_tags():
    """End-to-end: parser → segmenter → tagger → DB.

    Why this matters: this is the only test that proves the coordinator
    actually wires the pipeline end to end. If the order changes or a step
    is skipped, this test fails.
    """
    parser = StubParser(_SAMPLE_TEXT)
    tagger = StubTagger(chapter_slug="electricity", level="Ap")
    result = Ingestor(parser=parser, tagger=tagger).ingest(b"ignored")

    assert result.created == 5
    assert Question.objects.count() == 5
    assert all(q.verified is False for q in Question.objects.all())

    electricity = Chapter.objects.get(slug="electricity")
    assert all(q.chapter_id == electricity.pk for q in Question.objects.all())
    assert all(q.cognitive_level == "Ap" for q in Question.objects.all())


@pytest.mark.django_db
def test_ingestor_empty_pdf_creates_nothing():
    parser = StubParser("")
    tagger = StubTagger(chapter_slug="electricity")
    result = Ingestor(parser=parser, tagger=tagger).ingest(b"")

    assert result.created == 0
    assert Question.objects.count() == 0
    assert tagger.calls == []  # tagger not invoked when there's nothing to tag


@pytest.mark.django_db
def test_ingestor_unknown_chapter_slug_persists_without_chapter():
    """Tagger returns a slug not in the bank → chapter stays None, ingestion still succeeds."""
    parser = StubParser(_SAMPLE_TEXT)
    tagger = StubTagger(chapter_slug="no-such-chapter")
    result = Ingestor(parser=parser, tagger=tagger).ingest(b"x")

    assert result.created == 5
    assert all(q.chapter_id is None for q in Question.objects.all())


# ---------------------------------------------------------------------------
# LLMTagger — provider-agnostic, driven by an LLMClient
# ---------------------------------------------------------------------------


import json as _json  # noqa: E402  (alias so the per-test prompt builds cleanly)


class StubLLMClient:
    """LLMClient stub that returns canned JSON regardless of prompt."""

    def __init__(self, tags: list[dict], wrap_fences: bool = False):
        self.tags = tags
        self.wrap_fences = wrap_fences
        self.calls: list[str] = []

    def complete(self, prompt: str, max_tokens: int = 2048) -> str:
        self.calls.append(prompt)
        payload = _json.dumps(self.tags)
        if self.wrap_fences:
            return f"```json\n{payload}\n```"
        return payload


@pytest.mark.django_db
def test_llm_tagger_calls_client_and_attaches_tags():
    """LLMTagger calls the injected client, parses JSON, returns tagged dicts.

    Why this matters: this is the only test that verifies LLMTagger correctly
    composes the prompt + parses the response. Swapping the underlying provider
    must not break this contract.
    """
    raw = [
        {"section": "A", "qtype": "MCQ", "marks": 1, "text": "Q one", "options": []},
        {"section": "B", "qtype": "VSA", "marks": 2, "text": "Q two", "options": []},
    ]
    client = StubLLMClient(tags=[
        {"index": 0, "chapter_slug": "electricity", "cognitive_level": "R"},
        {"index": 1, "chapter_slug": "life-processes", "cognitive_level": "Ap"},
    ])
    tagged = LLMTagger(client=client).tag(raw, chapters=[])

    assert tagged[0]["chapter_slug"] == "electricity"
    assert tagged[0]["cognitive_level"] == "R"
    assert tagged[1]["chapter_slug"] == "life-processes"
    assert tagged[1]["cognitive_level"] == "Ap"
    assert len(client.calls) == 1


@pytest.mark.django_db
def test_llm_tagger_strips_markdown_fences():
    """Some providers wrap JSON in ```json fences; tagger must strip them."""
    raw = [{"section": "A", "qtype": "MCQ", "marks": 1, "text": "Q", "options": []}]
    client = StubLLMClient(
        tags=[{"index": 0, "chapter_slug": "electricity", "cognitive_level": "U"}],
        wrap_fences=True,
    )
    tagged = LLMTagger(client=client).tag(raw, chapters=[])
    assert tagged[0]["chapter_slug"] == "electricity"


def test_llm_tagger_empty_input_skips_llm_call():
    client = StubLLMClient(tags=[])
    result = LLMTagger(client=client).tag([], chapters=[])
    assert result == []
    assert client.calls == []
