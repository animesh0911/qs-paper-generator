"""Server-side PaperDocumentV1 contract guard.

``PaperBuilder.assemble`` runs this over the document it is about to return so a
contract violation is caught here — with precise, logged messages — instead of
silently shipping to the browser and surfacing as the opaque editor error
"Unable to open paper".

Single source of truth: the document *shape* is validated against
``paper_document_v1.schema.json``, a JSON Schema generated from the frontend Zod
schema (``paper-document.schema.ts``) — the one definition both sides derive
from, kept in sync by a drift-guard test on the frontend. JSON Schema cannot
express cross-references, so the Zod ``.superRefine`` (slot ↔ question
referential integrity and slot/question compatibility) is mirrored here as a
Python check.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator

_SCHEMA_PATH = Path(__file__).with_name("paper_document_v1.schema.json")


class PaperDocumentContractError(Exception):
    """A built PaperDocument violates the v1 contract. Lists every violation."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    schema = json.loads(_SCHEMA_PATH.read_text())
    return Draft202012Validator(schema)


def validate_paper_document(document: dict) -> list[str]:
    """Return contract-violation messages for ``document`` (empty == valid)."""
    errors = [
        f"{_json_path(error.absolute_path)}: {error.message}"
        for error in sorted(
            _validator().iter_errors(document), key=lambda e: list(e.absolute_path)
        )
    ]
    # Cross-reference checks JSON Schema can't express (mirrors Zod superRefine).
    errors.extend(_validate_references(document))
    return errors


def _json_path(path) -> str:
    parts = "".join(
        f"[{part}]" if isinstance(part, int) else f".{part}" for part in path
    )
    return f"document{parts}" if parts else "document"


def _validate_references(document: dict) -> list[str]:
    """Mirror the Zod superRefine: every slot's selected/alternate id must
    resolve to a question, and a referenced question must match the slot's
    marks/type and the paper's language."""
    paper = document.get("paper")
    questions = document.get("questions")
    if not isinstance(paper, dict) or not isinstance(questions, list):
        return []  # shape errors already reported by the JSON Schema pass.

    questions_by_id = {
        q["id"]: q for q in questions if isinstance(q, dict) and "id" in q
    }
    language = paper.get("language")

    errors: list[str] = []
    for section in paper.get("sections") or []:
        for slot in section.get("slots") or []:
            slot_id = slot.get("id", "?")
            selected = slot.get("selectedQuestionId")
            referenced = [
                qid
                for qid in [selected, *(slot.get("alternateQuestionIds") or [])]
                if qid is not None
            ]
            for qid in referenced:
                if qid not in questions_by_id:
                    label = "selects" if qid == selected else "lists alternate"
                    errors.append(f"slot {slot_id} {label} unknown question {qid!r}")
                    continue
                q = questions_by_id[qid]
                if (
                    q.get("defaultMarks") != slot.get("marks")
                    or q.get("type") != slot.get("type")
                    or q.get("language") != language
                ):
                    errors.append(
                        f"slot {slot_id} references incompatible question {qid!r} "
                        "(marks/type/language mismatch)"
                    )
    return errors
