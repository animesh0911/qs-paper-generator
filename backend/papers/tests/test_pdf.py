"""Unit tests for render_paper_pdf.

The renderer consumes a PaperDocumentV1 dict directly — these tests build
a minimal document fixture and verify the bytes back without touching the DB.
"""

import pdfplumber

from papers.pdf import render_paper_pdf


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


def test_render_returns_pdf_bytes():
    pdf = render_paper_pdf(_doc())
    assert pdf[:4] == b"%PDF"


def test_render_handles_unfilled_slot():
    """Unfilled slot (selectedQuestionId=None) must render without raising."""
    pdf = render_paper_pdf(_doc(slot_question_id=None))
    assert pdf[:4] == b"%PDF"


def test_render_uses_slot_override_instead_of_stale_question_text(tmp_path):
    """PDF must reflect final Slot edits because PaperDocumentV1 is canonical."""
    document = _doc()
    document["paper"]["sections"][0]["slots"][0]["overrides"] = {
        "modifiedFromSource": True,
        "regions": {
            "stem": [{"type": "paragraph", "text": "Teacher edited water question."}]
        },
    }

    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(render_paper_pdf(document))

    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    assert "Teacher edited water question." in text
    assert "What is water?" not in text
