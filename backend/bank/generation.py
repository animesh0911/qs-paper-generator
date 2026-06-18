"""Bulk Question generation seam and deterministic candidate validation.

This module defines the provider-neutral contract for generated Question
candidates. It sits between future batch lifecycle code and ``ai_services.llm``:
callers ask a ``QuestionGenerator`` for canonical-compatible payloads, while the
adapter resolves the actual model through the shared logical model route.

Patterns / invariants:
- Generated payloads contain only Question data; batch/candidate workflow state
  belongs to the later ``GeneratedQuestionCandidate`` lifecycle.
- Validation is deterministic and pure: malformed or non-canonical model output
  is rejected before persistence.

Where it fits:
- Called by: future bulk ``GenerationBatch`` drainer (#143).
- Calls into: ``ai_services.llm.make_chat_model`` using ``question_generation``.
- Persisted via: future ``GeneratedQuestionCandidate`` rows, not ``Question``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from ai_services.llm import ModelPurpose, make_chat_model

from .models import CognitiveLevel, QuestionType, SourceType

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

QUESTION_GENERATION_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "chapter_slug": {"type": "string"},
                    "qtype": {
                        "type": "string",
                        "enum": sorted(SUPPORTED_GENERATED_QTYPES),
                    },
                    "marks": {"type": "integer"},
                    "cognitive_level": {
                        "type": "string",
                        "enum": list(CognitiveLevel.values),
                    },
                    "raw_text": {"type": "string"},
                    "content": {"type": "object"},
                    "topic_names": {"type": "array", "items": {"type": "string"}},
                    "answer": {"type": "string"},
                    "source": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": [SourceType.AI_GENERATED],
                            },
                            "name": {"type": "string"},
                        },
                        "required": ["type", "name"],
                    },
                },
                "required": [
                    "chapter_slug",
                    "qtype",
                    "marks",
                    "cognitive_level",
                    "raw_text",
                    "content",
                    "topic_names",
                    "answer",
                    "source",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["questions"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class QuestionGenerationRequest:
    """Teacher/request intent that shapes one generation call."""

    chapter_slugs: tuple[str, ...]
    topic_names: tuple[str, ...] = ()
    difficulty_targets: dict[str, int] | None = None
    question_type_distribution: dict[str, int] | None = None
    count: int = 10
    language: str = "en"


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


class QuestionGenerator(Protocol):
    """Provider-neutral interface for bulk generated Question candidates."""

    def generate(self, request: QuestionGenerationRequest) -> list[dict[str, Any]]: ...


def build_question_generation_prompt(request: QuestionGenerationRequest) -> str:
    """Render the production prompt for one bulk Question-generation call."""
    chapters = ", ".join(request.chapter_slugs)
    topics = ", ".join(request.topic_names) if request.topic_names else "none"
    difficulty = request.difficulty_targets or {
        "easy": 30,
        "medium": 50,
        "hard": 20,
    }
    distribution = request.question_type_distribution or {
        QuestionType.MCQ: 4,
        QuestionType.VSA: 2,
        QuestionType.SA: 2,
        QuestionType.LA: 2,
    }
    return "\n".join(
        [
            "Generate CBSE Class 10 Science Question-and-answer candidates.",
            f"Language: {request.language}",
            f"Chapters: {chapters}",
            f"Optional topic hints: {topics}",
            f"Total candidates: {request.count}",
            "Distribute candidates approximately equally across selected "
            "Chapters unless the configured distribution says otherwise.",
            f"Difficulty targets: {difficulty}",
            f"QuestionType/marks distribution: {distribution}",
            "Use only canonical chapter slugs and these QuestionType values: "
            "mcq, very_short_answer, short_answer, long_answer.",
            "Return the structured response schema exactly. Put answer inside "
            "each Question payload. Do not include candidate id, batch id, "
            "validation status, modified state, or discarded state.",
            "Hand-reviewed examples:",
            "- mcq/1: stem asks one concept, four options A-D, answer names "
            "the correct option and term.",
            "- very_short_answer/2: stem asks for a definition or reason, "
            "answer is one or two precise sentences.",
            "- short_answer/3: stem asks for explanation, answer gives two or "
            "three NCERT-faithful points.",
            "- long_answer/5: stem asks for a process or comparison, answer "
            "uses a structured paragraph with all key steps.",
            "Keep source.type as ai_generated and source.name as "
            "question-generation.",
        ]
    )


def validate_generated_questions(
    payload: dict[str, Any],
    request: QuestionGenerationRequest,
) -> CandidateValidationResult:
    """Accept only canonical-compatible generated Question payloads."""
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


class LangChainQuestionGenerator:
    """QuestionGenerator adapter over the shared LangChain model seam."""

    def __init__(self, make_model=make_chat_model):
        self.make_model = make_model

    def generate(self, request: QuestionGenerationRequest) -> list[dict[str, Any]]:
        model = self.make_model(ModelPurpose.QUESTION_GENERATION)
        structured = model.with_structured_output(QUESTION_GENERATION_RESPONSE_SCHEMA)
        payload = structured.invoke(build_question_generation_prompt(request))
        result = validate_generated_questions(payload, request)
        return list(result.valid_questions)


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
    normalized_answer = answer.strip().lower()
    for option in options:
        if not isinstance(option, dict):
            continue
        label = option.get("label")
        if isinstance(label, str) and normalized_answer.startswith(label.lower()):
            return True
        text = _flatten_option_text(option.get("content"))
        if text and text.lower() in normalized_answer:
            return True
    return False


def _flatten_option_text(content: Any) -> str:
    if not isinstance(content, Sequence) or isinstance(content, str):
        return ""
    parts = [
        item.get("text", "")
        for item in content
        if isinstance(item, dict) and isinstance(item.get("text"), str)
    ]
    return " ".join(part for part in parts if part).strip()
