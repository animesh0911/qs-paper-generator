"""Tests for the marking-scheme PDF source (issue #122).

Since #122 the answer-key PDF renders from the saved ``answer_document`` by
slot id, not from live bank answers. These tests pin the trust boundary that
must survive that move: an unverified generated answer the teacher has not
reviewed must never reach the marking scheme (issue #87), while saved/edited
answers must print in current slot order.

The gate now lives in ``printable_answers_by_slot``; it is exercised both
directly and through the owner-scoped PDF endpoint.
"""

from __future__ import annotations

import pytest

from papers.answer_document import ANSWER_SCHEMA_VERSION, printable_answers_by_slot
from papers.models import Paper, PaperStatus


def _answer_document(*entries: dict) -> dict:
    return {
        "schemaVersion": ANSWER_SCHEMA_VERSION,
        "paperId": "paper_1",
        "answersBySlotId": {e["slotId"]: e for e in entries},
    }


def _entry(slot_id, text, *, source="source", modified=False) -> dict:
    content = [{"type": "paragraph", "text": text}] if text else []
    return {
        "slotId": slot_id,
        "questionId": "q_1",
        "content": content,
        "source": source,
        "modified": modified,
    }


def test_unverified_generated_answer_is_suppressed():
    """Why this matters: this is the trust boundary — blind LLM output in a
    marking scheme is the failure mode #87 exists to prevent."""
    answer_document = _answer_document(
        _entry("slot_A_01", "Bluffed", source="generated", modified=False)
    )

    assert printable_answers_by_slot(answer_document) == {}


def test_saved_answers_pass_through_by_slot():
    """Source-backed and teacher-edited generated answers reach the scheme,
    keyed by the slot they currently occupy."""
    answer_document = _answer_document(
        _entry("slot_A_01", "Real", source="source"),
        _entry("slot_A_02", "Checked", source="generated", modified=True),
    )

    printable = printable_answers_by_slot(answer_document)

    assert printable == {"slot_A_01": "Real", "slot_A_02": "Checked"}


@pytest.mark.django_db
def test_answer_key_pdf_renders_from_saved_answer_document(api_client, user):
    """End-to-end: the owner's answer-key endpoint renders a PDF from the saved
    answer document (the document itself still carries no answers)."""
    document = {
        "schemaVersion": "paper_document.v1",
        "paper": {
            "title": "Science",
            "sections": [
                {
                    "id": "A",
                    "title": "Section A",
                    "slots": [
                        {
                            "id": "slot_A_01",
                            "number": "1",
                            "marks": 1,
                            "type": "mcq",
                            "selectedQuestionId": "q_1",
                        }
                    ],
                }
            ],
        },
    }
    paper = Paper.objects.create(
        created_by=user,
        status=PaperStatus.DRAFT,
        document=document,
        answer_document=_answer_document(_entry("slot_A_01", "Real")),
    )

    resp = api_client.get(f"/api/papers/{paper.pk}/answer-key/pdf/")

    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"
