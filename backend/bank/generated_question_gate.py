"""Deterministic gate for generated Question payloads.

This module owns the generated Question validation seam used after model output
and before future candidate persistence. It depends only on the bank model
enums and request-shaped input, while ``bank.generation`` owns prompt rendering
and the LangChain adapter.

Patterns / invariants:
- Model output is untrusted until this module accepts it.
- Generated payloads contain Question data only; workflow state belongs to the
  future ``GeneratedQuestionCandidate`` lifecycle.
- Rejection reasons are deterministic reason-code data for tests and callers.

Where it fits:
- Called by: ``bank.generation.LangChainQuestionGenerator`` and future
  ``GenerationBatch`` lifecycle code.
- Calls into: no external model or persistence adapter.
- Persisted via: callers may persist accepted payloads as generated candidates.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from .models import CognitiveLevel, QuestionType, SourceType

__all__ = [
    "CandidateValidationError",
    "CandidateValidationResult",
    "SUPPORTED_GENERATED_QTYPES",
    "validate_generated_questions",
]

SUPPORTED_GENERATED_QTYPES = frozenset(
    {
        QuestionType.MCQ,
        QuestionType.VSA,
        QuestionType.SA,
        QuestionType.LA,
    }
)
MARKS_BY_QTYPE = {
    QuestionType.MCQ: {1},
    QuestionType.VSA: {2},
    QuestionType.SA: {3},
    QuestionType.LA: {5},
}
WORKFLOW_FIELDS = frozenset(
    {
        "candidate_id",
        "candidateId",
        "batch_id",
        "batchId",
        "validation_status",
        "validationStatus",
        "modified",
        "discarded",
    }
)


class GeneratedQuestionRequest(Protocol):
    """Request shape needed by the generated Question gate."""

    chapter_slugs: tuple[str, ...]


@dataclass(frozen=True)
class CandidateValidationError:
    """One deterministic reason a generated candidate cannot be persisted."""

    index: int
    code: str
    detail: str


@dataclass(frozen=True)
class CandidateValidationResult:
    """Valid generated Question payloads plus all rejection reasons."""

    valid_questions: tuple[dict[str, Any], ...]
    errors: tuple[CandidateValidationError, ...]


def validate_generated_questions(
    payload: Any,
    request: GeneratedQuestionRequest,
) -> CandidateValidationResult:
    """Accept only canonical-compatible generated Question payloads."""
    if not isinstance(payload, dict):
        return CandidateValidationResult(
            valid_questions=(),
            errors=(
                CandidateValidationError(
                    0, "malformed_payload", "payload must be an object"
                ),
            ),
        )

    questions = payload.get("questions")
    if not isinstance(questions, list):
        return CandidateValidationResult(
            valid_questions=(),
            errors=(
                CandidateValidationError(
                    0, "missing_questions", "questions must be a list"
                ),
            ),
        )

    valid: list[dict[str, Any]] = []
    errors: list[CandidateValidationError] = []
    allowed_chapters = set(request.chapter_slugs)
    valid_levels = set(CognitiveLevel.values)

    for index, question in enumerate(questions):
        question_errors = _validate_one(question, index, allowed_chapters, valid_levels)
        if question_errors:
            errors.extend(question_errors)
        else:
            valid.append(question)

    return CandidateValidationResult(
        valid_questions=tuple(valid),
        errors=tuple(errors),
    )


def _validate_one(
    question: Any,
    index: int,
    allowed_chapters: set[str],
    valid_levels: set[str],
) -> list[CandidateValidationError]:
    errors: list[CandidateValidationError] = []
    if not isinstance(question, dict):
        return [
            CandidateValidationError(
                index, "malformed_question", "question must be an object"
            )
        ]

    forbidden = sorted(WORKFLOW_FIELDS & set(question))
    if forbidden:
        errors.append(
            CandidateValidationError(
                index,
                "workflow_field",
                f"workflow fields are not model payload fields: {forbidden}",
            )
        )

    for field in (
        "chapter_slug",
        "qtype",
        "marks",
        "cognitive_level",
        "raw_text",
        "content",
        "topic_names",
        "answer",
        "source",
    ):
        if field not in question:
            errors.append(CandidateValidationError(index, "missing_field", field))

    qtype = question.get("qtype")
    marks = question.get("marks")
    if qtype not in SUPPORTED_GENERATED_QTYPES:
        errors.append(CandidateValidationError(index, "bad_qtype", str(qtype)))
    elif marks not in MARKS_BY_QTYPE[qtype]:
        errors.append(
            CandidateValidationError(index, "marks_qtype_mismatch", f"{qtype}/{marks}")
        )

    if question.get("chapter_slug") not in allowed_chapters:
        errors.append(
            CandidateValidationError(
                index, "bad_chapter_slug", str(question.get("chapter_slug"))
            )
        )
    if question.get("cognitive_level") not in valid_levels:
        errors.append(
            CandidateValidationError(
                index, "bad_cognitive_level", str(question.get("cognitive_level"))
            )
        )
    _validate_content(question, index, errors)
    if not _non_empty_string(question.get("raw_text")):
        errors.append(CandidateValidationError(index, "empty_question", "raw_text"))
    if not _non_empty_string(question.get("answer")):
        errors.append(CandidateValidationError(index, "empty_answer", "answer"))
    if not _string_sequence(question.get("topic_names")):
        errors.append(CandidateValidationError(index, "bad_topic_names", "topic_names"))
    source = question.get("source")
    if not isinstance(source, dict) or source.get("type") != SourceType.AI_GENERATED:
        errors.append(CandidateValidationError(index, "bad_source", "source.type"))
    elif not _non_empty_string(source.get("name")):
        errors.append(CandidateValidationError(index, "bad_source", "source.name"))
    return errors


def _validate_content(
    question: dict[str, Any],
    index: int,
    errors: list[CandidateValidationError],
) -> None:
    content = question.get("content")
    qtype = question.get("qtype")
    if not isinstance(content, dict):
        errors.append(CandidateValidationError(index, "bad_content", "content"))
        return
    stem = content.get("stem")
    if not isinstance(stem, list) or not stem:
        errors.append(CandidateValidationError(index, "missing_stem", "content.stem"))
    if qtype == QuestionType.MCQ:
        options = content.get("options")
        if not isinstance(options, list) or len(options) != 4:
            errors.append(
                CandidateValidationError(index, "bad_mcq_options", "content.options")
            )
        elif not _answer_matches_option(question.get("answer"), options):
            errors.append(
                CandidateValidationError(index, "mcq_answer_mismatch", "answer")
            )


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _string_sequence(value: Any) -> bool:
    return (
        isinstance(value, Sequence)
        and not isinstance(value, str)
        and all(isinstance(item, str) for item in value)
    )


def _answer_matches_option(answer: Any, options: Sequence[Any]) -> bool:
    if not isinstance(answer, str):
        return False
    normalized_answer = answer.strip()
    for option in options:
        if not isinstance(option, dict):
            continue
        label = option.get("label")
        if isinstance(label, str) and _answer_names_label(normalized_answer, label):
            return True
        text = _flatten_option_text(option.get("content"))
        if text and text.lower() in normalized_answer.lower():
            return True
    return False


def _answer_names_label(answer: str, label: str) -> bool:
    escaped = re.escape(label.strip())
    if not escaped:
        return False
    return bool(
        re.match(rf"(?i)^(?:option\s+)?{escaped}(?:\s*[.)\]:-]|\s+-|\s*$)", answer)
    )


def _flatten_option_text(content: Any) -> str:
    if not isinstance(content, Sequence) or isinstance(content, str):
        return ""
    parts = [
        item.get("text", "")
        for item in content
        if isinstance(item, dict) and isinstance(item.get("text"), str)
    ]
    return " ".join(part for part in parts if part).strip()
