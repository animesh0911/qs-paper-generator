"""Tests for the paper-local answer document (issue #122).

Covers the three concerns in ``papers.answer_document`` — assemble-time
construction, the editor-draft consistency gate (issue #125), and the
print-time flattening that preserves the issue #87 trust boundary — plus the
``/editor-draft/`` endpoint that loads and saves both lanes together.

Each test states *why* the behaviour matters: answers are the one piece of
content the contract deliberately keeps out of the student-facing paper, so the
rules that gate them are correctness/trust rules, not cosmetic ones.
"""

from __future__ import annotations

import pytest

from bank.models import AnswerSource
from conftest import QuestionFactory
from papers.answer_document import (
    ANSWER_SCHEMA_VERSION,
    build_answer_document,
    printable_answers_by_slot,
    validate_answer_document,
)
from papers.models import Paper, PaperStatus

PAPER_SCHEMA = "paper_document.v1"


def _document(*slots: dict) -> dict:
    """A minimal paper document with one section holding the given slots."""
    return {
        "schemaVersion": PAPER_SCHEMA,
        "paper": {
            "title": "Science — Practice Paper",
            "sections": [{"id": "A", "title": "Section A", "slots": list(slots)}],
        },
    }


def _slot(slot_id: str, qid: str | None, *, number="1", marks=1) -> dict:
    return {
        "id": slot_id,
        "number": number,
        "marks": marks,
        "type": "mcq",
        "selectedQuestionId": qid,
    }


# --- build_answer_document ------------------------------------------------


@pytest.mark.django_db
def test_build_keys_entries_by_slot_id_not_question_id(user):
    """The answer document is paper-local, keyed by slot — so a later swap can
    replace the answer at a position without colliding with the bank question."""
    q = QuestionFactory(answer="Model answer", answer_source=AnswerSource.HUMAN)
    paper = Paper.objects.create(
        created_by=user, document=_document(_slot("slot_A_01", f"q_{q.pk}"))
    )

    doc = build_answer_document(paper)

    assert doc["schemaVersion"] == ANSWER_SCHEMA_VERSION
    assert doc["paperId"] == f"paper_{paper.pk}"
    entry = doc["answersBySlotId"]["slot_A_01"]
    assert entry == {
        "slotId": "slot_A_01",
        "questionId": f"q_{q.pk}",
        "content": [{"type": "paragraph", "text": "Model answer"}],
        "source": "source",
        "modified": False,
    }


@pytest.mark.django_db
def test_build_flags_unverified_generated_as_generated(user):
    """An unverified LLM answer must reach the editor flagged ``generated`` so
    the teacher is warned it is not trustworthy (issue #87)."""
    q = QuestionFactory(
        answer="Bluffed", answer_source=AnswerSource.GENERATED_UNVERIFIED
    )
    paper = Paper.objects.create(
        created_by=user, document=_document(_slot("slot_A_01", f"q_{q.pk}"))
    )

    entry = build_answer_document(paper)["answersBySlotId"]["slot_A_01"]

    assert entry["source"] == "generated"
    assert entry["content"] == [{"type": "paragraph", "text": "Bluffed"}]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "source",
    [AnswerSource.HUMAN, AnswerSource.EXTRACTED, AnswerSource.GENERATED_VERIFIED],
)
def test_build_maps_trusted_sources_to_source(user, source):
    """Human, extracted, and human-verified answers are trustworthy → source."""
    q = QuestionFactory(answer="Real", answer_source=source)
    paper = Paper.objects.create(
        created_by=user, document=_document(_slot("slot_A_01", f"q_{q.pk}"))
    )

    entry = build_answer_document(paper)["answersBySlotId"]["slot_A_01"]

    assert entry["source"] == "source"


@pytest.mark.django_db
def test_build_missing_answer_is_empty_content_not_a_failure(user):
    """A question with no stored answer must not break assembly; it yields an
    empty-content entry so the slot still appears for the teacher to fill."""
    q = QuestionFactory(answer="", answer_source="")
    paper = Paper.objects.create(
        created_by=user, document=_document(_slot("slot_A_01", f"q_{q.pk}"))
    )

    entry = build_answer_document(paper)["answersBySlotId"]["slot_A_01"]

    assert entry["content"] == []
    assert entry["source"] == "source"


@pytest.mark.django_db
def test_build_skips_unfilled_slots(user):
    """An unfilled slot has no question to answer, so it gets no entry."""
    paper = Paper.objects.create(
        created_by=user, document=_document(_slot("slot_A_01", None))
    )

    assert build_answer_document(paper)["answersBySlotId"] == {}


# --- validate_answer_document (issue #125) --------------------------------


def _answer_doc(*entries: dict) -> dict:
    return {
        "schemaVersion": ANSWER_SCHEMA_VERSION,
        "paperId": "paper_1",
        "answersBySlotId": {e["slotId"]: e for e in entries},
    }


def _entry(slot_id: str, qid: str) -> dict:
    return {"slotId": slot_id, "questionId": qid, "content": [], "source": "source"}


def test_validate_consistent_documents_pass():
    document = _document(_slot("slot_A_01", "q_1"))
    answer_document = _answer_doc(_entry("slot_A_01", "q_1"))

    assert validate_answer_document(document, answer_document) == []


def test_validate_rejects_filled_slot_with_no_answer_entry():
    """A filled slot without an answer entry means the key is incomplete."""
    document = _document(_slot("slot_A_01", "q_1"))

    errors = validate_answer_document(document, _answer_doc())

    assert any("slot_A_01" in e and "no answer entry" in e for e in errors)


def test_validate_rejects_malformed_entry():
    """A non-object answer entry is a bad client payload — it must surface as a
    consistency error (clean 400), never crash the validator."""
    document = _document(_slot("slot_A_01", "q_1"))
    answer_document = {
        "schemaVersion": ANSWER_SCHEMA_VERSION,
        "answersBySlotId": {"slot_A_01": "not-an-object"},
    }

    errors = validate_answer_document(document, answer_document)

    assert any("no answer entry" in e for e in errors)


def test_validate_rejects_stale_answer_after_swap():
    """The core swap guard: if the slot now selects q_2 but the answer entry
    still points at q_1, the save is rejected so the old answer can't print."""
    document = _document(_slot("slot_A_01", "q_2"))
    answer_document = _answer_doc(_entry("slot_A_01", "q_1"))

    errors = validate_answer_document(document, answer_document)

    assert any("does not match selected question" in e for e in errors)


def test_validate_rejects_orphan_answer_entry():
    """An answer keyed to a slot that no longer exists is a stale leftover."""
    document = _document(_slot("slot_A_01", "q_1"))
    answer_document = _answer_doc(
        _entry("slot_A_01", "q_1"), _entry("slot_A_99", "q_9")
    )

    errors = validate_answer_document(document, answer_document)

    assert any("slot_A_99" in e and "not in the paper" in e for e in errors)


def test_validate_rejects_wrong_schema_version():
    document = _document(_slot("slot_A_01", "q_1"))

    errors = validate_answer_document(document, {"schemaVersion": "wrong"})

    assert errors and "schemaVersion" in errors[0]


# --- printable_answers_by_slot (issue #87 trust boundary) -----------------


def test_printable_suppresses_unreviewed_generated_answer():
    """A raw unverified LLM answer the teacher has not touched must not print in
    a marking scheme — the #87 trust boundary, now enforced at print time."""
    answer_document = _answer_doc(
        {
            "slotId": "slot_A_01",
            "questionId": "q_1",
            "content": [{"type": "paragraph", "text": "Bluffed"}],
            "source": "generated",
            "modified": False,
        }
    )

    assert printable_answers_by_slot(answer_document) == {}


def test_printable_includes_reviewed_generated_answer():
    """Once the teacher edits a generated answer (modified), it is trusted."""
    answer_document = _answer_doc(
        {
            "slotId": "slot_A_01",
            "questionId": "q_1",
            "content": [{"type": "paragraph", "text": "Edited"}],
            "source": "generated",
            "modified": True,
        }
    )

    assert printable_answers_by_slot(answer_document) == {"slot_A_01": "Edited"}


def test_printable_includes_source_answers_and_drops_empty():
    answer_document = _answer_doc(
        {
            "slotId": "slot_A_01",
            "questionId": "q_1",
            "content": [{"type": "paragraph", "text": "Real"}],
            "source": "source",
            "modified": False,
        },
        {
            "slotId": "slot_A_02",
            "questionId": "q_2",
            "content": [],
            "source": "source",
            "modified": False,
        },
    )

    assert printable_answers_by_slot(answer_document) == {"slot_A_01": "Real"}


# --- /editor-draft/ endpoint ----------------------------------------------


@pytest.mark.django_db
def test_editor_draft_get_returns_both_documents(api_client, user):
    q = QuestionFactory(answer="Real", answer_source=AnswerSource.HUMAN)
    document = _document(_slot("slot_A_01", f"q_{q.pk}"))
    paper = Paper.objects.create(created_by=user, document=document)
    paper.answer_document = build_answer_document(paper)
    paper.save(update_fields=["answer_document"])

    resp = api_client.get(f"/api/papers/{paper.pk}/editor-draft/")

    assert resp.status_code == 200
    assert resp.data["document"] == document
    assert resp.data["status"] == PaperStatus.DRAFT
    assert resp.data["answer_document"]["answersBySlotId"]["slot_A_01"]["content"]


@pytest.mark.django_db
def test_editor_draft_get_is_owner_scoped(api_client):
    """Answers are private to the paper owner — another teacher gets a 404."""
    paper = Paper.objects.create(
        created_by=_other_user(),
        document=_document(_slot("slot_A_01", "q_1")),
    )

    resp = api_client.get(f"/api/papers/{paper.pk}/editor-draft/")

    assert resp.status_code == 404


@pytest.mark.django_db
def test_editor_draft_patch_saves_both_and_bumps_revision(api_client, user):
    q = QuestionFactory(answer="Real", answer_source=AnswerSource.HUMAN)
    document = _document(_slot("slot_A_01", f"q_{q.pk}"))
    paper = Paper.objects.create(created_by=user, document=document, revision=0)
    answer_document = _answer_doc(
        {
            "slotId": "slot_A_01",
            "questionId": f"q_{q.pk}",
            "content": [{"type": "paragraph", "text": "Teacher edit"}],
            "source": "source",
            "modified": True,
        }
    )

    resp = api_client.patch(
        f"/api/papers/{paper.pk}/editor-draft/",
        {"document": document, "answer_document": answer_document},
        format="json",
    )

    assert resp.status_code == 200
    paper.refresh_from_db()
    assert paper.answer_document == answer_document
    assert paper.revision == 1


@pytest.mark.django_db
def test_editor_draft_patch_does_not_mutate_bank_answer(api_client, user):
    """Editor answer edits are paper-local — the shared bank answer is untouched
    (issue #122): another paper using the same question keeps the bank answer."""
    q = QuestionFactory(answer="Bank answer", answer_source=AnswerSource.HUMAN)
    document = _document(_slot("slot_A_01", f"q_{q.pk}"))
    paper = Paper.objects.create(created_by=user, document=document)
    answer_document = _answer_doc(
        {
            "slotId": "slot_A_01",
            "questionId": f"q_{q.pk}",
            "content": [{"type": "paragraph", "text": "Different edit"}],
            "source": "source",
            "modified": True,
        }
    )

    api_client.patch(
        f"/api/papers/{paper.pk}/editor-draft/",
        {"document": document, "answer_document": answer_document},
        format="json",
    )

    q.refresh_from_db()
    assert q.answer == "Bank answer"
    assert q.answer_source == AnswerSource.HUMAN


@pytest.mark.django_db
def test_editor_draft_patch_rejects_inconsistent_documents(api_client, user):
    """A stale answer (wrong questionId after a swap) is rejected with details
    so the frontend bug surfaces instead of a wrong answer being saved."""
    document = _document(_slot("slot_A_01", "q_2"))
    paper = Paper.objects.create(created_by=user, document=document)
    answer_document = _answer_doc(_entry("slot_A_01", "q_1"))

    resp = api_client.patch(
        f"/api/papers/{paper.pk}/editor-draft/",
        {"document": document, "answer_document": answer_document},
        format="json",
    )

    assert resp.status_code == 400
    assert resp.data["details"]


@pytest.mark.django_db
def test_editor_draft_patch_rejected_after_approval(api_client, user):
    document = _document(_slot("slot_A_01", "q_1"))
    paper = Paper.objects.create(
        created_by=user, document=document, status=PaperStatus.APPROVED
    )

    answer_document = _answer_doc(_entry("slot_A_01", "q_1"))
    resp = api_client.patch(
        f"/api/papers/{paper.pk}/editor-draft/",
        {"document": document, "answer_document": answer_document},
        format="json",
    )

    assert resp.status_code == 409


def _other_user():
    from conftest import UserFactory

    return UserFactory()
