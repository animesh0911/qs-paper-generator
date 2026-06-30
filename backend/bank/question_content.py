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

import re

from . import content as content_mod

# Contract §9: a ChoiceGroup's displayStyle is one of these. Mirrors the
# frontend Zod enum (``paper-document.schema.ts``).
CHOICE_DISPLAY_STYLES = ("or", "choose_any")
_DEFAULT_DISPLAY_STYLE = "or"
_DEFAULT_CHOOSE_COUNT = 1

# A stem (or text) carrying no real content — only enumeration scaffolding: a
# question number ("37."), a sub-part label ("(b)"), or a run of them
# ("39. (a)"). Mirrors ``bank.guardrails._ENUMERATION_ONLY_RE``.
_ENUMERATION_ONLY_RE = re.compile(
    r"^(?:\s*(?:\d{1,3}[.):]?|\(\s*[a-z0-9ivxlcdm]{1,4}\s*\)))+\s*$",
    re.IGNORECASE,
)


def _is_contentless(value: str) -> bool:
    """True when ``value`` is empty or only enumeration scaffolding."""
    stripped = (value or "").strip()
    return not stripped or bool(_ENUMERATION_ONLY_RE.match(stripped))


def repair_stem(content: dict, fallback_text: str) -> dict:
    """Rebuild a defective ``content.stem`` from the flat ``fallback_text``.

    Some ingested rows carry a stem that lost its body — it flattens to only a
    sub-part label ("(b)") or a number ("39. (a)") — while the full question
    survives in the flat ``text``. Both the bank view and the paper renderer
    prefer ``content.stem``, so the fragment would otherwise show in place of the
    real question (and in generated papers). When the stem is content-less but
    ``fallback_text`` carries real content, replace the stem with a single
    paragraph built from that text. The input dict is never mutated; an
    already-good stem is returned unchanged (same object).
    """
    if not isinstance(content, dict):
        return content
    if not _is_contentless(content_mod.flatten_text(content.get("stem"))):
        return content
    text = (fallback_text or "").strip()
    if not text or _is_contentless(text):
        return content
    return {**content, "stem": [{"type": "paragraph", "text": text}]}


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
