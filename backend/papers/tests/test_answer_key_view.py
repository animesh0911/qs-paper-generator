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

from bank.models import AnswerSource
from conftest import QuestionFactory
from papers.answer_document import (
    ANSWER_SCHEMA_VERSION,
    build_answer_document,
    printable_answers_by_slot,
)
from papers.models import Paper, PaperStatus
from papers.tests.contract_documents import contract_document, contract_slot


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
def test_answer_key_pdf_renders_from_saved_answer_document(
    api_client, user, monkeypatch
):
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
    render_calls = []

    def fake_render(document, answers_by_slot, print_url=None):
        render_calls.append(answers_by_slot)
        return b"%PDF answer"

    monkeypatch.setattr("papers.views.render_answer_key_pdf", fake_render)

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
    assert render_calls == [{"slot_A_01": "Real"}]


@pytest.mark.django_db
def test_editor_draft_patch_rejects_malformed_answer_document(api_client, user):
    document = contract_document()
    paper = Paper.objects.create(
        created_by=user, status=PaperStatus.DRAFT, document=document
    )

    resp = api_client.patch(
        f"/api/papers/{paper.pk}/editor-draft/",
        {"document": document, "answer_document": "not an object"},
        format="json",
    )

    assert resp.status_code == 400
    assert resp.data["error"] == "answer_document must be an object."


@pytest.mark.django_db
def test_editor_draft_patch_rebuilds_swapped_answer_from_bank(api_client, user):
    """Frontend saves cannot carry bank answers for newly-swapped questions.

    When the answer entry is missing/stale, PATCH reconciles from the bank before
    persisting so the later package download does not permanently lose the new
    question's source answer.
    """
    old = QuestionFactory(answer="STALE_OLD_ANSWER", answer_source=AnswerSource.HUMAN)
    new = QuestionFactory(answer="FRESH_NEW_ANSWER", answer_source=AnswerSource.HUMAN)

    document = contract_document(contract_slot("slot_A_01", f"q_{old.pk}"))
    paper = Paper.objects.create(
        created_by=user, status=PaperStatus.DRAFT, document=document
    )
    paper.answer_document = build_answer_document(paper)
    paper.save(update_fields=["answer_document"])

    swapped_document = contract_document(contract_slot("slot_A_01", f"q_{new.pk}"))
    swapped_document["paper"]["id"] = f"paper_{paper.pk}"
    stale_answer_document = {
        **paper.answer_document,
        "paperId": f"paper_{paper.pk}",
        "answersBySlotId": {},
    }

    resp = api_client.patch(
        f"/api/papers/{paper.pk}/editor-draft/",
        {"document": swapped_document, "answer_document": stale_answer_document},
        format="json",
    )

    assert resp.status_code == 200
    assert resp.data["document"] == swapped_document
    response_entry = resp.data["answer_document"]["answersBySlotId"]["slot_A_01"]
    assert response_entry["questionId"] == f"q_{new.pk}"
    assert response_entry["content"] == [
        {"type": "paragraph", "text": "FRESH_NEW_ANSWER"}
    ]
    paper.refresh_from_db()
    entry = paper.answer_document["answersBySlotId"]["slot_A_01"]
    assert entry["questionId"] == f"q_{new.pk}"
    assert entry["content"] == [{"type": "paragraph", "text": "FRESH_NEW_ANSWER"}]


@pytest.mark.django_db
def test_answer_key_pdf_never_prints_stale_answer_after_legacy_swap(
    api_client, user, monkeypatch
):
    """Regression: before #122 the PDF joined live bank answers by the slot's
    current question, so a swap printed the new answer. The saved snapshot must
    not reintroduce stale answers when a question is swapped through the legacy
    paper PATCH — the marking scheme prints the current question's answer.
    """
    old = QuestionFactory(answer="STALE_OLD_ANSWER", answer_source=AnswerSource.HUMAN)
    new = QuestionFactory(answer="FRESH_NEW_ANSWER", answer_source=AnswerSource.HUMAN)

    def _doc(qid: str) -> dict:
        return {
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
                                "selectedQuestionId": qid,
                            }
                        ],
                    }
                ],
            },
        }

    paper = Paper.objects.create(
        created_by=user, status=PaperStatus.DRAFT, document=_doc(f"q_{old.pk}")
    )
    paper.answer_document = build_answer_document(paper)
    paper.save(update_fields=["answer_document"])
    # Legacy document-only swap leaves answer_document pointing at the old answer.
    paper.document = _doc(f"q_{new.pk}")
    paper.save(update_fields=["document"])

    render_calls = []

    def fake_render(document, answers_by_slot, print_url=None):
        render_calls.append(answers_by_slot)
        return b"%PDF answer"

    monkeypatch.setattr("papers.views.render_answer_key_pdf", fake_render)

    resp = api_client.get(f"/api/papers/{paper.pk}/answer-key/pdf/")

    assert resp.status_code == 200
    assert render_calls[0]["slot_A_01"] == "FRESH_NEW_ANSWER"
    assert "STALE_OLD_ANSWER" not in render_calls[0].values()
