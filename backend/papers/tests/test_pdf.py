"""Unit tests for render_paper_pdf.

The renderer consumes a PaperDocumentV1 dict directly — these tests build
a minimal document fixture and verify the bytes back without touching the DB.
"""

import fitz
import pytest

from papers.pdf import (
    PdfRenderConfigurationError,
    PdfRenderError,
    _render_reportlab_answer_key_pdf,
    _render_reportlab_pdf,
    render_answer_key_pdf,
    render_paper_pdf,
)


def _pdf_text(pdf_bytes: bytes) -> str:
    """Extract all text from rendered PDF bytes via PyMuPDF (a production dep)."""
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        return "\n".join(page.get_text() for page in doc)


def _doc(slot_question_id: str | None = "q_1") -> dict:
    return {
        "schemaVersion": "paper_document.v1",
        "paper": {
            "title": "Test Paper",
            "totalMarks": 5,
            "sections": [
                {
                    "sectionId": "A",
                    "title": "Section A",
                    "slots": [
                        {
                            "slotId": "slot_A_01",
                            "displayNumber": "1",
                            "marks": 1,
                            "questionType": "mcq",
                            "selectedQuestionId": slot_question_id,
                            "locked": False,
                        }
                    ],
                }
            ],
        },
        "questions": [
            {
                "questionId": "q_1",
                "rawText": "What is water?",
                "marks": 1,
                "questionType": "mcq",
                "content": {
                    "stem": [{"type": "paragraph", "text": "What is water?"}],
                    "options": [
                        {
                            "label": "A",
                            "content": [{"type": "paragraph", "text": "H2O"}],
                        },
                        {
                            "label": "B",
                            "content": [{"type": "paragraph", "text": "CO2"}],
                        },
                    ],
                },
            }
        ],
    }


def test_render_requires_print_url():
    with pytest.raises(PdfRenderConfigurationError):
        render_paper_pdf(_doc())


def test_render_uses_browser_route_when_print_url_is_supplied(monkeypatch):
    calls = []

    def fake_browser_pdf(print_url):
        calls.append(print_url)
        return b"%PDF browser paper"

    monkeypatch.setattr("papers.pdf._render_browser_pdf", fake_browser_pdf)

    pdf = render_paper_pdf(_doc(), print_url="http://frontend/paper")

    assert pdf == b"%PDF browser paper"
    assert calls == ["http://frontend/paper"]


def test_render_fails_hard_when_browser_fails(monkeypatch):
    def fail_browser_pdf(print_url):
        raise PdfRenderError("chromium unavailable")

    monkeypatch.setattr("papers.pdf._render_browser_pdf", fail_browser_pdf)

    with pytest.raises(PdfRenderError):
        render_paper_pdf(_doc(), print_url="http://bad")


def test_legacy_reportlab_renderer_handles_unfilled_slot():
    """Legacy unit seam still renders unfilled slots, but downloads do not use it."""
    pdf = _render_reportlab_pdf(_doc(slot_question_id=None))
    assert pdf[:4] == b"%PDF"


def test_render_uses_slot_override_instead_of_stale_question_text():
    """PDF must reflect final Slot edits because PaperDocumentV1 is canonical."""
    document = _doc()
    document["paper"]["sections"][0]["slots"][0]["overrides"] = {
        "modifiedFromSource": True,
        "regions": {
            "stem": [{"type": "paragraph", "text": "Teacher edited water question."}]
        },
    }

    text = _pdf_text(_render_reportlab_pdf(document))

    assert "Teacher edited water question." in text
    assert "What is water?" not in text


def test_branding_renders_school_identity_in_paper_pdf():
    """Branding must reach the PDF — a per-school name/header is the deliverable.

    Asserts the school's own identity, not CBSE's, so a regression that dropped
    the branding header (or reverted to a hardcoded masthead) fails here.
    """
    document = _doc()
    document["paper"]["branding"] = {
        "schoolName": "Greenwood High School",
        "examHeader": "Half-Yearly Examination 2026",
        "logoUrl": "https://cdn.example.com/logo.png",
    }

    text = _pdf_text(_render_reportlab_pdf(document))

    assert "Greenwood High School" in text
    assert "Half-Yearly Examination 2026" in text


def test_paper_pdf_renders_without_branding():
    """No branding key must render cleanly — branding is optional, not assumed."""
    document = _doc()
    assert "branding" not in document["paper"]
    assert _render_reportlab_pdf(document)[:4] == b"%PDF"


def test_answer_key_pdf_uses_browser_route_when_print_url_is_supplied(monkeypatch):
    """Frontend print route is the primary answer-key PDF renderer when configured."""
    calls = []

    def fake_browser_pdf(print_url):
        calls.append(print_url)
        return b"%PDF browser answer key"

    monkeypatch.setattr("papers.pdf._render_browser_pdf", fake_browser_pdf)

    pdf = render_answer_key_pdf(
        _doc(), {"slot_A_01": "H2O"}, print_url="http://frontend/answer-key"
    )

    assert pdf == b"%PDF browser answer key"
    assert calls == ["http://frontend/answer-key"]


def test_answer_key_pdf_fails_hard_when_browser_fails(monkeypatch):
    """A browser failure must not produce a degraded fallback answer key."""

    def fail_browser_pdf(print_url):
        raise PdfRenderError("chromium unavailable")

    monkeypatch.setattr("papers.pdf._render_browser_pdf", fail_browser_pdf)

    with pytest.raises(PdfRenderError):
        render_answer_key_pdf(
            _doc(), {"slot_A_01": "H2O fallback answer"}, print_url="http://bad"
        )


def test_answer_key_pdf_contains_answers_in_slot_order():
    """The marking scheme is worthless if the supplied answer text is absent.

    Answers come from the caller's map (the document never carries them), keyed
    by the slot id the renderer walks — so this also pins the join (issue #122).
    """
    text = _pdf_text(
        _render_reportlab_answer_key_pdf(
            _doc(), {"slot_A_01": "H2O — water is a compound"}
        )
    )

    assert "Answer Key" in text
    assert "H2O — water is a compound" in text


def test_answer_key_pdf_flags_filled_slot_with_no_answer():
    """A selected question with no printable answer must surface the gap, not blank.

    Silent blanks in a marking scheme read as 'no marks' — a loud placeholder
    forces the teacher to notice the missing answer (Rule 12, fail loud).
    """
    text = _pdf_text(_render_reportlab_answer_key_pdf(_doc(), {}))

    assert "Answer not available" in text


def test_answer_key_pdf_marks_unfilled_slot():
    """Unfilled slot (no selected question) renders as unfilled, never crashes."""
    text = _pdf_text(_render_reportlab_answer_key_pdf(_doc(slot_question_id=None), {}))

    assert "unfilled" in text


def test_answer_key_pdf_carries_branding():
    """The marking scheme is a school document too; branding header must show."""
    document = _doc()
    document["paper"]["branding"] = {"schoolName": "Greenwood High School"}

    text = _pdf_text(_render_reportlab_answer_key_pdf(document, {"slot_A_01": "H2O"}))

    assert "Greenwood High School" in text
