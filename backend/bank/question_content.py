"""Shared Question ``content`` repair used at ingestion and paper assembly.

``Question.content`` is first persisted at ingestion and later emitted into a
PaperDocumentV1 at assembly. Both paths run ``normalise_question_content`` to
fill the cheap, unambiguous contract gaps some ingested rows carry — chiefly a
ChoiceGroup missing ``displayStyle``/``chooseCount`` — so contract-invalid
content never reaches the editor (the "Unable to open paper" failure, contract
§9 requires those fields).

This is *repair*, not validation: the authoritative shape check lives in
``papers.document_contract``, which validates the assembled document against the
JSON Schema generated from the frontend Zod schema (the single source of truth).
"""

from __future__ import annotations

# Contract §9: a ChoiceGroup's displayStyle is one of these. Mirrors the
# frontend Zod enum (``paper-document.schema.ts``).
CHOICE_DISPLAY_STYLES = ("or", "choose_any")
_DEFAULT_DISPLAY_STYLE = "or"
_DEFAULT_CHOOSE_COUNT = 1


def normalise_question_content(content: dict) -> dict:
    """Return ``content`` with contract-required ChoiceGroup fields filled.

    A group with N options where the teacher answers ``chooseCount`` of them is
    an "or" choice, so a missing ``displayStyle`` defaults to "or" and a missing
    ``chooseCount`` to 1. The input dict is never mutated; an already-valid
    ``content`` is returned unchanged (same object) so callers can cheaply tell
    nothing was repaired.
    """
    if not isinstance(content, dict):
        return content
    groups = content.get("choices")
    if not isinstance(groups, list):
        return content

    normalised = []
    changed = False
    for group in groups:
        if isinstance(group, dict) and (
            "displayStyle" not in group or "chooseCount" not in group
        ):
            group = {
                "displayStyle": group.get("displayStyle", _DEFAULT_DISPLAY_STYLE),
                "chooseCount": group.get("chooseCount", _DEFAULT_CHOOSE_COUNT),
                **group,
            }
            changed = True
        normalised.append(group)
    if not changed:
        return content
    return {**content, "choices": normalised}
