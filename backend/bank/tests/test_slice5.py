"""Tests for ingestion enrichment: de-duplication, numerical detection, diagram
flagging, source provenance — over the Gemini native-PDF Extractor seam."""

from __future__ import annotations

import pytest

from bank.ingestor import Ingestor, _detect_numerical, _fingerprint
from bank.models import Question

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


def _q(section="B", qtype="short_answer", marks=2, text="Q?", **extra):
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

_DEDUP_QUESTIONS = [
    _q(text="Define decomposition reaction and give one example."),
    _q(text="What is the function of the stomata in a leaf?"),
]


@pytest.mark.django_db
def test_ingestor_dedup_skips_existing_questions():
    """Second ingest of identical questions must not create duplicate rows."""
    extractor = StubExtractor(_DEDUP_QUESTIONS)

    r1 = Ingestor(extractor=extractor).ingest(b"x")
    assert r1.created == 2
    assert r1.skipped_duplicates == 0

    r2 = Ingestor(extractor=extractor).ingest(b"x")
    assert r2.created == 0
    assert r2.skipped_duplicates == 2
    assert Question.objects.count() == 2


@pytest.mark.django_db
def test_ingestor_dedup_within_single_pdf():
    """Repeated questions within one PDF collapse to a single row."""
    questions = [
        _q(text="Define decomposition reaction."),
        _q(text="Define decomposition reaction."),
        _q(text="What is the function of the stomata in a leaf?"),
    ]
    r = Ingestor(extractor=StubExtractor(questions)).ingest(b"x")
    assert r.created == 2
    assert r.skipped_duplicates == 1
    assert Question.objects.count() == 2


@pytest.mark.django_db
def test_ingestor_dedup_only_skips_exact_matches():
    """A slightly different question must NOT be skipped."""
    Ingestor(
        extractor=StubExtractor([_q(text="Define decomposition reaction.")])
    ).ingest(b"x")
    r = Ingestor(
        extractor=StubExtractor([_q(text="Define synthesis reaction.")])
    ).ingest(b"x")
    assert r.created == 1
    assert Question.objects.count() == 2


# ---------------------------------------------------------------------------
# is_numerical flag on ingested questions
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_ingestor_flags_numerical_question():
    Ingestor(
        extractor=StubExtractor(
            [_q(section="C", text="A car accelerates from 0 to 20 m/s in 4 s.")]
        )
    ).ingest(b"x")
    assert Question.objects.get().is_numerical is True


@pytest.mark.django_db
def test_ingestor_does_not_flag_conceptual_question():
    Ingestor(
        extractor=StubExtractor(
            [_q(section="C", text="Describe the role of the liver in digestion.")]
        )
    ).ingest(b"x")
    assert Question.objects.get().is_numerical is False


# ---------------------------------------------------------------------------
# Diagram keyword flagging — coordinator flags has_diagram from question text
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_ingestor_flags_diagram_keyword_question_via_text():
    """A question mentioning 'Fig.' gets has_diagram=True from text alone."""
    questions = [
        _q(text="Refer to the diagram below and label the parts. (Fig. 3)"),
        _q(text="Define photosynthesis."),
    ]
    Ingestor(extractor=StubExtractor(questions)).ingest(b"x")
    qs = Question.objects.order_by("id")
    assert qs[0].has_diagram is True  # mentions "Fig. 3"
    assert qs[1].has_diagram is False  # plain text


@pytest.mark.django_db
def test_ingestor_flags_diagram_from_primary_form():
    """diagram_based primary_form reinforces has_diagram even without a keyword."""
    Ingestor(
        extractor=StubExtractor(
            [_q(text="Identify the labelled structure.", primary_form="diagram_based")]
        )
    ).ingest(b"x")
    assert Question.objects.get().has_diagram is True


# ---------------------------------------------------------------------------
# Source provenance + enrichment persistence
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_ingest_records_source_provenance_from_filename():
    """Filename + source_type land on the row; source_name is the filename stem.

    Why this matters: CONTEXT promises ingest records provenance, and
    PaperDocumentV1.source maps it. source_page_number is a V2 deferral (the
    Extractor does not track page offsets), so it stays null."""
    Ingestor(extractor=StubExtractor([_q()])).ingest(
        b"x", source_file_name="31-2-1.pdf", source_type="sample_paper"
    )

    q = Question.objects.get()
    assert q.source_file_name == "31-2-1.pdf"
    assert q.source_name == "31-2-1"  # filename stem
    assert q.source_type == "sample_paper"
    assert q.source_page_number is None
    assert q.source_original_qnum == ""


@pytest.mark.django_db
def test_ingest_defaults_source_type_when_omitted():
    """No source_type → previous_year_paper (the common case for a PYQ PDF)."""
    Ingestor(extractor=StubExtractor([_q()])).ingest(
        b"x", source_file_name="boards-2025.pdf"
    )
    assert Question.objects.get().source_type == "previous_year_paper"


@pytest.mark.django_db
def test_ingest_persists_topic_names_and_primary_form():
    """Extractor enrichment reaches the DB; diagram_based reinforces has_diagram."""
    Ingestor(
        extractor=StubExtractor(
            [_q(topic_names=["Decomposition"], primary_form="diagram_based")]
        )
    ).ingest(b"x")
    q = Question.objects.get()
    assert q.topic_names == ["Decomposition"]
    assert q.primary_form == "diagram_based"
    assert q.has_diagram is True
