"""Tests for Slice 5: de-duplication, numerical detection, marking scheme, admin actions."""
from __future__ import annotations

import pytest

from bank.ingestor import (
    Ingestor,
    MarkingSchemeAnswerSource,
    _detect_numerical,
    _fingerprint,
    segment_questions,
)
from bank.models import Question


# ---------------------------------------------------------------------------
# _detect_numerical
# ---------------------------------------------------------------------------


def test_detect_numerical_si_unit():
    assert _detect_numerical("A wire of length 2.5 m carries current of 3 A.")


def test_detect_numerical_equation():
    assert _detect_numerical("Calculate v if u=0, a=9.8 m/s and t=2s.")


def test_detect_numerical_scientific_notation():
    assert _detect_numerical("The speed of light is 3×10^8 m/s.")


def test_detect_numerical_conceptual_question():
    assert not _detect_numerical("Explain the process of photosynthesis.")


def test_detect_numerical_definition():
    assert not _detect_numerical("Define decomposition reaction and give one example.")


# ---------------------------------------------------------------------------
# _fingerprint
# ---------------------------------------------------------------------------


def test_fingerprint_deterministic():
    assert _fingerprint("Hello world") == _fingerprint("Hello world")


def test_fingerprint_normalises_case_and_spaces():
    assert _fingerprint("Hello  World") == _fingerprint("hello world")


def test_fingerprint_different_texts_differ():
    assert _fingerprint("question one") != _fingerprint("question two")


# ---------------------------------------------------------------------------
# De-duplication — via Ingestor
# ---------------------------------------------------------------------------

_DEDUP_TEXT = """\
SECTION B
1. Define decomposition reaction and give one example.
2. What is the function of the stomata in a leaf?
"""


class _StubParser:
    def __init__(self, text):
        self._text = text

    def parse(self, b):
        return self._text

    def parse_pages(self, b):
        return [self._text]


class _StubTagger:
    def tag(self, qs, chapters):
        return [{**q, "chapter_slug": None, "cognitive_level": "U"} for q in qs]


class _NullExtractor:
    def extract(self, pdf_bytes, raw_questions):
        return [None] * len(raw_questions)


@pytest.mark.django_db
def test_ingestor_dedup_skips_existing_questions():
    """Second ingest of identical text must not create duplicate rows."""
    parser = _StubParser(_DEDUP_TEXT)
    tagger = _StubTagger()
    extractor = _NullExtractor()

    r1 = Ingestor(parser=parser, tagger=tagger, extractor=extractor).ingest(b"x")
    assert r1.created == 2
    assert r1.skipped_duplicates == 0

    r2 = Ingestor(parser=parser, tagger=tagger, extractor=extractor).ingest(b"x")
    assert r2.created == 0
    assert r2.skipped_duplicates == 2
    assert Question.objects.count() == 2


@pytest.mark.django_db
def test_ingestor_dedup_within_single_pdf():
    """Repeated questions within one PDF must collapse to a single row."""
    text = """\
SECTION B
1. Define decomposition reaction.
2. Define decomposition reaction.
3. What is the function of the stomata in a leaf?
"""
    parser = _StubParser(text)
    r = Ingestor(parser=parser, tagger=_StubTagger(), extractor=_NullExtractor()).ingest(b"x")
    assert r.created == 2
    assert r.skipped_duplicates == 1
    assert Question.objects.count() == 2


@pytest.mark.django_db
def test_ingestor_dedup_only_skips_exact_matches():
    """A slightly different question must NOT be skipped."""
    text1 = """\
SECTION B
1. Define decomposition reaction and give one example.
"""
    text2 = """\
SECTION B
1. Define synthesis reaction and give one example.
"""
    extractor = _NullExtractor()
    tagger = _StubTagger()

    Ingestor(parser=_StubParser(text1), tagger=tagger, extractor=extractor).ingest(b"x")
    r = Ingestor(parser=_StubParser(text2), tagger=tagger, extractor=extractor).ingest(b"x")
    assert r.created == 1
    assert Question.objects.count() == 2


# ---------------------------------------------------------------------------
# is_numerical flag on ingested questions
# ---------------------------------------------------------------------------

_NUMERICAL_TEXT = """\
SECTION C
1. A car accelerates from 0 to 20 m/s in 4 s. Calculate the acceleration.
"""

_NON_NUMERICAL_TEXT = """\
SECTION C
1. Describe the role of the liver in the digestive system.
"""


@pytest.mark.django_db
def test_ingestor_flags_numerical_question(db):
    extractor = _NullExtractor()
    tagger = _StubTagger()
    Ingestor(parser=_StubParser(_NUMERICAL_TEXT), tagger=tagger, extractor=extractor).ingest(b"x")
    q = Question.objects.get()
    assert q.is_numerical is True


@pytest.mark.django_db
def test_ingestor_does_not_flag_conceptual_question(db):
    extractor = _NullExtractor()
    tagger = _StubTagger()
    Ingestor(
        parser=_StubParser(_NON_NUMERICAL_TEXT), tagger=tagger, extractor=extractor
    ).ingest(b"x")
    q = Question.objects.get()
    assert q.is_numerical is False


# ---------------------------------------------------------------------------
# Diagram keyword detection — moved from extractor to coordinator
# ---------------------------------------------------------------------------

_DIAGRAM_KEYWORD_TEXT = """\
SECTION B
1. Refer to the diagram below and label the parts. (Fig. 3)
2. Define photosynthesis.
"""


@pytest.mark.django_db
def test_ingestor_flags_diagram_keyword_question_via_text_only():
    """Questions mentioning 'Fig.' get has_diagram=True even when no image is extracted."""
    parser = _StubParser(_DIAGRAM_KEYWORD_TEXT)
    Ingestor(
        parser=parser, tagger=_StubTagger(), extractor=_NullExtractor()
    ).ingest(b"not-a-pdf")
    qs = Question.objects.order_by("id")
    assert qs[0].has_diagram is True   # mentions "Fig. 3"
    assert qs[1].has_diagram is False  # plain text


# ---------------------------------------------------------------------------
# AnswerSource — MarkingSchemeAnswerSource
# ---------------------------------------------------------------------------


def _fake_pdf(monkeypatch, text: str | None = None) -> None:
    """Monkeypatch pdfplumber.open so MarkingSchemeAnswerSource sees `text`."""
    import pdfplumber

    class FakePage:
        def extract_text(self):
            return text

    class FakePDF:
        pages = [FakePage()] if text is not None else []

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    monkeypatch.setattr(pdfplumber, "open", lambda *a, **kw: FakePDF())


def test_marking_scheme_answer_source_extracts_answers(monkeypatch):
    _fake_pdf(
        monkeypatch,
        text=(
            "1. Oxygen (O2)\n"
            "2. The SI unit of current is Ampere.\n"
            "3. Decomposition is the breakdown of a compound into simpler substances.\n"
        ),
    )
    scheme = MarkingSchemeAnswerSource().answers(b"fake")
    assert scheme[1] == "Oxygen (O2)"
    assert scheme[2] == "The SI unit of current is Ampere."
    assert scheme[3] == "Decomposition is the breakdown of a compound into simpler substances."


def test_marking_scheme_answer_source_empty_pdf(monkeypatch):
    _fake_pdf(monkeypatch, text=None)
    assert MarkingSchemeAnswerSource().answers(b"fake") == {}


# ---------------------------------------------------------------------------
# Ingestor.apply_answers — coordinator method
# ---------------------------------------------------------------------------


class _StubAnswerSource:
    def __init__(self, scheme: dict[int, str]):
        self.scheme = scheme

    def answers(self, pdf_bytes: bytes) -> dict[int, str]:
        return self.scheme


@pytest.mark.django_db
def test_apply_answers_fills_unverified_rows_by_position():
    """n-th answer in the scheme maps to the n-th unverified Question by id."""
    q1 = Question.objects.create(
        section="B", qtype="very_short_answer", marks=2, text="Q1?", verified=False, answer=""
    )
    q2 = Question.objects.create(
        section="B", qtype="very_short_answer", marks=2, text="Q2?", verified=False, answer=""
    )

    ingestor = Ingestor(
        parser=_StubParser(""),
        tagger=_StubTagger(),
        extractor=_NullExtractor(),
        answer_source=_StubAnswerSource({1: "Answer one", 2: "Answer two"}),
    )
    assert ingestor.apply_answers(b"x") == 2

    q1.refresh_from_db()
    q2.refresh_from_db()
    assert q1.answer == "Answer one"
    assert q2.answer == "Answer two"


@pytest.mark.django_db
def test_apply_answers_skips_verified_questions():
    """Verified questions are excluded from the candidate list, so they are never overwritten."""
    Question.objects.create(
        section="B", qtype="very_short_answer", marks=2, text="Verified?", verified=True, answer="correct"
    )
    ingestor = Ingestor(
        parser=_StubParser(""),
        tagger=_StubTagger(),
        extractor=_NullExtractor(),
        answer_source=_StubAnswerSource({1: "Wrong answer"}),
    )
    assert ingestor.apply_answers(b"x") == 0
