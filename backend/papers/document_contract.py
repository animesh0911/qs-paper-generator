"""Server-side PaperDocumentV1 contract guard.

``PaperBuilder.assemble`` runs this over the document it is about to return so a
contract violation is caught here — with a precise, logged message — instead of
silently shipping to the browser and surfacing as the opaque editor error
"Unable to open paper". It deliberately checks only the invariants the editor's
Zod schema enforces strictly and that the builder does not guarantee by
construction: required top-level keys, per-question ``content`` shape (via the
shared ``bank.question_content`` validator), and slot→question referential
integrity. It is a safety net against our own regressions, not a full mirror of
the frontend schema.
"""

from __future__ import annotations

from bank.question_content import validate_question_content

_REQUIRED_TOP_LEVEL_KEYS = (
    "schemaVersion",
    "request",
    "template",
    "format",
    "paper",
    "questions",
)


class PaperDocumentContractError(Exception):
    """A built PaperDocument violates the v1 contract. Lists every violation."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def validate_paper_document(document: dict) -> list[str]:
    """Return contract-violation messages for ``document`` (empty == valid)."""
    errors: list[str] = []

    missing = [k for k in _REQUIRED_TOP_LEVEL_KEYS if k not in document]
    if missing:
        errors.append(f"document missing required keys: {missing}")

    questions = document.get("questions")
    if not isinstance(questions, list):
        errors.append("document.questions must be a list")
        return errors  # nothing more can be checked without the question list

    question_ids: set[str] = set()
    for index, question in enumerate(questions):
        if not isinstance(question, dict):
            errors.append(f"questions[{index}] must be an object")
            continue
        qid = question.get("id")
        if isinstance(qid, str):
            question_ids.add(qid)
        errors.extend(
            validate_question_content(
                question.get("content"), where=f"questions[{index}].content"
            )
        )

    errors.extend(_validate_slot_references(document, question_ids))
    return errors


def _validate_slot_references(document: dict, question_ids: set[str]) -> list[str]:
    """Every slot's selected/alternate question id must resolve to a question."""
    errors: list[str] = []
    sections = (document.get("paper") or {}).get("sections") or []
    for section in sections:
        for slot in section.get("slots") or []:
            selected = slot.get("selectedQuestionId")
            slot_id = slot.get("id", "?")
            if selected is not None and selected not in question_ids:
                errors.append(
                    f"slot {slot_id} selects unknown question id {selected!r}"
                )
            for alt in slot.get("alternateQuestionIds") or []:
                if alt not in question_ids:
                    errors.append(f"slot {slot_id} lists unknown alternate id {alt!r}")
    return errors
