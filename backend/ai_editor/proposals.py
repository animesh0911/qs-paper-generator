"""AI editor proposal contract + deterministic guardrail validators.

PRD #30 lets a teacher ask the editor AI to change *chrome* — paper title and
header, instructions, section labels, approved format fields, and slot marks —
but the model must never become the source of truth for what is safe. So the
model returns a **scoped proposal** (a small list of replace-only patches, not a
re-written document and not BlockNote JSON), and this module is the deterministic
boundary that decides — independently of anything the model "reasoned" — whether
that proposal may reach preview/apply.

Two layers:

* **Structural contract** — :class:`EditProposal` / :class:`EditPatch` (pydantic)
  reject malformed model output (missing ``patches``, wrong types, …) before any
  guard runs. ``#34``'s drain handler parses raw model JSON through these.
* **Guardrails** — :func:`validate_proposal` runs deny-by-default: a patch is
  allowed *only* when it is a ``replace`` of a scalar value at an
  :data:`ALLOWED_PATH_PATTERNS` path whose ids resolve in the live document.
  Everything else is blocked and mapped to a named guard (:data:`GUARD_MESSAGES`)
  with a user-safe message — so "I can't rewrite sourced question text" reaches
  the teacher, never a stack trace. The forbidden categories the PRD enumerates
  (sourced question text, question-bank source data, section membership, question
  count, cross-section movement, raw BlockNote JSON, unknown operations, missing
  ids, oversized output, stale ``baseRevision``) all fall out of this single
  allowlist; the named guards exist to make each rejection legible.

Patterns / invariants:
- Patches address by **stable id**, not array index (``/paper/sections/<id>/...``)
  so a reorder can never silently retarget a patch (#32 decision).
- Marks edits are allowed but never trust the model's totals: a valid marks patch
  emits a recompute *warning* (``Total marks changed from X to Y``); the reducer
  owns the actual recomputation.
- The frontend re-validates with the same rules
  (``frontend/src/types/ai-proposal.schema.ts``); the shared contract is
  ``contracts/ai_proposal.v1.md``. Guard ids/messages must stay in sync — the
  parity test pins the id set.

Where it fits:
- Called by: ``ai_editor`` drain handlers (#34), before a proposal is stored.
- Contract: ``contracts/ai_proposal.v1.md``.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

# A proposal larger than this is refused outright rather than diffed — a model
# that wants to touch dozens of fields at once is not making a scoped edit, and
# an unbounded payload is a denial-of-service / runaway-cost vector.
MAX_PATCHES = 40
MAX_VALUE_CHARS = 20_000

# The only operation an editor-edit proposal may carry. ``add``/``remove``/``move``
# would change question count or section membership and are rejected as
# unsupported (see the guard mapping below).
ALLOWED_OP = "replace"


class EditPatch(BaseModel):
    """One scoped replace against the canonical paper document.

    ``op``/``value`` are intentionally permissive at the structural layer (``op``
    is a free string, ``value`` is ``Any``) so an unknown operation or a
    non-scalar BlockNote value surfaces as a *user-safe guard* in
    :func:`validate_proposal` rather than an opaque pydantic 422.
    """

    op: str
    path: str
    value: Any = None
    # The model's claim about the pre-edit value; advisory only — the guards read
    # the live document, never this, so a wrong oldValue cannot widen what apply
    # touches. Surfaced in the inspector diff.
    oldValue: Any = None  # noqa: N815 — camelCase matches the JSON contract


class EditProposal(BaseModel):
    """Structural shape of an editor-edit / refine proposal from the model."""

    summary: str = ""
    affected: list[dict] = Field(default_factory=list)
    patches: list[EditPatch] = Field(default_factory=list)


# Guard ids and the user-safe message each carries into the chat/inspector. The
# id set is the contract pinned by the parity test and mirrored on the frontend.
GUARD_MESSAGES: dict[str, str] = {
    "stale_base_revision": (
        "The paper changed after this suggestion was prepared. Please ask again."
    ),
    "proposal_too_large": "This suggestion is too large to apply safely.",
    "unsupported_operation": (
        "I can only update existing fields, not add, remove, or move parts of the "
        "paper."
    ),
    "unknown_target": (
        "This suggestion points at a part of the paper that no longer exists."
    ),
    "forbidden_question_text": "I can't rewrite sourced question text.",
    "forbidden_question_source": "I can't change question-bank source data.",
    "forbidden_question_swap": ("I can't change which question fills a slot here."),
    "forbidden_question_count": "I can't add or remove questions.",
    "forbidden_section_membership": (
        "I can't change which questions belong to a section."
    ),
    "forbidden_raw_content": (
        "I can only set plain text or a number here, not raw editor content."
    ),
    "forbidden_value_type": "That value isn't the right type for this field.",
    "forbidden_path": "I can't change that part of the paper.",
}

# Deny-by-default allowlist. A patch is allowed only if its path fully matches one
# of these AND the captured ids resolve in the live document AND its value is the
# expected scalar type. Each entry is ``(pattern, id_kinds, value_kind)``:
# ``id_kinds`` names the ids the resolver must confirm exist (the "missing ids"
# guard) — block kinds are collection-specific so a chrome path can't resolve an
# instruction block (or vice versa); ``value_kind`` is ``"text"`` or ``"number"``
# so a string can't land on a numeric field (e.g. slot marks).
_FORMAT_LAYOUT_ROLES = "marks|questionNumbers|mcqOptions|instructions|masthead|footer"
ALLOWED_PATH_PATTERNS: tuple[tuple[re.Pattern[str], tuple[str, ...], str], ...] = (
    (re.compile(r"^/paper/title$"), (), "text"),
    (re.compile(r"^/paper/subtitle$"), (), "text"),
    (
        re.compile(r"^/paper/chromeBlocks/(?P<blockId>[^/]+)/text$"),
        ("chromeBlockId",),
        "text",
    ),
    (
        re.compile(r"^/paper/instructionBlocks/(?P<blockId>[^/]+)/text$"),
        ("instructionBlockId",),
        "text",
    ),
    (
        re.compile(r"^/paper/sections/(?P<sectionId>[^/]+)/title$"),
        ("sectionId",),
        "text",
    ),
    (
        re.compile(r"^/paper/sections/(?P<sectionId>[^/]+)/subtitle$"),
        ("sectionId",),
        "text",
    ),
    (
        re.compile(r"^/paper/sections/(?P<sectionId>[^/]+)/instructions$"),
        ("sectionId",),
        "text",
    ),
    (
        re.compile(
            r"^/paper/sections/(?P<sectionId>[^/]+)/slots/(?P<slotId>[^/]+)/marks$"
        ),
        ("sectionId", "slotId"),
        "number",
    ),
    (re.compile(r"^/format/page/(size|orientation)$"), (), "text"),
    (re.compile(rf"^/format/layout/(?:{_FORMAT_LAYOUT_ROLES})$"), (), "text"),
)

# Resolves a block id against the one collection its path names, keyed by id kind.
_BLOCK_COLLECTION = {
    "chromeBlockId": "chromeBlocks",
    "instructionBlockId": "instructionBlocks",
}

# A marks edit is allowed; this matches it so the warning pass can recompute
# totals without re-running the full classifier.
_MARKS_PATH = re.compile(
    r"^/paper/sections/(?P<sectionId>[^/]+)/slots/(?P<slotId>[^/]+)/marks$"
)


def _segments(path: str) -> list[str]:
    """Split a JSON Pointer into decoded segments (RFC 6901)."""
    if not path.startswith("/"):
        return [path]
    return [seg.replace("~1", "/").replace("~0", "~") for seg in path[1:].split("/")]


def _is_scalar(value: Any) -> bool:
    # bool is an int subclass and is fine; dict/list/None are not — a structured
    # value at a text/number field is the "raw BlockNote JSON" the model must not
    # smuggle in.
    return isinstance(value, (str, int, float, bool))


def _value_matches_kind(value: Any, value_kind: str) -> bool:
    """Confirm a scalar value is the type the field expects.

    ``number`` rejects ``bool`` (a ``True`` marks value is a type confusion, not a
    quantity); ``text`` requires a string so a bare number can't land on a label.
    """
    if value_kind == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, str)


def _find_by_id(items: Any, target_id: str) -> dict | None:
    if not isinstance(items, list):
        return None
    return next(
        (
            item
            for item in items
            if isinstance(item, dict) and item.get("id") == target_id
        ),
        None,
    )


def _target_exists(document: dict, kind: str, captured: dict[str, str]) -> bool:
    """Confirm a captured id resolves to a node in the live document."""
    paper = document.get("paper", {}) if isinstance(document, dict) else {}
    if kind in _BLOCK_COLLECTION:
        collection = paper.get(_BLOCK_COLLECTION[kind])
        return _find_by_id(collection, captured["blockId"]) is not None
    section = _find_by_id(paper.get("sections"), captured["sectionId"])
    if section is None:
        return False
    if kind == "sectionId":
        return True
    # kind == "slotId": the slot must live in *that* section (membership matters).
    return _find_by_id(section.get("slots"), captured["slotId"]) is not None


def _classify_patch(document: dict, patch: EditPatch) -> str | None:
    """Return the guard id a patch breaks, or ``None`` if it is allowed.

    Order matters: operation first, then the deny-by-default allowlist, then —
    only for paths outside the allowlist — the named forbidden classifiers that
    give the rejection a specific, user-safe message.
    """
    if patch.op != ALLOWED_OP:
        return "unsupported_operation"

    for pattern, id_kinds, value_kind in ALLOWED_PATH_PATTERNS:
        match = pattern.match(patch.path)
        if match is None:
            continue
        captured = match.groupdict()
        for kind in id_kinds:
            if not _target_exists(document, kind, captured):
                return "unknown_target"
        if not _is_scalar(patch.value):
            return "forbidden_raw_content"
        if not _value_matches_kind(patch.value, value_kind):
            return "forbidden_value_type"
        return None

    return _forbidden_guard(patch.path)


def _forbidden_guard(path: str) -> str:
    """Pick the most specific guard for a path outside the allowlist."""
    segs = _segments(path)
    if segs and segs[0] == "questions":
        if "source" in segs or "metadata" in segs:
            return "forbidden_question_source"
        return "forbidden_question_text"
    if segs[:1] == ["paper"] and "sections" in segs:
        if segs[-1] in ("selectedQuestionId", "alternateQuestionIds"):
            return "forbidden_question_swap"
        # A whole-slot or slots-collection target adds/removes questions; a
        # whole-section or sections-collection target re-homes them.
        if segs[-1] == "slots" or (len(segs) >= 5 and segs[-2] == "slots"):
            return "forbidden_question_count"
        if segs[-1] == "sections" or (len(segs) == 3 and segs[-2] == "sections"):
            return "forbidden_section_membership"
    return "forbidden_path"


def _marks_warnings(document: dict, patches: list[EditPatch]) -> list[str]:
    """Surface a total-marks recompute for every *valid* marks patch.

    Marks edits are allowed, but the model's arithmetic is never trusted: we read
    the live slot marks, apply the deltas the (already-validated) patches imply,
    and warn when the paper total moves. The reducer performs the real recompute.
    """
    paper = document.get("paper", {}) if isinstance(document, dict) else {}
    slot_marks: dict[str, float] = {}
    for section in paper.get("sections", []):
        for slot in section.get("slots", []):
            if isinstance(slot, dict) and "id" in slot:
                slot_marks[slot["id"]] = slot.get("marks", 0) or 0

    old_total = sum(slot_marks.values())
    new_marks = dict(slot_marks)
    touched = False
    for patch in patches:
        match = _MARKS_PATH.match(patch.path)
        if match is None or not isinstance(patch.value, (int, float)):
            continue
        slot_id = match.group("slotId")
        if slot_id in new_marks:
            new_marks[slot_id] = patch.value
            touched = True

    new_total = sum(new_marks.values())
    if touched and new_total != old_total:
        return [f"Total marks changed from {_fmt(old_total)} to {_fmt(new_total)}."]
    return []


def _fmt(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


def validate_proposal(
    document: dict,
    proposal: EditProposal,
    *,
    base_revision: int,
    current_revision: int,
) -> dict:
    """Run the deterministic guardrails over a parsed proposal.

    Returns ``{"blocking": [...], "warnings": [...]}``. ``blocking`` entries are
    ``{"guardId", "message", "path"}`` (path omitted for proposal-wide guards).
    A non-empty ``blocking`` list means the frontend must keep Apply disabled.
    """
    blocking: list[dict] = []
    seen: set[tuple[str, str | None]] = set()

    def add(guard_id: str, path: str | None = None) -> None:
        key = (guard_id, path)
        if key in seen:
            return
        seen.add(key)
        entry = {"guardId": guard_id, "message": GUARD_MESSAGES[guard_id]}
        if path is not None:
            entry["path"] = path
        blocking.append(entry)

    if base_revision != current_revision:
        add("stale_base_revision")

    total_value_chars = sum(
        len(str(patch.value)) for patch in proposal.patches if patch.value is not None
    )
    if len(proposal.patches) > MAX_PATCHES or total_value_chars > MAX_VALUE_CHARS:
        add("proposal_too_large")

    for patch in proposal.patches:
        guard_id = _classify_patch(document, patch)
        if guard_id is not None:
            add(guard_id, patch.path)

    # Warnings only describe an otherwise-valid proposal; a blocked proposal will
    # not apply, so recompute noise would be misleading.
    warnings = [] if blocking else _marks_warnings(document, proposal.patches)
    return {"blocking": blocking, "warnings": warnings}


def build_refusal(message: str, broken_guards: list[str]) -> dict:
    """Shape a guardrail-refusal response (PRD #30 ``status: "refused"``)."""
    return {
        "status": "refused",
        "message": message,
        "brokenGuards": broken_guards,
    }
