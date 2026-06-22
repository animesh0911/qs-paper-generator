"""Semantic citation-support review for generated Question candidates.

This module is a deterministic pre-review aid, not a proof of truth. It checks
whether cited NCERT excerpts contain lexical evidence for the generated question
and answer, and flags generation shapes that need human review before issue #177
can treat a candidate as accepted.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

__all__ = [
    "CitationSupportIssue",
    "CitationSupportReview",
    "review_candidate_citation_support",
]

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9\-]*")
_FORMULA_OR_DIAGRAM_TERMS = frozenset(
    {
        "draw",
        "drawing",
        "electron-dot",
        "electron",
        "dot",
        "formula",
        "formulas",
        "structure",
        "structures",
        "structural",
        "iupac",
        "nomenclature",
        "name",
        "naming",
    }
)
_STOPWORDS = frozenset(
    {
        "a",
        "about",
        "according",
        "an",
        "and",
        "are",
        "as",
        "be",
        "because",
        "between",
        "by",
        "can",
        "class",
        "compared",
        "compound",
        "compounds",
        "describe",
        "discuss",
        "does",
        "each",
        "explain",
        "for",
        "from",
        "give",
        "has",
        "have",
        "how",
        "in",
        "is",
        "it",
        "its",
        "list",
        "many",
        "more",
        "of",
        "on",
        "or",
        "outline",
        "question",
        "state",
        "than",
        "that",
        "the",
        "their",
        "these",
        "this",
        "to",
        "used",
        "what",
        "when",
        "where",
        "which",
        "why",
        "with",
    }
)


@dataclass(frozen=True)
class CitationSupportIssue:
    """One review finding for a candidate's cited support."""

    field: str
    code: str
    detail: str


@dataclass(frozen=True)
class CitationSupportReview:
    """Citation-support review result for one generated candidate."""

    question_supported: bool
    answer_supported: bool
    issues: tuple[CitationSupportIssue, ...]

    @property
    def supported(self) -> bool:
        """Whether both question and answer pass this deterministic screen."""
        return self.question_supported and self.answer_supported and not self.issues


def review_candidate_citation_support(
    candidate: dict[str, Any],
    grounding_manifest: dict[str, Any],
    *,
    min_overlap: float = 0.35,
) -> CitationSupportReview:
    """Check whether cited excerpts appear to support a generated candidate.

    This is intentionally conservative and lexical. It catches obvious
    hallucinated/unsupported citations and policy-risky formula/diagram prompts;
    teacher or stronger semantic review still owns final acceptance.
    """
    excerpt_text_by_id = _excerpt_text_by_id(grounding_manifest)
    issues: list[CitationSupportIssue] = []
    question_text = _candidate_question_text(candidate)
    answer_text = _candidate_answer_text(candidate)

    question_supported = _review_field(
        field="question",
        text=question_text,
        citation_ids=candidate.get("question_citation_ids"),
        excerpt_text_by_id=excerpt_text_by_id,
        issues=issues,
        min_overlap=min_overlap,
    )
    answer_supported = _review_field(
        field="answer",
        text=answer_text,
        citation_ids=candidate.get("answer_citation_ids"),
        excerpt_text_by_id=excerpt_text_by_id,
        issues=issues,
        min_overlap=min_overlap,
    )

    risky_terms = sorted(_tokens(question_text) & _FORMULA_OR_DIAGRAM_TERMS)
    if risky_terms:
        issues.append(
            CitationSupportIssue(
                "question",
                "formula_or_diagram_review_required",
                ", ".join(risky_terms),
            )
        )

    return CitationSupportReview(
        question_supported=question_supported,
        answer_supported=answer_supported,
        issues=tuple(issues),
    )


def _review_field(
    *,
    field: str,
    text: str,
    citation_ids: Any,
    excerpt_text_by_id: dict[str, str],
    issues: list[CitationSupportIssue],
    min_overlap: float,
) -> bool:
    cited_text = _cited_text(citation_ids, excerpt_text_by_id)
    if not cited_text:
        issues.append(CitationSupportIssue(field, "missing_cited_text", field))
        return False

    text_tokens = _meaningful_tokens(text)
    if not text_tokens:
        issues.append(CitationSupportIssue(field, "empty_review_text", field))
        return False

    cited_tokens = _meaningful_tokens(cited_text)
    overlap = text_tokens & cited_tokens
    ratio = len(overlap) / len(text_tokens)
    if ratio < min_overlap:
        missing = ", ".join(sorted(text_tokens - overlap)[:8])
        issues.append(
            CitationSupportIssue(
                field,
                "low_lexical_citation_overlap",
                f"{ratio:.2f} overlap; missing: {missing}",
            )
        )
        return False
    return True


def _excerpt_text_by_id(grounding_manifest: dict[str, Any]) -> dict[str, str]:
    excerpts = grounding_manifest.get("excerpts", [])
    return {
        excerpt["citation_id"]: str(excerpt.get("text", ""))
        for excerpt in excerpts
        if isinstance(excerpt, dict) and isinstance(excerpt.get("citation_id"), str)
    }


def _cited_text(citation_ids: Any, excerpt_text_by_id: dict[str, str]) -> str:
    if not isinstance(citation_ids, Iterable) or isinstance(citation_ids, str):
        return ""
    return "\n".join(
        excerpt_text_by_id.get(citation_id, "")
        for citation_id in citation_ids
        if isinstance(citation_id, str)
    ).strip()


def _candidate_question_text(candidate: dict[str, Any]) -> str:
    raw_text = str(candidate.get("raw_text") or "")
    stem_text = _blocks_text(candidate.get("content", {}).get("stem"))
    return "\n".join(part for part in (raw_text, stem_text) if part).strip()


def _candidate_answer_text(candidate: dict[str, Any]) -> str:
    answer = str(candidate.get("answer") or "").strip()
    options = candidate.get("content", {}).get("options")
    option_text = _answer_option_text(answer, options)
    return "\n".join(part for part in (answer, option_text) if part).strip()


def _answer_option_text(answer: str, options: Any) -> str:
    if not answer or not isinstance(options, list):
        return ""
    normalized_answer = answer.casefold().strip()
    for option in options:
        if not isinstance(option, dict):
            continue
        label = str(option.get("label") or "").casefold().strip()
        text = _blocks_text(option.get("content"))
        if label and normalized_answer in {label, f"option {label}"}:
            return text
        if text and text.casefold() in normalized_answer:
            return text
    return ""


def _blocks_text(blocks: Any) -> str:
    if not isinstance(blocks, list):
        return ""
    return " ".join(
        block.get("text", "")
        for block in blocks
        if isinstance(block, dict) and isinstance(block.get("text"), str)
    ).strip()


def _meaningful_tokens(text: str) -> set[str]:
    return {
        token for token in _tokens(text) if token not in _STOPWORDS and len(token) > 2
    }


def _tokens(text: str) -> set[str]:
    return {match.group(0).casefold() for match in _TOKEN_RE.finditer(text)}
