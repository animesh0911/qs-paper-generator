"""Contract-valid PaperDocumentV1 fixtures for view tests.

The draft PATCH endpoints validate saved documents against the v1 contract
(``papers.document_contract``), the same schema the real editor round-trips.
Tests that exercise those endpoints therefore need documents that pass the
schema — these helpers build the smallest such document, synthesising a
matching ``questions`` entry for every id a slot references so the
cross-reference checks (marks/type/language) hold by construction.
"""

from __future__ import annotations

PAPER_SCHEMA = "paper_document.v1"


def contract_slot(
    slot_id: str,
    qid: str | None,
    *,
    number: str = "1",
    marks: int = 1,
    qtype: str = "mcq",
) -> dict:
    return {
        "id": slot_id,
        "number": number,
        "marks": marks,
        "type": qtype,
        "selectedQuestionId": qid,
        "alternateQuestionIds": [],
        "locked": False,
    }


def contract_question(qid: str, *, marks: int = 1, qtype: str = "mcq") -> dict:
    return {
        "id": qid,
        "language": "en",
        "defaultMarks": marks,
        "type": qtype,
        "rawText": "Question text",
        "content": {"stem": [{"type": "paragraph", "text": "Question text"}]},
        "metadata": {
            "classLevel": "10",
            "subject": "Science",
            "chapterNames": [],
            "difficulty": "medium",
        },
        "source": {"type": "question_bank", "name": "Test Bank"},
    }


def contract_document(*slots: dict) -> dict:
    """A minimal contract-valid paper document with one section of ``slots``."""
    total_marks = sum(slot.get("marks", 0) for slot in slots)
    referenced: dict[str, dict] = {}
    for slot in slots:
        qid = slot.get("selectedQuestionId")
        if qid:
            referenced.setdefault(qid, slot)
        for alt in slot.get("alternateQuestionIds") or []:
            referenced.setdefault(alt, slot)
    return {
        "schemaVersion": PAPER_SCHEMA,
        "request": {
            "id": "req_1",
            "language": "en",
            "classLevel": "10",
            "subject": "Science",
            "examType": "full_term",
            "filters": {"chapters": [], "englishOnly": True},
        },
        "template": {
            "id": "tmpl_test_v1",
            "name": "Test Template",
            "classLevel": "10",
            "subject": "Science",
            "examType": "full_term",
            "totalMarks": total_marks,
            "durationMinutes": 60,
            "language": "en",
        },
        "format": {
            "id": "fmt_test_v1",
            "page": {"size": "A4", "orientation": "portrait"},
            "layout": {
                "marks": "right_column",
                "questionNumbers": "left_column",
                "mcqOptions": "two_column",
                "instructions": "note_table_then_general",
                "masthead": "cbse_compact",
                "footer": "code_page_pto",
            },
        },
        "paper": {
            "id": "paper_1",
            "title": "Science — Practice Paper",
            "totalMarks": total_marks,
            "durationMinutes": 60,
            "language": "en",
            "sections": [
                {
                    "id": "A",
                    "title": "Section A",
                    "marks": total_marks,
                    "slots": list(slots),
                }
            ],
        },
        "questions": [
            contract_question(
                qid,
                marks=slot.get("marks", 1),
                qtype=slot.get("type", "mcq"),
            )
            for qid, slot in referenced.items()
        ],
    }
