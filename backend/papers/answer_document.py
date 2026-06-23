"""Builds, validates, and flattens paper_answer_document.v1.

The paper-local answer document is a draft artifact parallel to
``Paper.document``. It carries model answers keyed by **slot id** so the editor
can review, edit, save, and print answers without ever mutating the shared bank
``Question.answer`` (issue #122). Answers are deliberately absent from
``paper_document.v1``; this is the one paper-scoped place they live, gated to the
paper owner by the editor-draft view.

Three concerns live here so neither the builder, the view, nor the PDF renderer
re-derives the shape:

* ``build_answer_document`` — assemble-time construction from bank answers.
* ``validate_answer_document`` — the consistency gate the editor-draft PATCH
  applies (issue #125): a save is rejected when the paper and answer documents
  disagree, so a stale answer key can never reach PDF preview/download.
* ``printable_answers_by_slot`` — flatten saved entries to slot-keyed text for
  the marking-scheme PDF, preserving the issue #87 trust boundary.
"""

from __future__ import annotations

from bank.models import AnswerSource, Question

ANSWER_SCHEMA_VERSION = "paper_answer_document.v1"

# Editor-facing provenance. The bank stores four AnswerSource values; the editor
# only needs to know whether an answer is an unverified LLM draft (warn the
# teacher) or trustworthy source/human/verified content.
SOURCE_GENERATED = "generated"
SOURCE_SOURCE = "source"

# Marking-scheme placeholder for a filled slot whose answer is missing or not
# yet trustworthy. Mirrors the loud-fail intent of the old "(no answer on file)".
ANSWER_NOT_AVAILABLE = "Answer not available"


def editor_source(answer_text: str, answer_source: str) -> str:
    """Map a bank ``AnswerSource`` to the editor-facing ``source`` value.

    Only an unverified generated answer that actually carries text is flagged
    ``"generated"`` so the editor can warn it is unverified (issue #87). Human,
    extracted, verified, or empty answers are ``"source"``. There is no third
    value for "missing" — that is represented by empty ``content`` (issue #122).
    """
    if answer_text and answer_source == AnswerSource.GENERATED_UNVERIFIED:
        return SOURCE_GENERATED
    return SOURCE_SOURCE


def _answer_content(answer_text: str) -> list[dict]:
    """Wrap stored answer text as contract ``ContentItem[]`` (empty if blank)."""
    if not answer_text:
        return []
    return [{"type": "paragraph", "text": answer_text}]


def _slot_id(slot: dict) -> str | None:
    """Return the slot id across current and legacy document keys, else None.

    Mirrors ``papers.pdf._slot_id`` so a client-supplied or legacy document with
    ``slotId`` instead of ``id`` is parsed, not crashed on with a ``KeyError``.
    """
    return slot.get("id") or slot.get("slotId")


def _selected_slots(document: dict):
    """Yield ``(slot_id, selected_question_id)`` for every filled slot, in order.

    Slots with no ``selectedQuestionId`` are skipped — unfilled slots are
    excluded from the answer document (issue #125 decision). A slot with no id at
    all is skipped too: it cannot key an answer, and tolerating it keeps a
    malformed client document a clean validation pass/fail rather than a 500.
    """
    paper = (document or {}).get("paper", {})
    for section in paper.get("sections", []):
        for slot in section.get("slots", []):
            qid = slot.get("selectedQuestionId")
            slot_id = _slot_id(slot)
            if qid and slot_id:
                yield slot_id, qid


def build_answer_document(paper) -> dict:
    """Build the ``paper_answer_document.v1`` consistent with the paper document.

    Keyed by selected slot id. Each entry carries the slot id, the selected
    question id, the bank answer as rich content (empty when no answer exists),
    editor-facing provenance, and ``modified``. A missing bank answer never fails
    the build; it yields an empty-content entry.

    Reconciles against any existing ``paper.answer_document``: an entry whose
    ``questionId`` still matches the slot's current selected question is kept
    verbatim, preserving teacher edits and the ``modified`` flag. A slot that is
    new, or whose question was swapped (e.g. through the legacy paper PATCH which
    does not maintain answers), is rebuilt from the bank so a stale answer is
    never carried forward (issue #125). At assembly there is no existing
    document, so every entry is fresh. This is also what makes older drafts with
    no answer document gain one lazily on first editor-draft load.
    """
    document = paper.document or {}
    existing = (paper.answer_document or {}).get("answersBySlotId") or {}
    answers_by_qid = _bank_answers_by_question_id(document)

    answers_by_slot: dict[str, dict] = {}
    for slot_id, qid in _selected_slots(document):
        prior = existing.get(slot_id)
        if isinstance(prior, dict) and prior.get("questionId") == qid:
            answers_by_slot[slot_id] = prior
            continue
        text, source = answers_by_qid.get(qid, ("", ""))
        answers_by_slot[slot_id] = {
            "slotId": slot_id,
            "questionId": qid,
            "content": _answer_content(text),
            "source": editor_source(text, source),
            "modified": False,
        }

    return {
        "schemaVersion": ANSWER_SCHEMA_VERSION,
        "paperId": f"paper_{paper.pk}",
        "answersBySlotId": answers_by_slot,
    }


def _bank_answers_by_question_id(document: dict) -> dict[str, tuple[str, str]]:
    """Map contract question id (``"q_{pk}"``) to ``(answer, answer_source)``.

    Reads the bank directly — answers never travel through a client-facing
    serializer. Only the questions selected into filled slots are fetched.
    """
    pks: dict[int, str] = {}
    for _slot_id, qid in _selected_slots(document):
        pk = _pk_from_question_id(qid)
        if pk is not None:
            pks[pk] = qid
    if not pks:
        return {}
    rows = Question.objects.filter(pk__in=pks).values("pk", "answer", "answer_source")
    return {pks[row["pk"]]: (row["answer"], row["answer_source"]) for row in rows}


def _pk_from_question_id(question_id) -> int | None:
    """Parse a contract ``selectedQuestionId`` (``"q_{pk}"``) back to a PK."""
    if isinstance(question_id, str) and question_id.startswith("q_"):
        try:
            return int(question_id[2:])
        except ValueError:
            return None
    return None


def validate_answer_document(document: dict, answer_document: dict) -> list[str]:
    """Return consistency errors between a paper and its answer document.

    Issue #125 rule — reject a draft save loudly when the two documents
    disagree, so a swapped question can never leave a stale answer behind:

    * a filled slot has no answer entry;
    * an answer entry references a ``slotId`` absent from the paper document;
    * an answer entry's ``questionId`` does not match that slot's current
      ``selectedQuestionId``;
    * an answer entry's ``content`` is present but is not a list.

    The ``content`` type check matters because a saved non-list ``content`` would
    later crash the answer-key PDF (``_content_to_text`` iterates it). Catching it
    here keeps a bad client payload a clean 400, not a 500 at print time.

    An empty list means the documents are consistent. ``schemaVersion`` is
    validated first; a wrong version short-circuits the rest.
    """
    if not isinstance(answer_document, dict):
        return ["answer_document must be an object."]
    if answer_document.get("schemaVersion") != ANSWER_SCHEMA_VERSION:
        return [f"answer_document.schemaVersion must be '{ANSWER_SCHEMA_VERSION}'."]

    entries = answer_document.get("answersBySlotId")
    if not isinstance(entries, dict):
        return ["answer_document.answersBySlotId must be an object."]

    selected_by_slot = dict(_selected_slots(document))
    errors: list[str] = []

    for slot_id, qid in selected_by_slot.items():
        entry = entries.get(slot_id)
        # A missing or malformed (non-object) entry both fail the same way: the
        # slot has no usable answer. Guarding the type keeps a bad client payload
        # a clean 400, not a 500 on ``.get`` below.
        if not isinstance(entry, dict):
            errors.append(f"Slot {slot_id!r} has no answer entry.")
            continue
        if entry.get("questionId") != qid:
            errors.append(
                f"Slot {slot_id!r} answer questionId {entry.get('questionId')!r} "
                f"does not match selected question {qid!r}."
            )
        if "content" in entry and not isinstance(entry["content"], list):
            errors.append(f"Slot {slot_id!r} answer content must be a list.")

    for slot_id in entries:
        if slot_id not in selected_by_slot:
            errors.append(
                f"Answer entry {slot_id!r} references a slot not in the paper."
            )

    return errors


def printable_answers_by_slot(answer_document: dict) -> dict[str, str]:
    """Flatten saved answer entries to ``{slot_id: text}`` for the PDF.

    Only entries safe to print are included; the renderer falls back to
    ``ANSWER_NOT_AVAILABLE`` for the rest. An entry is suppressed when:

    * its content is empty (no answer on file), or
    * it is an unverified generated draft the teacher has not reviewed
      (``source == "generated"`` and ``modified`` is false) — this preserves the
      issue #87 trust boundary: blind LLM output never reaches a marking scheme
      until a human edits or verifies it.
    """
    entries = (answer_document or {}).get("answersBySlotId") or {}
    printable: dict[str, str] = {}
    for slot_id, entry in entries.items():
        # A non-object entry (only reachable from legacy/corrupt stored data,
        # since the PATCH validator now rejects it) has no printable answer.
        if not isinstance(entry, dict):
            continue
        if entry.get("source") == SOURCE_GENERATED and not entry.get("modified"):
            continue
        content = entry.get("content")
        text = _content_to_text(content if isinstance(content, list) else [])
        if text:
            printable[slot_id] = text
    return printable


def _content_to_text(content: list) -> str:
    """Join a ``ContentItem[]`` to plain text for the marking-scheme PDF.

    Non-dict items are skipped defensively — print rendering must not crash on a
    malformed legacy entry the way it would on ``"a string".get(...)``.
    """
    parts = [
        item.get("text") or item.get("latex") or ""
        for item in content
        if isinstance(item, dict)
    ]
    return "\n".join(part for part in parts if part).strip()
