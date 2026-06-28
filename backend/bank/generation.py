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

from collections.abc import Sequence
from dataclasses import dataclass
from math import ceil
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
    "DIFFICULTY_TARGETS_BY_PRESET",
    "LangChainQuestionGenerator",
    "QUESTION_GENERATION_RESPONSE_SCHEMA",
    "QuestionGenerationRequest",
    "QuestionGenerator",
    "build_question_generation_prompt",
    "node_question_targets",
    "select_balanced_questions",
    "validate_generated_questions",
]

DIFFICULTY_TARGETS_BY_PRESET = {
    "balanced": {"easy": 30, "medium": 50, "hard": 20},
    "easy": {"easy": 60, "medium": 30, "hard": 10},
    "hard": {"easy": 10, "medium": 40, "hard": 50},
}

# Per topic node we ask the model for this fraction of extra candidates above
# the node's final target so deterministic selection has spare to draw from when
# the model under-delivers for a node. The single paid call stays single
# (Rule 13): the surplus is trimmed locally, never re-billed.
GENERATION_HEADROOM_RATIO = 0.5

QUESTION_GENERATION_RESPONSE_SCHEMA: dict[str, Any] = {
    "title": "QuestionGenerationResponse",
    "description": "Structured CBSE Question-and-answer candidates.",
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
                        "enum": sorted(
                            str(qtype) for qtype in SUPPORTED_GENERATED_QTYPES
                        ),
                    },
                    "marks": {"type": "integer"},
                    "cognitive_level": {
                        "type": "string",
                        "enum": list(CognitiveLevel.values),
                    },
                    "raw_text": {"type": "string", "minLength": 1},
                    "content": {
                        "type": "object",
                        "properties": {
                            "stem": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "type": {
                                            "type": "string",
                                            "enum": ["paragraph"],
                                        },
                                        "text": {"type": "string"},
                                    },
                                    "required": ["type", "text"],
                                    "additionalProperties": False,
                                },
                            },
                            "options": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "label": {"type": "string"},
                                        "content": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "type": {
                                                        "type": "string",
                                                        "enum": ["paragraph"],
                                                    },
                                                    "text": {"type": "string"},
                                                },
                                                "required": ["type", "text"],
                                                "additionalProperties": False,
                                            },
                                        },
                                    },
                                    "required": ["label", "content"],
                                    "additionalProperties": False,
                                },
                            },
                        },
                        "required": ["stem"],
                        "additionalProperties": False,
                    },
                    "topic_names": {"type": "array", "items": {"type": "string"}},
                    "answer": {"type": "string"},
                    "question_citation_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "answer_citation_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "source": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": [str(SourceType.AI_GENERATED)],
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
                    "question_citation_ids",
                    "answer_citation_ids",
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
    chapter_map_node_ids: tuple[str, ...] = ()
    topic_names: tuple[str, ...] = ()
    difficulty_targets: dict[str, int] | None = None
    question_type_distribution: dict[str, int] | None = None
    grounding_manifest: dict[str, Any] | None = None
    count: int = 10
    language: str = "en"


class QuestionGenerator(Protocol):
    """Provider-neutral interface for bulk generated Question candidates."""

    def generate(self, request: QuestionGenerationRequest) -> list[dict[str, Any]]: ...


def _default_distribution_for_count(count: int) -> dict[str, int]:
    """Return a small CBSE-shaped type mix whose values sum to ``count``."""
    if count < 1:
        return {}
    order = (QuestionType.MCQ, QuestionType.VSA, QuestionType.SA, QuestionType.LA)
    distribution = {str(qtype): 0 for qtype in order}
    for index in range(count):
        distribution[str(order[index % len(order)])] += 1
    return {qtype: value for qtype, value in distribution.items() if value}


def node_question_targets(
    chapter_map_node_ids: tuple[str, ...], count: int
) -> dict[str, int]:
    """Split ``count`` as evenly as possible across the selected topic nodes.

    The remainder lands on the earliest nodes so the split is deterministic and
    the values always sum to ``count``. Returns an empty mapping when there are
    no topic nodes (the ungrounded, chapter-only path keeps its old behaviour).
    """
    nodes = list(dict.fromkeys(chapter_map_node_ids))
    if not nodes or count < 1:
        return {}
    base, remainder = divmod(count, len(nodes))
    return {
        node_id: base + (1 if index < remainder else 0)
        for index, node_id in enumerate(nodes)
    }


def _generation_targets_per_node(targets: dict[str, int]) -> dict[str, int]:
    """How many candidates to request per node, padded with review headroom."""
    return {
        node_id: final + max(1, ceil(final * GENERATION_HEADROOM_RATIO))
        for node_id, final in targets.items()
        if final >= 1
    }


def _node_citation_ids(grounding_manifest: dict[str, Any] | None) -> dict[str, set]:
    """Map each topic node id to the citation ids of its grounding excerpts."""
    mapping: dict[str, set] = {}
    for excerpt in (grounding_manifest or {}).get("excerpts", []):
        if not isinstance(excerpt, dict):
            continue
        node_id = excerpt.get("chapter_map_node_id")
        citation_id = excerpt.get("citation_id")
        if isinstance(node_id, str) and isinstance(citation_id, str):
            mapping.setdefault(node_id, set()).add(citation_id)
    return mapping


def _attribute_node(
    question: dict[str, Any],
    node_citation_map: dict[str, set],
    target_nodes: list[str],
) -> str | None:
    """Attribute a question to the target node whose excerpts it cites most."""
    cited = [
        citation_id
        for citation_id in (question.get("question_citation_ids") or [])
        if isinstance(citation_id, str)
    ]
    best_node: str | None = None
    best_overlap = 0
    for node_id in target_nodes:
        node_citations = node_citation_map.get(node_id, set())
        overlap = sum(1 for citation_id in cited if citation_id in node_citations)
        if overlap > best_overlap:
            best_node, best_overlap = node_id, overlap
    return best_node


def select_balanced_questions(
    questions: Sequence[dict[str, Any]],
    targets: dict[str, int],
    grounding_manifest: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Trim validated candidates down to an even per-topic-node distribution.

    Each candidate is attributed to a topic node by its citations; up to that
    node's target is kept. Any surplus (or candidates that match no node) is
    used to backfill toward the total only when a node under-delivered, so the
    result is as even as the model's output allows without a second paid call.
    """
    if not targets:
        return list(questions)
    node_citation_map = _node_citation_ids(grounding_manifest)
    target_nodes = list(targets)
    by_node: dict[str, list[dict[str, Any]]] = {node_id: [] for node_id in target_nodes}
    leftovers: list[dict[str, Any]] = []
    for question in questions:
        node_id = _attribute_node(question, node_citation_map, target_nodes)
        if node_id is None:
            leftovers.append(question)
        else:
            by_node[node_id].append(question)

    selected: list[dict[str, Any]] = []
    for node_id in target_nodes:
        target = targets[node_id]
        selected.extend(by_node[node_id][:target])
        leftovers.extend(by_node[node_id][target:])

    total = sum(targets.values())
    if len(selected) < total:
        selected.extend(leftovers[: total - len(selected)])
    return selected


def build_question_generation_prompt(request: QuestionGenerationRequest) -> str:
    """Render the production prompt for one bulk Question-generation call."""
    chapters = ", ".join(request.chapter_slugs)
    topic_nodes = (
        ", ".join(request.chapter_map_node_ids)
        if request.chapter_map_node_ids
        else "none"
    )
    topics = ", ".join(request.topic_names) if request.topic_names else "none"
    difficulty = request.difficulty_targets or {
        "easy": 30,
        "medium": 50,
        "hard": 20,
    }
    targets = node_question_targets(request.chapter_map_node_ids, request.count)
    generation_targets = _generation_targets_per_node(targets)
    total_candidates = sum(generation_targets.values()) or request.count
    distribution = (
        request.question_type_distribution
        or _default_distribution_for_count(total_candidates)
    )
    per_node_lines = _per_node_target_lines(targets, generation_targets)
    grounding_lines = _grounding_prompt_lines(request.grounding_manifest)
    return "\n".join(
        [
            "Generate CBSE Class 10 Science Question-and-answer candidates.",
            f"Language: {request.language}",
            f"Chapters: {chapters}",
            f"Selected NCERT topic node ids: {topic_nodes}",
            f"Optional topic hints: {topics}",
            f"Total candidates: exactly {total_candidates}",
            "Distribute candidates approximately equally across selected "
            "Chapters unless the configured distribution says otherwise.",
            *per_node_lines,
            f"Difficulty targets: {difficulty}",
            f"Requested counts by QuestionType: {distribution}",
            "Marks are fixed by QuestionType: mcq=1, very_short_answer=2, "
            "short_answer=3, long_answer=5.",
            "raw_text must be a non-empty plain-text copy of the full Question "
            "stem; do not leave it blank when content.stem is present.",
            "Use content.stem as an array of paragraph blocks. For MCQ only, "
            "include content.options as four objects with label A-D and "
            "paragraph content; non-MCQ content must still include content.stem.",
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
            *grounding_lines,
        ]
    )


def _per_node_target_lines(
    targets: dict[str, int], generation_targets: dict[str, int]
) -> list[str]:
    """Prompt lines giving an explicit per-topic-node candidate breakdown."""
    if not generation_targets:
        return []
    lines = [
        "Per-topic question targets: generate the listed count for EACH topic "
        "node id so reviewers have spare candidates to choose from. Spread "
        "candidates evenly across the topic nodes below; do not concentrate "
        "them on one topic.",
    ]
    for node_id, generate_count in generation_targets.items():
        lines.append(
            f"- topic node {node_id}: generate {generate_count} candidates "
            f"(final target {targets[node_id]})"
        )
    lines.append(
        "Attribute each candidate to its topic node by citing that node's "
        "supplied excerpts in question_citation_ids."
    )
    return lines


def _grounding_prompt_lines(grounding_manifest: dict[str, Any] | None) -> list[str]:
    if not grounding_manifest:
        return []
    lines = [
        "Grounding requirements:",
        "Use only the NCERT excerpts supplied below for factual claims.",
        "Use NCERT-faithful terminology and refuse unsupported requests by "
        "returning no candidate for that unsupported idea.",
        "For every candidate, include non-empty question_citation_ids and "
        "answer_citation_ids chosen from the supplied citation_id values.",
        "Do not generate diagram-image questions. Caption-aware text questions "
        "are allowed only when supported by caption/prose context below.",
        "Unsupported content policy: "
        f"{grounding_manifest.get('unsupported_content_policy', '')}",
    ]
    for excerpt in grounding_manifest.get("excerpts", []):
        lines.extend(
            [
                f"[citation_id: {excerpt.get('citation_id')}]",
                f"ChapterMapNode: {excerpt.get('chapter_map_node_id')}",
                f"Pages: {excerpt.get('pages')}",
                f"Content types: {excerpt.get('content_types')}",
                str(excerpt.get("text", "")),
            ]
        )
    return lines


class LangChainQuestionGenerator:
    """QuestionGenerator adapter over the shared LangChain model seam."""

    def __init__(self, make_model=make_chat_model):
        self.make_model = make_model

    def generate(self, request: QuestionGenerationRequest) -> list[dict[str, Any]]:
        model = self.make_model(ModelPurpose.QUESTION_GENERATION)
        structured = model.with_structured_output(QUESTION_GENERATION_RESPONSE_SCHEMA)
        payload = structured.invoke(build_question_generation_prompt(request))
        result = validate_generated_questions(payload, request)
        targets = node_question_targets(request.chapter_map_node_ids, request.count)
        return select_balanced_questions(
            result.valid_questions, targets, request.grounding_manifest
        )
