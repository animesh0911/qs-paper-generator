"""Deterministic ingest guardrails — resolve toward the taxonomy, flag the rest.

The Layer-2 safety net behind the Layer-1 schema constraint (``build_question_schema``
in ``bank.ingestor``). Where Layer 1 stops a live Gemini extraction from *emitting*
a non-canonical ``chapter_slug``, this module is the **general, deterministic**
backstop that runs on **every** ingest — both the live ``Ingestor.ingest`` path
and the committed-JSON ``load_questions`` path (which carries pre-Layer-1 data) —
so a bad value is never silently persisted.

It replaces two overfitted one-off scripts (``fix_parsed.py``'s hardcoded
bad-slug→good-slug table and ``validate_tags.py``'s throwaway checks): instead of
blacklisting the exact strings seen in one batch, ``resolve_chapter_slug`` matches
*toward* the closed 13-slug taxonomy (so it generalises to unseen variants), and
``apply_guardrails`` promotes the structural checks into a gate that records
``review_flags`` and downgrades ``parse_quality`` rather than accepting silently.

Patterns / invariants:
- Mutates the question dicts in place; call it after ``parse_quality`` is set and
  before de-duplication, on the full per-paper batch (blueprint needs the batch).
- Never *upgrades* ``parse_quality`` — flags only drag it down.
- Imports ``MARKS_TO_SECTION`` from ``bank.ingestor`` at module top; ``ingestor``
  imports this module *lazily* (inside ``ingest``) to keep the dependency acyclic.

Where it fits:
- Called by: ``bank.ingestor.Ingestor.ingest`` and the ``load_questions`` command
- Persisted via: ``Question.review_flags`` (set in ``Ingestor._persist``)
"""

from __future__ import annotations

import difflib
import re
from collections import Counter

from . import content as content_mod
from .ingestor import MARKS_TO_SECTION
from .models import QuestionType, Section

# ---------------------------------------------------------------------------
# review_flag reason codes (one queryable vocabulary for the review queue)
# ---------------------------------------------------------------------------

FLAG_CHAPTER_UNRESOLVED = "chapter_unresolved"
FLAG_MARKS_SECTION_MISMATCH = "marks_section_mismatch"
FLAG_BAD_MARKS = "bad_marks"
FLAG_BAD_SECTION = "bad_section"
FLAG_BAD_QTYPE = "bad_qtype"
FLAG_MCQ_TOO_FEW_OPTIONS = "mcq_too_few_options"
FLAG_POSSIBLE_SPLIT = "possible_split"
FLAG_EMPTY_STEM = "empty_stem"
FLAG_BLUEPRINT_DRIFT = "blueprint_count_drift"

# A structurally unusable row → broken; a mis-tagged-but-renderable row → partial.
# blueprint drift is informational (paper-level) and downgrades nothing.
_SEVERE_FLAGS = frozenset({FLAG_BAD_SECTION, FLAG_BAD_QTYPE, FLAG_EMPTY_STEM})
_PARTIAL_FLAGS = frozenset(
    {
        FLAG_CHAPTER_UNRESOLVED,
        FLAG_MARKS_SECTION_MISMATCH,
        FLAG_BAD_MARKS,
        FLAG_MCQ_TOO_FEW_OPTIONS,
        FLAG_POSSIBLE_SPLIT,
    }
)
_QUALITY_RANK = {"broken": 0, "partial": 1, "clean": 2}
_RANK_QUALITY = {v: k for k, v in _QUALITY_RANK.items()}

# CBSE Cl.10 Science board blueprint — only applied to a full-paper-sized batch
# (a teacher's short worksheet upload, #104, must not be flagged for "drift").
_BOARD_PAPER_MIN = 30
_BLUEPRINT_TOTAL = 39
_BLUEPRINT_SECTIONS = {"A": 20, "B": 6, "C": 7, "D": 3, "E": 3}

# ---------------------------------------------------------------------------
# Chapter resolver — match an emitted slug toward the closed taxonomy
# ---------------------------------------------------------------------------

_FUZZY_THRESHOLD = 0.82
# Connective words that vary between emitted and canonical slugs; dropping them
# from both sides makes the comparison robust (e.g. "acids-bases-salts" vs the
# canonical "acids-bases-and-salts"). Distinctive words (its/how/do/our/non) stay.
_FILLER_TOKENS = frozenset({"and", "the", "of"})
_SPLIT_RE = re.compile(r"[-_\s]+")


def _tokens(slug: str) -> list[str]:
    """Normalise a slug to its distinctive token list (lowercase, filler dropped)."""
    cleaned = re.sub(r"[^a-z0-9\-_ ]", "", slug.strip().lower())
    return [t for t in _SPLIT_RE.split(cleaned) if t and t not in _FILLER_TOKENS]


def resolve_chapter_slug(emitted, canonical) -> tuple[str | None, bool]:
    """Snap an emitted ``chapter_slug`` to the nearest canonical slug, or flag it.

    Returns ``(canonical_slug, True)`` on a confident match, else ``(None, False)``.
    Three escalating strategies, all matching *toward* ``canonical`` (so an unseen
    bad variant still resolves, unlike a hardcoded blacklist):

    1. exact match on the filler-stripped token form (handles `_`↔`-`, dropped
       `and`/`the`, leading `the-`);
    2. canonical token-set ⊆ emitted token-set, most specific wins (handles
       ``heredity-and-evolution`` → ``heredity``);
    3. fuzzy ratio ≥ threshold (handles spelling, ``colorful`` → ``colourful``).
    """
    if not emitted or not isinstance(emitted, str):
        return None, False
    emitted_tokens = _tokens(emitted)
    if not emitted_tokens:
        return None, False
    emitted_form = "-".join(emitted_tokens)
    emitted_set = set(emitted_tokens)

    canon_tokens = {c: _tokens(c) for c in canonical}

    # 1. exact (filler-stripped) form
    for c, toks in canon_tokens.items():
        if toks and "-".join(toks) == emitted_form:
            return c, True

    # 2. canonical-token-subset → most specific (most tokens) canonical
    subset = [
        c for c, toks in canon_tokens.items() if toks and set(toks) <= emitted_set
    ]
    if subset:
        return max(subset, key=lambda c: len(canon_tokens[c])), True

    # 3. fuzzy on the filler-stripped form
    best, best_ratio = None, 0.0
    for c, toks in canon_tokens.items():
        ratio = difflib.SequenceMatcher(None, emitted_form, "-".join(toks)).ratio()
        if ratio > best_ratio:
            best, best_ratio = c, ratio
    if best is not None and best_ratio >= _FUZZY_THRESHOLD:
        return best, True

    return None, False


# ---------------------------------------------------------------------------
# Structural gate
# ---------------------------------------------------------------------------

_BARE_NUMBER_RE = re.compile(r"^\s*\d{1,3}[.):]?\s*$")
_CONTINUATION_RE = re.compile(r"continued\s+(?:on|from)\b", re.I)
# A stem that *begins* at a non-first sub-part label — "(b)", "(c)", … (never
# "(a)" or roman "(i)") — is an orphaned OR/sub-part half the model split into
# its own entry. This is the residual segmentation defect the no-split prompt
# doesn't fully prevent (validated on 31-2-3: the 4 spurious rows all start
# "(b)"); flagging it names the specific rows, not just the paper-level drift.
_ORPHAN_LABEL_RE = re.compile(r"^\s*\(\s*([b-z])\s*\)", re.IGNORECASE)


def _derive_options(content: dict) -> list[dict]:
    """Flatten ``content.options`` into the top-level ``[{label, text}]`` mirror.

    The one *general* transform kept from ``fix_parsed.py``: the renderer reads
    ``content.options``, but the flat ``options`` list is the de-dup/admin shape,
    so a fully-formed MCQ should never have an empty flat list.
    """
    opts = content.get("options")
    if not isinstance(opts, list):
        return []
    return [
        {
            "label": o.get("label", ""),
            "text": content_mod.flatten_text(o.get("content")),
        }
        for o in opts
        if isinstance(o, dict)
    ]


def _stem_flag(text) -> str | None:
    """Flag a lost/continued/split stem.

    ``empty_stem`` for an empty stem or a bare question number ("37."); otherwise
    ``possible_split`` for a "continued on/from" placeholder or a stem that begins
    at an orphaned non-first sub-part label ("(b) …") — the OR-half segmentation
    defect. Returns ``None`` for a normal stem (incl. a legitimate "(a) …" first
    part and roman "(i)").
    """
    stripped = (text or "").strip()
    if not stripped or _BARE_NUMBER_RE.match(stripped):
        return FLAG_EMPTY_STEM
    if _CONTINUATION_RE.search(stripped):
        return FLAG_POSSIBLE_SPLIT
    orphan = _ORPHAN_LABEL_RE.match(stripped)
    if orphan and orphan.group(1).lower() != "i":
        return FLAG_POSSIBLE_SPLIT
    return None


def _downgrade(current: str, flags: list[str]) -> str:
    """Drag ``parse_quality`` down to match the worst flag — never upgrade."""
    rank = _QUALITY_RANK.get(current, _QUALITY_RANK["partial"])
    for flag in flags:
        if flag in _SEVERE_FLAGS:
            rank = min(rank, _QUALITY_RANK["broken"])
        elif flag in _PARTIAL_FLAGS:
            rank = min(rank, _QUALITY_RANK["partial"])
    return _RANK_QUALITY[rank]


def apply_guardrails(questions: list[dict], canonical_slugs) -> None:
    """Resolve chapters, derive options, and flag structural defects in place.

    For each question: snap ``chapter_slug`` toward the taxonomy (or flag
    ``chapter_unresolved``), backfill ``options`` from ``content.options``, and
    record ``review_flags`` for marks/section, enum, MCQ-option, and split
    defects — downgrading ``parse_quality`` accordingly. Then, only for a
    board-paper-sized batch, flag every row if the section histogram drifts from
    the 39-question blueprint.
    """
    canonical_slugs = set(canonical_slugs)
    valid_sections = set(Section.values)
    valid_qtypes = set(QuestionType.values)
    section_hist: Counter = Counter()

    for q in questions:
        flags: list[str] = []

        slug, matched = resolve_chapter_slug(q.get("chapter_slug"), canonical_slugs)
        q["chapter_slug"] = slug
        if not matched:
            flags.append(FLAG_CHAPTER_UNRESOLVED)

        if not q.get("options"):
            derived = _derive_options(q.get("content") or {})
            if derived:
                q["options"] = derived

        section = q.get("section")
        section_hist[section] += 1
        if section not in valid_sections:
            flags.append(FLAG_BAD_SECTION)
        if q.get("qtype") not in valid_qtypes:
            flags.append(FLAG_BAD_QTYPE)

        marks = q.get("marks")
        if marks not in MARKS_TO_SECTION:
            flags.append(FLAG_BAD_MARKS)
        elif MARKS_TO_SECTION[marks] != section:
            flags.append(FLAG_MARKS_SECTION_MISMATCH)

        if q.get("qtype") == "mcq" and len(q.get("options") or []) < 2:
            flags.append(FLAG_MCQ_TOO_FEW_OPTIONS)

        stem_flag = _stem_flag(q.get("text"))
        if stem_flag:
            flags.append(stem_flag)

        q["review_flags"] = flags
        if flags:
            q["parse_quality"] = _downgrade(q.get("parse_quality", "partial"), flags)

    # Per-paper blueprint — only for a full-paper-sized batch (not a worksheet).
    if len(questions) >= _BOARD_PAPER_MIN:
        drift = len(questions) != _BLUEPRINT_TOTAL or any(
            section_hist.get(s, 0) != n for s, n in _BLUEPRINT_SECTIONS.items()
        )
        if drift:
            for q in questions:
                if FLAG_BLUEPRINT_DRIFT not in q["review_flags"]:
                    q["review_flags"].append(FLAG_BLUEPRINT_DRIFT)
