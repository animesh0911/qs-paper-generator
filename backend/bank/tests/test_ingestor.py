"""Tests for bank.ingestor.

Pure helpers (strip_hindi, segment_questions) tested directly.
Ingestor coordinator tested end-to-end with stub Parser/Tagger adapters —
no mock.patch on module globals.
"""

from __future__ import annotations

import pytest

from bank.ingestor import (
    Ingestor,
    LLMSegmenter,
    LLMTagger,
    RegexSegmenter,
    _classify_qtype,
    _compute_parse_quality,
    _parse_assertion_reason,
    _parse_case_based,
    _parse_internal_choice,
    _parse_long_answer_subparts,
    _verify,
    segment_questions,
    strip_hindi,
)
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
    result = Ingestor(parser=parser, segmenter=RegexSegmenter(), tagger=tagger).ingest(
        b"ignored"
    )

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
    result = Ingestor(parser=parser, segmenter=RegexSegmenter(), tagger=tagger).ingest(
        b""
    )

    assert result.created == 0
    assert Question.objects.count() == 0
    assert tagger.calls == []  # tagger not invoked when there's nothing to tag


@pytest.mark.django_db
def test_ingestor_unknown_chapter_slug_persists_without_chapter():
    """Tagger returns an unknown slug → chapter stays None, ingestion succeeds."""
    parser = StubParser(_SAMPLE_TEXT)
    tagger = StubTagger(chapter_slug="no-such-chapter")
    result = Ingestor(parser=parser, segmenter=RegexSegmenter(), tagger=tagger).ingest(
        b"x"
    )

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
        {"section": "A", "qtype": "mcq", "marks": 1, "text": "Q one", "options": []},
        {
            "section": "B",
            "qtype": "very_short_answer",
            "marks": 2,
            "text": "Q two",
            "options": [],
        },
    ]
    client = StubLLMClient(
        tags=[
            {"index": 0, "chapter_slug": "electricity", "cognitive_level": "R"},
            {"index": 1, "chapter_slug": "life-processes", "cognitive_level": "Ap"},
        ]
    )
    tagged = LLMTagger(client=client).tag(raw, chapters=[])

    assert tagged[0]["chapter_slug"] == "electricity"
    assert tagged[0]["cognitive_level"] == "R"
    assert tagged[1]["chapter_slug"] == "life-processes"
    assert tagged[1]["cognitive_level"] == "Ap"
    assert len(client.calls) == 1


@pytest.mark.django_db
def test_llm_tagger_strips_markdown_fences():
    """Some providers wrap JSON in ```json fences; tagger must strip them."""
    raw = [{"section": "A", "qtype": "mcq", "marks": 1, "text": "Q", "options": []}]
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


# ---------------------------------------------------------------------------
# Shape-detection helpers — pure unit tests
# ---------------------------------------------------------------------------

_AR_TEXT = """\
Assertion (A): Blood plasma transports carbon dioxide in dissolved form.
Reason (R): Carbon dioxide is more soluble in water than oxygen.
(A) Both A and R are true and R is the correct explanation of A.
(B) Both A and R are true but R is not the correct explanation of A.
(C) A is true but R is false.
(D) A is false but R is true."""

_CASE_TEXT = """\
A student observed that burning a candle produces heat, light, and gases. \
The wax melts near the flame and some of it vaporises and burns.
(a) Is burning of candle a physical or chemical change?
(b) Name two products of combustion of wax.
(c) Is this change reversible? Give one reason."""

_OR_TEXT = """\
Explain the process of digestion in human beings.
OR
Explain the mechanism of breathing in humans."""

_SUBPART_TEXT = """\
(i) Name the organ that regulates blood sugar.
(ii) Write the pathway of urine formation.
(iii) Mention one function of the liver."""


def test_parse_assertion_reason_detects_assertion_and_reason():
    """assertion_reason matters: CBSE Section A has AR questions that must be
    classified by structure, not by section position."""
    result = _parse_assertion_reason(_AR_TEXT)
    assert result is not None
    assert result["assertion"][0]["text"].startswith("Blood plasma")
    assert result["reason"][0]["text"].startswith("Carbon dioxide is more soluble")


def test_parse_assertion_reason_includes_options():
    result = _parse_assertion_reason(_AR_TEXT)
    assert result is not None
    labels = [o["label"] for o in result["options"]]
    assert labels == ["A", "B", "C", "D"]


def test_parse_assertion_reason_returns_none_for_plain_text():
    result = _parse_assertion_reason("What is photosynthesis?")
    assert result is None


def test_parse_case_based_detects_passage_and_subparts():
    """case_based matters: Section E questions must expose passage + subparts
    so the frontend can render them correctly and the picker can select them."""
    result = _parse_case_based(_CASE_TEXT)
    assert result is not None
    assert "candle" in result["passage"][0]["text"]
    assert len(result["subparts"]) == 3


def test_parse_case_based_subpart_labels():
    result = _parse_case_based(_CASE_TEXT)
    assert result is not None
    labels = [s["label"] for s in result["subparts"]]
    assert labels == ["a", "b", "c"]


def test_parse_case_based_returns_none_for_single_subpart():
    text = "Some passage text here.\n(a) Only one subpart."
    result = _parse_case_based(text)
    assert result is None


def test_parse_case_based_returns_none_for_plain_text():
    result = _parse_case_based("State two functions of stomata.")
    assert result is None


def test_parse_internal_choice_detects_or_split():
    """internal_choice matters: OR questions in Section D must expose both
    options so students can see the alternative and teachers can swap them."""
    result = _parse_internal_choice(_OR_TEXT)
    assert result is not None
    choices = result["choices"]
    assert len(choices) == 1
    assert choices[0]["displayStyle"] == "or"
    assert len(choices[0]["options"]) == 2


def test_parse_internal_choice_option_text():
    result = _parse_internal_choice(_OR_TEXT)
    assert result is not None
    texts = [o["content"][0]["text"] for o in result["choices"][0]["options"]]
    assert any("digestion" in t for t in texts)
    assert any("breathing" in t for t in texts)


def test_parse_internal_choice_returns_none_without_or():
    result = _parse_internal_choice("Explain the process of digestion.")
    assert result is None


def test_parse_long_answer_subparts_splits_roman_numerals():
    result = _parse_long_answer_subparts(_SUBPART_TEXT)
    assert result is not None
    assert len(result) == 3
    labels = [s["label"] for s in result]
    assert labels == ["i", "ii", "iii"]


def test_parse_long_answer_subparts_returns_none_for_plain():
    result = _parse_long_answer_subparts("Explain the process of photosynthesis.")
    assert result is None


def test_classify_qtype_assertion_reason():
    raw_q = {"text": _AR_TEXT, "options": []}
    assert _classify_qtype(raw_q, "A") == "assertion_reason"


def test_classify_qtype_case_based():
    raw_q = {"text": _CASE_TEXT, "options": []}
    assert _classify_qtype(raw_q, "E") == "case_based"


def test_classify_qtype_internal_choice():
    raw_q = {"text": _OR_TEXT, "options": []}
    assert _classify_qtype(raw_q, "D") == "internal_choice"


def test_classify_qtype_falls_back_to_section_default():
    raw_q = {"text": "Explain the process of photosynthesis.", "options": []}
    assert _classify_qtype(raw_q, "C") == "short_answer"
    assert _classify_qtype(raw_q, "D") == "long_answer"


def test_compute_parse_quality_clean_assertion_reason():
    content = {
        "assertion": [{"type": "paragraph", "text": "Some assertion."}],
        "reason": [{"type": "paragraph", "text": "Some reason."}],
        "options": [],
    }
    raw_q = {"text": _AR_TEXT, "content": content}
    assert _compute_parse_quality(raw_q, "assertion_reason") == "clean"


def test_compute_parse_quality_broken_when_content_empty():
    """parse_quality='broken' means the picker will exclude this question.
    A structured qtype with empty content must be broken, not silently partial."""
    raw_q = {"text": "Assertion (A): X\n(garbled text)", "content": {}}
    assert _compute_parse_quality(raw_q, "assertion_reason") == "broken"


def test_compute_parse_quality_broken_mcq_missing_options():
    raw_q = {"text": "Which gas is released?", "options": [], "content": {}}
    assert _compute_parse_quality(raw_q, "mcq") == "broken"


def test_compute_parse_quality_clean_mcq_four_options():
    opts = [
        {"label": label, "text": t}
        for label, t in [("A", "O2"), ("B", "CO2"), ("C", "N2"), ("D", "H2")]
    ]
    content = {"stem": [{"type": "paragraph", "text": "Which gas?"}], "options": []}
    raw_q = {"text": "Which gas?", "options": opts, "content": content}
    assert _compute_parse_quality(raw_q, "mcq") == "clean"


def test_segment_questions_emits_content_and_parse_quality():
    qs = segment_questions(_SAMPLE_TEXT)
    for q in qs:
        assert "content" in q
        assert "parse_quality" in q
        assert q["parse_quality"] in ("clean", "partial", "broken")


def test_segment_assertion_reason_classified_from_structure():
    """Structural detection overrides section default.
    An AR question in Section A must be assertion_reason, not mcq."""
    text = f"SECTION A\n1. {_AR_TEXT}\n"
    qs = segment_questions(text)
    assert len(qs) == 1
    assert qs[0]["qtype"] == "assertion_reason"
    assert "assertion" in qs[0]["content"]
    assert "reason" in qs[0]["content"]
    assert qs[0]["parse_quality"] == "clean"


def test_segment_internal_choice_classified_from_structure():
    text = f"SECTION D\n18. {_OR_TEXT}\n"
    qs = segment_questions(text)
    assert len(qs) == 1
    assert qs[0]["qtype"] == "internal_choice"
    assert "choices" in qs[0]["content"]
    assert qs[0]["parse_quality"] == "clean"


def test_segment_malformed_input_falls_back_to_broken():
    """Parser failure must not crash; broken parse_quality, content={}, text populated.
    This matters because the picker gates on parse_quality — broken must propagate."""
    text = "SECTION A\n1. (garbled text without proper assertion format\n"
    qs = segment_questions(text)
    assert len(qs) == 1
    assert qs[0]["text"]
    # MCQ with no options → broken
    assert qs[0]["parse_quality"] == "broken"


# ---------------------------------------------------------------------------
# LLMSegmenter — provider-agnostic, driven by an LLMClient
# ---------------------------------------------------------------------------


def test_llm_segmenter_parses_canned_json():
    """LLMSegmenter calls the client and coerces the JSON array into question dicts.

    Why this matters: this is the seam that replaces regex segmentation. If the
    prompt/parse contract drifts, every ingested paper is affected."""
    questions = [
        {
            "section": "A",
            "qtype": "mcq",
            "marks": 1,
            "text": "Which gas?",
            "options": [{"label": "A", "text": "O2"}],
            "content": {},
        }
    ]
    client = StubLLMClient(tags=questions)
    out = LLMSegmenter(client=client).segment("some paper text")

    assert len(out) == 1
    assert out[0]["section"] == "A"
    assert out[0]["qtype"] == "mcq"
    assert out[0]["marks"] == 1
    assert len(client.calls) == 1


def test_llm_segmenter_empty_text_skips_llm_call():
    client = StubLLMClient(tags=[])
    assert LLMSegmenter(client=client).segment("") == []
    assert client.calls == []


def test_llm_segmenter_malformed_response_falls_back_to_regex():
    """A bad LLM round-trip must degrade to deterministic rules, not drop the paper."""

    class BadLLMClient:
        def __init__(self):
            self.calls: list[str] = []

        def complete(self, prompt: str, max_tokens: int = 4096) -> str:
            self.calls.append(prompt)
            return "this is not json {{{"

    client = BadLLMClient()
    out = LLMSegmenter(client=client, fallback=RegexSegmenter()).segment(_SAMPLE_TEXT)

    assert len(client.calls) == 1
    assert len(out) == 5  # RegexSegmenter recovered all five questions


# ---------------------------------------------------------------------------
# _verify — deterministic guardrails (ADR-0003)
# ---------------------------------------------------------------------------


def test_verify_fidelity_fabricated_text_is_broken():
    """A question whose text isn't in the source is a hallucination → broken."""
    source = "1. Which gas is released during photosynthesis?\n"
    q = {
        "section": "A",
        "qtype": "short_answer",
        "marks": 1,
        "text": "Explain quantum chromodynamics in full detail.",
        "options": [],
        "content": {},
    }
    out = _verify([q], source)
    assert out[0]["parse_quality"] == "broken"


def test_verify_faithful_text_keeps_structural_quality():
    source = "1. Which gas is released during photosynthesis?\n"
    q = {
        "section": "A",
        "qtype": "short_answer",
        "marks": 1,
        "text": "Which gas is released during photosynthesis?",
        "options": [],
        "content": {},
    }
    out = _verify([q], source)
    assert out[0]["parse_quality"] == "clean"


def test_verify_coverage_mismatch_degrades_clean_to_partial():
    """Fewer questions than source anchors → can't trust completeness → partial."""
    source = "1. Which gas is released during photosynthesis?\n2. Define inertia.\n"
    q = {
        "section": "A",
        "qtype": "short_answer",
        "marks": 1,
        "text": "Which gas is released during photosynthesis?",
        "options": [],
        "content": {},
    }
    out = _verify([q], source)  # 1 emitted vs 2 anchors
    assert out[0]["parse_quality"] == "partial"


def test_verify_out_of_order_question_is_broken():
    """Questions emitted out of source reading order signal a merge/reorder error."""
    source = (
        "1. First question about photosynthesis here.\n"
        "2. Second question about inertia here.\n"
    )
    first = {
        "section": "A",
        "qtype": "short_answer",
        "marks": 1,
        "text": "First question about photosynthesis here.",
        "options": [],
        "content": {},
    }
    second = {
        "section": "A",
        "qtype": "short_answer",
        "marks": 1,
        "text": "Second question about inertia here.",
        "options": [],
        "content": {},
    }
    out = _verify([second, first], source)  # emitted in reversed order
    assert out[0]["parse_quality"] != "broken"  # first emitted establishes position
    assert out[1]["parse_quality"] == "broken"  # then a backward jump → broken


def test_verify_swapped_mcq_options_is_broken():
    """Option texts emitted out of source order = swapped labels → broken."""
    source = (
        "Which gas is released during photosynthesis?\n(A) CO2 (B) O2 (C) N2 (D) H2\n"
    )
    q = {
        "section": "A",
        "qtype": "mcq",
        "marks": 1,
        "text": "Which gas is released during photosynthesis?",
        # O2 emitted before CO2 — reversed vs source order
        "options": [
            {"label": "A", "text": "O2"},
            {"label": "B", "text": "CO2"},
            {"label": "C", "text": "N2"},
            {"label": "D", "text": "H2"},
        ],
        "content": {},
    }
    out = _verify([q], source)  # no numbered anchors → coverage not in play
    assert out[0]["parse_quality"] == "broken"


class StubSegmenter:
    """Segmenter adapter that returns canned question dicts."""

    def __init__(self, questions: list[dict]):
        self._questions = questions

    def segment(self, text: str) -> list[dict]:
        return [dict(q) for q in self._questions]


@pytest.mark.django_db
def test_ingestor_verification_marks_hallucinated_row_broken():
    """End-to-end: a fabricated question from the segmenter lands as broken in the DB.

    Why this matters: this proves the guardrail is wired into the coordinator, so
    hallucinations cap yield (excluded by the picker) instead of corrupting the bank."""
    source = "SECTION A\n1. Which gas is released during photosynthesis?\n"
    faithful = {
        "section": "A",
        "qtype": "short_answer",
        "marks": 1,
        "text": "Which gas is released during photosynthesis?",
        "options": [],
        "content": {},
    }
    fabricated = {
        "section": "A",
        "qtype": "short_answer",
        "marks": 1,
        "text": "Explain quantum chromodynamics in full detail.",
        "options": [],
        "content": {},
    }
    result = Ingestor(
        parser=StubParser(source),
        segmenter=StubSegmenter([faithful, fabricated]),
        tagger=StubTagger(chapter_slug="electricity"),
    ).ingest(b"x")

    assert result.created == 2
    hallucination = Question.objects.get(text__icontains="quantum chromodynamics")
    assert hallucination.parse_quality == "broken"
    real = Question.objects.get(text__icontains="photosynthesis")
    assert real.parse_quality != "broken"
