"""Tests for bank.guardrails — the deterministic Layer-2 ingest safety net.

The resolver and gate are pure (no DB): the canonical slug set and the question
dicts are passed in, so these run without ``django_db``. WHY each case matters is
in its docstring — the point is generality (match *toward* the taxonomy, flag the
rest) where the deleted ``fix_parsed.py`` was an overfitted blacklist.
"""

from __future__ import annotations

from bank.guardrails import (
    FLAG_BLUEPRINT_DRIFT,
    FLAG_EMPTY_STEM,
    FLAG_MARKS_SECTION_MISMATCH,
    FLAG_MCQ_TOO_FEW_OPTIONS,
    FLAG_POSSIBLE_SPLIT,
    apply_guardrails,
    resolve_chapter_slug,
)

# The seeded 13-slug taxonomy (migration 0003) — inlined so the test is
# self-contained and not coupled to the DB or untracked fixture dirs.
CANONICAL = {
    "acids-bases-and-salts",
    "carbon-and-its-compounds",
    "chemical-reactions-and-equations",
    "control-and-coordination",
    "electricity",
    "heredity",
    "how-do-organisms-reproduce",
    "human-eye-and-the-colourful-world",
    "life-processes",
    "light-reflection-and-refraction",
    "magnetic-effects-of-electric-current",
    "metals-and-non-metals",
    "our-environment",
}

# Every bad variant the 2026 audit observed (the deleted fix_parsed SLUG_FIX
# corpus) → the canonical it must resolve to. The resolver must map ALL of these
# without a hardcoded table.
KNOWN_VARIANTS = {
    "acids-bases-salts": "acids-bases-and-salts",
    "acids_bases_and_salts": "acids-bases-and-salts",
    "carbon_and_its_compounds": "carbon-and-its-compounds",
    "chemical_reactions_and_equations": "chemical-reactions-and-equations",
    "heredity-and-evolution": "heredity",
    "human-eye-and-colorful-world": "human-eye-and-the-colourful-world",
    "human-eye-and-colourful-world": "human-eye-and-the-colourful-world",
    "light_reflection_and_refraction": "light-reflection-and-refraction",
    "metals_and_non_metals": "metals-and-non-metals",
    "the-human-eye-and-the-colorful-world": "human-eye-and-the-colourful-world",
    "the-human-eye-and-the-colourful-world": "human-eye-and-the-colourful-world",
}


def _q(section="C", qtype="short_answer", marks=3, text="Define refraction.", **extra):
    base = {
        "section": section,
        "qtype": qtype,
        "marks": marks,
        "text": text,
        "options": [],
        "content": {},
        "chapter_slug": "light-reflection-and-refraction",
        "parse_quality": "clean",
    }
    base.update(extra)
    return base


# ---------------------------------------------------------------------------
# Chapter resolver
# ---------------------------------------------------------------------------


def test_resolver_maps_every_known_audit_variant():
    """All real bad slugs from the audit snap to the right canonical — no table."""
    for variant, expected in KNOWN_VARIANTS.items():
        slug, matched = resolve_chapter_slug(variant, CANONICAL)
        assert (slug, matched) == (expected, True), variant


def test_resolver_generalises_to_unseen_variant():
    """A variant never seen in the audit (the whole point vs a blacklist) resolves."""
    assert resolve_chapter_slug("heredity_&_evolution", CANONICAL) == ("heredity", True)
    assert resolve_chapter_slug("Metals And Non Metals", CANONICAL) == (
        "metals-and-non-metals",
        True,
    )


def test_resolver_flags_unmappable_slug():
    """Something genuinely off-taxonomy is left null + flagged, never force-matched."""
    assert resolve_chapter_slug("genetics", CANONICAL) == (None, False)
    assert resolve_chapter_slug("", CANONICAL) == (None, False)
    assert resolve_chapter_slug(None, CANONICAL) == (None, False)


def test_resolver_passes_canonical_through_unchanged():
    """A slug already canonical stays itself (exact path), matched True."""
    assert resolve_chapter_slug("electricity", CANONICAL) == ("electricity", True)


# ---------------------------------------------------------------------------
# Structural gate
# ---------------------------------------------------------------------------


def test_gate_derives_options_from_content_options():
    """An MCQ with an empty flat options[] is backfilled from content.options.

    Why: the renderer reads content.options but de-dup/admin read the flat list;
    the empty-flat-list inconsistency (#108) must not persist."""
    q = _q(
        section="A",
        qtype="mcq",
        marks=1,
        options=[],
        content={"options": [{"label": "A", "content": [{"text": "Oxygen"}]}]},
    )
    apply_guardrails([q], CANONICAL)
    assert q["options"] == [{"label": "A", "text": "Oxygen"}]


def test_gate_flags_marks_section_mismatch_and_downgrades():
    """A 3-mark question tagged section A (should be C) is flagged + partial.

    Why: marks deterministically map to a section (MARKS_TO_SECTION); a mismatch
    is a tagging defect that must surface, not silently persist as clean."""
    q = _q(section="A", marks=3)  # 3 marks → section C, not A
    apply_guardrails([q], CANONICAL)
    assert FLAG_MARKS_SECTION_MISMATCH in q["review_flags"]
    assert q["parse_quality"] == "partial"


def test_gate_flags_mcq_with_too_few_options():
    q = _q(section="A", qtype="mcq", marks=1, options=[{"label": "A", "text": "x"}])
    apply_guardrails([q], CANONICAL)
    assert FLAG_MCQ_TOO_FEW_OPTIONS in q["review_flags"]


def test_gate_flags_lost_or_continued_stem():
    """A bare question number (#108 lost stem) → empty_stem/broken; a 'continued'
    placeholder → possible_split. Both route to review instead of passing."""
    lost = _q(text="37.")
    apply_guardrails([lost], CANONICAL)
    assert FLAG_EMPTY_STEM in lost["review_flags"]
    assert lost["parse_quality"] == "broken"

    cont = _q(text="This question is continued on the next page")
    apply_guardrails([cont], CANONICAL)
    assert FLAG_POSSIBLE_SPLIT in cont["review_flags"]


def test_gate_flags_blueprint_drift_only_for_board_sized_batch():
    """A 40-question board-paper-shaped batch that drifts from 39 flags every row;
    a teacher's 5-question worksheet (sub-board size) is left clean.

    Why: the blueprint (20/6/7/3/3 = 39) only describes a full board paper — the
    #104 teacher-upload path accepts arbitrary worksheets that must not be flagged."""
    board = [
        _q(
            section="A",
            qtype="mcq",
            marks=1,
            options=[{"label": "A", "text": "x"}, {"label": "B", "text": "y"}],
        )
        for _ in range(40)
    ]
    apply_guardrails(board, CANONICAL)
    assert all(FLAG_BLUEPRINT_DRIFT in q["review_flags"] for q in board)

    worksheet = [_q(section="C", marks=3) for _ in range(5)]
    apply_guardrails(worksheet, CANONICAL)
    assert all(q["review_flags"] == [] for q in worksheet)


def test_gate_leaves_clean_question_untouched():
    """A well-formed, correctly-tagged question gets no flags, no downgrade."""
    q = _q(section="C", qtype="short_answer", marks=3)
    apply_guardrails([q], CANONICAL)
    assert q["review_flags"] == []
    assert q["parse_quality"] == "clean"
    assert q["chapter_slug"] == "light-reflection-and-refraction"
