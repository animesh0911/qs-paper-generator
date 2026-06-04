"""Per-**QuestionType** structure spec — the single source for the regions a qtype uses.

Three layers used to encode "what regions does an ``assertion_reason`` (or
``case_based``, ``mcq`` …) question have?" independently and silently: the
Gemini response schema in ``bank.ingestor``, the ``parse_quality``
self-assessment, and ``PaperDocumentBuilder``'s empty-content fallback. The same
class of drift ADR-0001 closed for the qtype *value* was still open for the
*shape* behind it.

``QUESTION_SHAPES`` is now that single declaration:
- ``compute_parse_quality`` (the picker-gate assessment) lives here, beside the
  table, so the qtype→structure knowledge is in one file (locality).
- ``PaperDocumentBuilder`` reads ``fallback_regions`` to synthesise content for
  legacy rows with an empty ``content`` map.
- A test in ``bank.tests`` asserts the hand-written response schema covers every
  shape's ``content_regions``, keeping the three in lockstep.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QuestionShape:
    """The structured-content footprint of one QuestionType.

    ``content_regions`` are the Content regions the qtype legitimately populates
    (used to validate the response schema covers them). ``fallback_regions`` are
    the regions ``PaperDocumentBuilder`` synthesises when a row carries no
    structured content — a strict subset of ``content_regions``.
    """

    qtype: str
    content_regions: tuple[str, ...] = ("stem",)
    fallback_regions: tuple[str, ...] = ("stem",)


QUESTION_SHAPES: dict[str, QuestionShape] = {
    "mcq": QuestionShape(
        "mcq", content_regions=("stem", "options"), fallback_regions=("stem", "options")
    ),
    "assertion_reason": QuestionShape(
        "assertion_reason", content_regions=("stem", "assertion", "reason")
    ),
    "very_short_answer": QuestionShape("very_short_answer"),
    "short_answer": QuestionShape("short_answer"),
    "long_answer": QuestionShape("long_answer"),
    "case_based": QuestionShape(
        "case_based", content_regions=("stem", "passage", "subparts")
    ),
    "internal_choice": QuestionShape(
        "internal_choice", content_regions=("stem", "choices")
    ),
}


def fallback_regions(qtype: str) -> tuple[str, ...]:
    """Regions ``PaperDocumentBuilder`` synthesises for an empty-content ``qtype``."""
    shape = QUESTION_SHAPES.get(qtype)
    return shape.fallback_regions if shape else ("stem",)


def compute_parse_quality(raw_question: dict, classified_qtype: str) -> str:
    """Return clean/partial/broken from how well structure matches the qtype.

    A plain structural self-assessment (ADR-0004): the picker draws from
    clean+partial and excludes broken. No verification against source text. The
    count thresholds (4 options, ≥2 subparts, a 2-option internal choice) are the
    crux of clean-vs-partial-vs-broken and stay as explicit code rather than data.
    """
    text = raw_question.get("text", "") or ""
    content = raw_question.get("content", {}) or {}

    if classified_qtype == "assertion_reason":
        if content.get("assertion") and content.get("reason"):
            return "clean"
        return "broken"

    if classified_qtype == "case_based":
        if content.get("passage") and len(content.get("subparts", [])) >= 2:
            return "clean"
        return "partial"

    if classified_qtype == "internal_choice":
        choices = content.get("choices", [])
        if choices and len(choices[0].get("options", [])) == 2:
            return "clean"
        return "broken"

    if classified_qtype == "mcq":
        options = raw_question.get("options", [])
        if not options:
            # The flat ``options`` list is optional; the model often emits the
            # choices only under ``content.options`` (the contract source the
            # renderer actually reads). Count those so a fully-formed MCQ isn't
            # falsely marked broken just because the flat mirror is empty.
            options = content.get("options", [])
        if len(options) == 4:
            return "clean"
        return "partial" if options else "broken"

    # short_answer, long_answer, very_short_answer
    if text.strip():
        return "clean"
    return "broken"
