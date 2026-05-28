"""Tests for Slice 5: de-duplication, numerical detection, marking scheme, admin actions."""
from __future__ import annotations

import pytest

from bank.ingestor import Ingestor, _detect_numerical, _fingerprint, segment_questions
from bank.marking_scheme import parse_marking_scheme, apply_marking_scheme
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
# DiagramExtractor — keyword sentinel
# ---------------------------------------------------------------------------

_DIAGRAM_KEYWORD_TEXT = """\
SECTION B
1. Refer to the diagram below and label the parts. (Fig. 3)
2. Define photosynthesis.
"""


@pytest.mark.django_db
def test_ingestor_flags_diagram_keyword_question():
    """Questions mentioning 'Fig.' must be flagged has_diagram even without real PDF."""
    extractor = _NullExtractor()  # returns all None — falls back to keyword scan
    # Override: use PdfplumberDiagramExtractor which has keyword fallback built in.
    from bank.ingestor import PdfplumberDiagramExtractor

    qs = segment_questions(_DIAGRAM_KEYWORD_TEXT)
    results = PdfplumberDiagramExtractor().extract(b"not-a-pdf", qs)
    # First question mentions "Fig." → sentinel empty bytes
    assert results[0] == b""
    # Second question is plain text → None
    assert results[1] is None


# ---------------------------------------------------------------------------
# Marking scheme — parse_marking_scheme
# ---------------------------------------------------------------------------

_SCHEME_TEXT = b""  # will be provided as fake PDF — tested via parse_marking_scheme directly

_SCHEME_PLAIN = """
1. Oxygen (O2)
2. The SI unit of current is Ampere.
3. Decomposition is the breakdown of a compound into simpler substances.
"""


def test_parse_marking_scheme_extracts_answers(monkeypatch):
    """parse_marking_scheme called with real PDF bytes; we monkeypatch pdfplumber."""
    import pdfplumber

    class FakePage:
        def extract_text(self):
            return _SCHEME_PLAIN

    class FakePDF:
        pages = [FakePage()]

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    monkeypatch.setattr(pdfplumber, "open", lambda *a, **kw: FakePDF())
    scheme = parse_marking_scheme(b"fake")

    assert scheme[1] == "Oxygen (O2)"
    assert scheme[2] == "The SI unit of current is Ampere."
    assert scheme[3] == "Decomposition is the breakdown of a compound into simpler substances."


def test_parse_marking_scheme_empty_pdf(monkeypatch):
    import pdfplumber

    class FakePDF:
        pages = []

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    monkeypatch.setattr(pdfplumber, "open", lambda *a, **kw: FakePDF())
    assert parse_marking_scheme(b"fake") == {}


# ---------------------------------------------------------------------------
# Marking scheme — apply_marking_scheme
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_apply_marking_scheme_updates_answers(monkeypatch):
    """apply_marking_scheme must fill in answer fields for unverified questions."""
    import pdfplumber

    q1 = Question.objects.create(
        section="B", qtype="VSA", marks=2, text="Q1 text?", verified=False, answer=""
    )
    q2 = Question.objects.create(
        section="B", qtype="VSA", marks=2, text="Q2 text?", verified=False, answer=""
    )

    class FakePage:
        def extract_text(self):
            return "1. Answer one\n2. Answer two\n"

    class FakePDF:
        pages = [FakePage()]

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    monkeypatch.setattr(pdfplumber, "open", lambda *a, **kw: FakePDF())
    updated = apply_marking_scheme(b"fake")

    assert updated == 2
    q1.refresh_from_db()
    q2.refresh_from_db()
    assert q1.answer == "Answer one"
    assert q2.answer == "Answer two"


@pytest.mark.django_db
def test_apply_marking_scheme_skips_verified_questions(monkeypatch):
    """Verified questions must not be overwritten by marking scheme."""
    import pdfplumber

    Question.objects.create(
        section="B", qtype="VSA", marks=2, text="Verified Q?", verified=True, answer="correct"
    )

    class FakePage:
        def extract_text(self):
            return "1. Wrong answer\n"

    class FakePDF:
        pages = [FakePage()]

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    monkeypatch.setattr(pdfplumber, "open", lambda *a, **kw: FakePDF())
    updated = apply_marking_scheme(b"fake")

    assert updated == 0
