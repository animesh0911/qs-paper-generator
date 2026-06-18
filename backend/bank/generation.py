"""Bulk Question generation seam and model adapter.

This module defines the provider-neutral contract for generated Question
candidates. It sits between future batch lifecycle code and ``ai_services.llm``:
callers ask a ``QuestionGenerator`` for canonical-compatible payloads, while the
adapter resolves the actual model through the shared logical model route and
the generated Question gate validates untrusted model output.

Patterns / invariants:
- Generated payloads contain only Question data; batch/candidate workflow state
  belongs to the later ``GeneratedQuestionCandidate`` lifecycle.
- Validation is deterministic and pure: malformed or non-canonical model output
  is delegated to ``bank.generated_question_gate`` before persistence.

Where it fits:
- Called by: future bulk ``GenerationBatch`` drainer (#143).
- Calls into: ``ai_services.llm.make_chat_model`` using ``question_generation``.
- Persisted via: future ``GeneratedQuestionCandidate`` rows, not ``Question``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ai_services.llm import ModelPurpose, make_chat_model

from .generated_question_gate import (
    SUPPORTED_GENERATED_QTYPES,
    CandidateValidationError,
    CandidateValidationResult,
    validate_generated_questions,
)
from .models import CognitiveLevel, QuestionType, SourceType

__all__ = [
    "CandidateValidationError",
    "CandidateValidationResult",
    "LangChainQuestionGenerator",
    "QUESTION_GENERATION_RESPONSE_SCHEMA",
    "QuestionGenerationRequest",
    "QuestionGenerator",
    "build_question_generation_prompt",
    "validate_generated_questions",
]

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
