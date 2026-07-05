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
    """Return ``content`` repaired to the PaperDocumentV1 content contract.

    Ingested rows occasionally carry two cheap shape defects:

    * a ChoiceGroup missing ``displayStyle``/``chooseCount``;
    * a case-based subpart whose ``content`` is itself ``{"choices": [...]}``,
      even though contract §9 requires each subpart ``content`` to be a
      ContentItem[] and only top-level ``content.choices`` may hold ChoiceGroups.

    The latter appears when a paper has an OR choice inside one sub-question. We
    preserve the alternatives by lifting that nested group into top-level
    ``choices`` and prefixing option labels with the subpart label (for example
    ``c(i)`` / ``c(ii)``). The original dict is never mutated.
    """
    if not isinstance(content, dict):
        return content

    changed = False
    result = content
    top_level_choices, choices_changed = _normalise_choice_groups(
        content.get("choices")
    )
    if choices_changed:
        result = {**result, "choices": top_level_choices}
        changed = True

    subparts = content.get("subparts")
    if isinstance(subparts, list):
        repaired_subparts = []
        lifted_choices = []
        for subpart in subparts:
            repaired_subpart, nested_choices = _repair_subpart_choices(subpart)
            if repaired_subpart is not None:
                repaired_subparts.append(repaired_subpart)
            lifted_choices.extend(nested_choices)
            changed = changed or repaired_subpart is not subpart or bool(nested_choices)
        if lifted_choices:
            existing = result.get("choices") if isinstance(result, dict) else None
            existing_choices = existing if isinstance(existing, list) else []
            result = {
                **result,
                "subparts": repaired_subparts,
                "choices": [*existing_choices, *lifted_choices],
            }
        elif changed:
            result = {**result, "subparts": repaired_subparts}

    return result if changed else content


def _normalise_choice_groups(groups) -> tuple[list, bool]:
    if not isinstance(groups, list):
        return [], False

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
    return normalised, changed


def _repair_subpart_choices(subpart) -> tuple[object | None, list[dict]]:
    if not isinstance(subpart, dict):
        return subpart, []
    nested_content = subpart.get("content")
    if not isinstance(nested_content, dict):
        return subpart, []
    nested_groups, groups_changed = _normalise_choice_groups(
        nested_content.get("choices")
    )
    if not nested_groups:
        return subpart, []

    subpart_label = str(subpart.get("label") or "").strip()
    lifted_groups = []
    for group in nested_groups:
        if not isinstance(group, dict):
            lifted_groups.append(group)
            continue
        options = []
        for option in group.get("options") or []:
            if not isinstance(option, dict):
                options.append(option)
                continue
            option_label = str(option.get("label") or "").strip()
            prefixed_label = (
                f"{subpart_label}({option_label})"
                if subpart_label and option_label
                else subpart_label or option_label
            )
            option = {**option, "label": prefixed_label}
            if "marks" not in option and subpart.get("marks") is not None:
                option["marks"] = subpart["marks"]
            options.append(option)
        lifted_groups.append({**group, "options": options})

    repaired_content = _content_items_from_nested_subpart_content(nested_content)
    repaired_subpart = (
        {**subpart, "content": repaired_content} if repaired_content else None
    )
    return repaired_subpart, lifted_groups


def _content_items_from_nested_subpart_content(content: dict) -> list[dict]:
    """Best-effort salvage of real content from an invalid nested region map."""
    items = []
    for region in content_mod.ITEM_REGIONS:
        region_items = content.get(region)
        if isinstance(region_items, list):
            items.extend(item for item in region_items if isinstance(item, dict))
    return items
