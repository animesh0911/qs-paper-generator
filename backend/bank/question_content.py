"""Shared Question ``content`` normalisation + contract validation.

One source of truth for the contract-shape rules that both *ingestion* (where
``Question.content`` is first persisted) and *paper assembly* (where it is
emitted into a PaperDocumentV1) must honour. Keeping the rules here stops the
two paths from drifting and stops contract-invalid content from silently
reaching the editor — the failure mode that showed up as "Unable to open paper"
when a chapter's case-based questions stored a choice group with no
``displayStyle`` (contract §9 requires it).

Two operations:
- ``normalise_question_content`` *repairs* the cheap, unambiguous gaps (a
  ChoiceGroup missing ``displayStyle``/``chooseCount``) without mutating the
  caller's dict. Ingestion runs it at the door; the document builder runs it
  again as a belt-and-suspenders for rows persisted before this existed.
- ``validate_question_content`` *reports* the contract violations the editor's
  schema enforces strictly, so a bad row is caught server-side rather than in
  the browser.
"""

from __future__ import annotations

from collections.abc import Iterable

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


def validate_question_content(content: object, *, where: str = "content") -> list[str]:
    """Return human-readable messages for contract violations in ``content``.

    Empty list means valid. Checks the invariants the editor's schema enforces
    strictly and that are not guaranteed by the document builder's construction:
    ``content`` is a dict, and every ChoiceGroup carries a well-typed
    ``displayStyle`` (in the enum), ``chooseCount`` (int), and ``options``
    (list). Runs against *normalised* content in the assembly path, so a
    violation here means a genuine structural problem, not a missing default.
    """
    errors: list[str] = []
    if not isinstance(content, dict):
        errors.append(f"{where} must be an object")
        return errors

    groups = content.get("choices")
    if groups is not None:
        if not isinstance(groups, list):
            errors.append(f"{where}.choices must be a list")
        else:
            for index, group in enumerate(groups):
                errors.extend(
                    _validate_choice_group(group, f"{where}.choices[{index}]")
                )
    return errors


def _validate_choice_group(group: object, where: str) -> Iterable[str]:
    if not isinstance(group, dict):
        yield f"{where} must be an object"
        return
    style = group.get("displayStyle")
    if style not in CHOICE_DISPLAY_STYLES:
        yield (
            f"{where}.displayStyle must be one of "
            f"{list(CHOICE_DISPLAY_STYLES)} (got {style!r})"
        )
    if not isinstance(group.get("chooseCount"), int):
        yield f"{where}.chooseCount must be an integer"
    if not isinstance(group.get("options"), list):
        yield f"{where}.options must be a list"
